# MULE : format du flux, version 4

Ce document est **normatif** pour le décodeur. Les implémentations de référence sont le décodeur `core/dec.c`, en entiers seulement, et l'encodeur `core/enc.c`. **La sortie du décodeur de référence est normative au bit près** : c'est elle que joue le lecteur, et un autre décodeur conforme doit donner les mêmes échantillons sur 16 bits. Tout ce qui n'est pas décrit ici, comme la psychoacoustique, l'allocation, la stéréo ou la commutation de blocs, relève des **choix de l'encodeur** : le décodeur se contente de lire.

Conventions :
- entiers en petit-boutiste ;
- `>>` désigne la division entière par excès vers −∞ (floor) ;
- *M(s, c)* désigne un symbole décodé avec le modèle adaptatif du flux *s*, contexte *c* ;
- *R(n)* désigne *n* bits bruts (1 ≤ n ≤ 15).

## 1. Encapsulation Ogg

Un flux logique Ogg (RFC 3533), qui contient dans l'ordre :

1. un paquet `MULEHead`, seul sur la première page (drapeau BOS) ;
2. un paquet `MULETags`, seul sur la deuxième page ;
3. des paquets audio, regroupés en pages d'environ 4 Kio.

La **granule** d'une page est le nombre d'échantillons par canal que le décodeur a produits à la fin du dernier paquet achevé sur cette page, **pre_skip compris**. La dernière page (drapeau EOS) a pour granule `pre_skip + longueur`. Le lecteur coupe au début les `pre_skip` premiers échantillons, et à la fin tout ce qui dépasse la granule de fin, ce qui donne une lecture sans blanc.

### MULEHead (22 octets ; 20 en v2)

| Octets | Champ | Valeur |
|---|---|---|
| 0–7 | signature | `MULEHead` |
| 8 | version | 4 (la v3 plus le bruit dans les zéros des bandes codées et le bruit en pente, §5, §5.3 ; historique au §7). Le décodeur de référence lit aussi la v3 (même en-tête, sans les ajouts de la v4) et la v2 (en-tête de 20 octets, sans les octets 20 et 21) |
| 9 | canaux | 2 |
| 10–11 | pre_skip | 1024 |
| 12–15 | fréquence | 44100 (le format n'est réglé que pour 44,1 kHz) |
| 16 | bandes codées | 22 |
| 17 | trames entre paquets clés | indicatif (40) |
| 18 | trames par paquet | indicatif (4) |
| 19 | jeu de CDF initiales | 2 = `core/init_cdf.h` actuel (v2, entraîné sur les statistiques de la TCQ). **Le décodeur refuse un flux dont il n'a pas les tables** : les CDF initiales font partie du format, et un réentraînement produira un nouvel identifiant |
| 20 | taille du treillis | log2 du nombre d'états : 3 à 6 (8 à 64 états) ; l'encodeur écrit 6. v2 : 8 états |
| 21 | drapeaux | bit 0 `MULE_TCQ_CHAIN` : l'état du treillis se poursuit d'une bande à l'autre (§5.3) ; bit 1 `MULE_COEF_A8` : coefficients sur 8 symboles (§3, §5.3). L'encodeur écrit les deux (3) ; les autres valeurs ne servent qu'aux comparaisons. Bits 2 à 7 : 0, sinon le flux est refusé. v2 : 0 |

### MULETags

Même structure que `OpusTags` (RFC 7845 §5.2), avec la signature `MULETags` :
- vendor : longueur u32 + UTF-8 ;
- nombre de commentaires : u32 ;
- chaque commentaire : longueur u32 + `CLÉ=valeur` en UTF-8.

## 2. Paquet audio

| Octets | Champ |
|---|---|
| 0 | bit 0 : **clé** ; bits 1–3 : nombre de trames − 1 (1 à 8 trames) |
| 1–4 | présent seulement si clé : indice de la première trame (u32) |
| puis 4 | état rANS initial `x` (u32) |
| puis | mots de 16 bits, lus dans l'ordre |

**Taille maximale : 8192 octets.** L'encodeur la garantit en découpant si nécessaire.

**Paquet clé** : avant sa première trame, le décodeur remet tout son état à zéro (§4). Après un saut dans le fichier, le décodeur ignore les paquets jusqu'au premier paquet clé, puis jette la sortie de la première trame de celui-ci : son recouvrement de la trame précédente manque.

### Décodage rANS

- état `x` sur 32 bits, probabilités sur 15 bits, `L = 2^16` ;
- symbole de début `start` et de fréquence `freq`, avec `slot = x & 0x7FFF` :
  `x = freq·(x >> 15) + slot − start` ; puis si `x < L`, `x = (x << 16) | mot16 suivant` ;
- symbole d'un modèle : le premier `s` tel que `slot < start(s) + freq(s)` (§3) ;
- bits bruts R(n) : `freq = 2^(15−n)`, valeur `v = slot >> (15 − n)`, `start = v·freq`.

À la fin du paquet, `x` doit valoir `L` et tous les mots doivent avoir été lus. C'est un contrôle d'intégrité.

## 3. Modèles adaptatifs

Chaque modèle possède `n` symboles et une CDF `cdf[0..n]` sur 15 bits (`cdf[0] = 0`, `cdf[n] = 32768`), plus un compteur `count`.

**Plage codée** du symbole `s` : `span = 32768 − 4n` ;
- `start(s) = (cdf[s]·span >> 15) + 4s` ;
- `start(n) = 32768` ;
- `freq(s) = start(s+1) − start(s)`.

Chaque symbole garde donc une fréquence d'au moins 4.

**Adaptation** après le symbole `s` :
- `rate = 4 + (count > 15) + (count > 31) + (n > 4)` ;
- pour chaque `i` de 1 à n−1 : si `i > s`, `cdf[i] += (32768 − cdf[i]) >> rate` ; sinon `cdf[i] −= cdf[i] >> rate` ;
- `count = min(count + 1, 32)`.

**Initialisation** au paquet clé : les CDF entraînées de `core/init_cdf.h` avec `count = 16` (avec `MULE_COEF_A8`, celles des flux `coef` et `cesc` viennent de `core/init_cdf_a8.h`), ou la CDF uniforme `cdf[i] = 32768·i / n` avec `count = 0` pour un flux sans table.

| Flux | Symboles | Contextes |
|---|---|---|
| btype | 2 | 1 |
| alpha | 4 | 1 |
| stereo | 2 | 3 |
| energy | 16 | 9 |
| alloc | 16 | 6 |
| amode | 2 | 1 |
| cesc | 16 | 16 |
| coef | 8 (16 sans `MULE_COEF_A8`, et en v2) | 96 |
| eaesc | 16 | 1 |

`classe(b) = 0` si b < 8, `1` si b < 16, `2` sinon.

## 4. État du décodeur et remise à zéro

État remis à zéro à chaque paquet clé :
- les modèles (§3) ;
- `Qprev[c][b] = −40` et `Aprev[c][b] = 20` pour les deux canaux codés et les 22 bandes ;
- l'état inter-trame `valide[c] = 0` ;
- le générateur de bruit `lcg = 0x2545F491`.

État conservé d'un paquet à l'autre, mais pas à travers un saut :
- le type de la trame précédente (long au départ) ;
- l'accumulateur de recouvrement ;
- la demi-fenêtre en attente.

## 5. Trame

```
type            = M(btype, 0)                 0 : longue, 1 : 8 courtes
si courte :
  masque        = R(7)                        bit k−1 = 1 : un groupe commence à la fenêtre k (k = 1..7)
ai              = M(alpha, 0)                 α = {0, 16, 26, 31}[ai]
pour b < 22 :
  ms[b]         = M(stereo, classe(b))        1 : la bande est codée en M/S
pour c = 0, 1 :                               canal codé (L/M, R/S)
  si v4 : nf = R(3)                           niveau du bruit des zéros (§5.3), 0 : aucun
  queues = (0, 0)                             |y| des deux coefficients précédents, sur toute la trame
  pour chaque groupe g (1 en trame longue) :
    énergies, allocation, coefficients        §5.1 à §5.3
  si longue : état inter-trame de c = (|y|, Q, a) de cette trame, valide = 1 ; sinon valide = 0
```

**Groupes** : en trame longue, un seul groupe d'une seule fenêtre de 1024 coefficients. En trame courte, les fenêtres 0 à 7 (128 coefficients chacune) sont découpées selon le masque.

**Bandes** : les bords sont `E = {0,1,2,3,4,5,6,7,8,10,12,14,16,20,24,28,34,40,48,60,78,100,116}`.
- trame longue : la bande b couvre les coefficients `[8·E[b], 8·E[b+1])` ;
- trame courte : dans un groupe de fenêtres `[k0, k1)`, la bande b couvre `[E[b], E[b+1])` de chaque fenêtre ;
- **ordre de parcours** : fenêtre par fenêtre, puis par fréquence croissante.

Le nombre de coefficients d'une bande est `n_b`.

### 5.1 Énergies

```
α_g = α si g = 0, sinon 26 ;  gauche = Qprev[c][0] ;  rprec = 0
pour b < 22 :
  s = M(energy, 3·classe(b) + min(|rprec|, 2))
  r = val(s)                                  (§5.4)
  Q[b] = ((α_g·Qprev[c][b] + (32 − α_g)·gauche) >> 5) + r
  gauche = Q[b] ;  rprec = r
Qprev[c] = Q
```

La bande a une énergie efficace par coefficient de `rms_b = 2^(Q[b]/4)`. Une bande avec `Q[b] ≤ −100` est silencieuse (coefficients nuls).

**Validité** : un flux valide a toujours `−100 ≤ Q[b] ≤ 20` (`MULE_QMIN`, `MULE_QMAX`). Le décodeur rejette le paquet qui contient une énergie hors de ces bornes (flux endommagé).

### 5.2 Allocation

```
mode = M(amode, 0)
pour b < 22 :
  d = val(M(alloc, classe(b) + 3·mode))
  a[b] = d + (mode ? Aprev[c][b] : (b > 0 ? a[b−1] : Aprev[c][0]))
Aprev[c] = a
```

**Validité** : un flux valide a toujours `0 ≤ a[b] ≤ 47` (`MULE_AMAX`). Le décodeur rejette le paquet qui contient une allocation hors de ces bornes. Ces deux règles bornent les contextes, les échelles et les décalages du décodeur en virgule fixe ; elles ont été ajoutées après le fuzzing (novembre 2026), sans changer aucun flux produit par l'encodeur.

### 5.3 Coefficients

Pour chaque bande b avec `Q[b] > −100` :

**Si a[b] = 0 : bruit.**
- `n_b` valeurs : `lcg = 1664525·lcg + 1013904223 (mod 2^32)`, puis `z_i = (lcg >> 16) − 32768` ;
- `X_i = z_i · rms_b · sqrt(n_b / Σz²)`.

**v4, bruit en pente** (trame longue, `b ≥ 12`) : le bruit suit la pente des niveaux des bandes voisines.
- `l = b − 1` si `b > 0` et `Q[b−1] > −100`, sinon `l = b` ; `r = b + 1` si `b < 21` et `Q[b+1] > −100`, sinon `r = b` ; `c_k = 4·(E[k] + E[k+1])` (centre de la bande k, en coefficients) ;
- si `l = r`, ou si la pente `s` ci-dessous est nulle : le bruit plat ci-dessus ;
- sinon `s = ((Q[r] − Q[l]) << 14) div (c_r − c_l)` (log2 par coefficient en Q16, division entière tronquée vers 0), bornée à `±(2^16 div max(n_b div 2, 1))`, soit ±6 dB aux bords de la bande ;
- pour `i < n_b` : `lcg` comme ci-dessus, `w_i = 2^((s·(8·E[b] + i − c_b) + (s >> 1)) / 2^16)` en Q16, `z_i = (((lcg >> 16) − 32768) · w_i) >> 18` ; puis `X_i = z_i · rms_b · sqrt(n_b / Σz²)` comme le bruit plat (tous nuls si `Σz² = 0`).
- `2^x` en Q16 est celui de `core/dec.c` (`exp2_q16`) : `x = i + f` (`i = x >> 16`, `f = x & 0xFFFF`), `p = 65536 + (f·(45426 + (f·(15743 + (f·4367 >> 16)) >> 16)) >> 16)`, puis `p << i` ou `p >> −i`.

**Sinon** : quantification **TCQ**, treillis de `N` états (`N = 2^octet20`, 64 pour l'encodeur ; 8 en v2). Pas `Δ = 2^((9 − a[b])/4)`, `ac = min(a[b] div 3, 15)`.

**État initial.** L'état `t` du treillis vaut 0 au début de chaque groupe (§5 : la trame longue, ou chaque groupe de fenêtres d'une trame courte) de chaque canal. Avec `MULE_TCQ_CHAIN`, il se poursuit d'une bande codée à la suivante du même groupe : chaque bande commence dans l'état où la précédente bande codée (`a > 0`) a fini ; les bandes silencieuses et les bandes de bruit ne le changent pas. Sans ce drapeau (et en v2), `t = 0` au début de chaque bande.

**Treillis.** Avec le masque `μ = {8 : 0x6, 16 : 0xD, 32 : 0x17, 64 : 0x33}[N]` et `par(v)` la parité du nombre de bits à 1 de `v`, pour l'état `t` et la branche `br` ∈ {0, 1} :

```
SUIVANT[t][br] = (2·t + br) mod N
SOUSENS[t][br] = (t & 1) + 2·(br ⊕ par(t & μ))
```

Pour `N = 8`, ce sont les tables de JPEG 2000 partie 2 (celles de la v2) :

```
SUIVANT[t][br]    = {0,1} {2,3} {4,5} {6,7} {0,1} {2,3} {4,5} {6,7}
SOUSENS[t][br]    = {0,2} {1,3} {2,0} {3,1} {2,0} {3,1} {0,2} {1,3}
```

Un niveau `k` (entier signé) appartient au sous-ensemble `j = k mod 4` (reste dans 0..3). Depuis l'état `t`, l'état suivant est `SUIVANT[t][br]`, pour la branche `br` telle que `SOUSENS[t][br] = j`. Les états pairs n'utilisent que des niveaux pairs, les états impairs que des niveaux impairs. Le décodeur de référence remplit à l'initialisation une table de `N × 4` octets (état suivant selon `k mod 4`).
- **Prédiction inter-trame**, si la trame est longue, `valide[c]` et `a_prev[b] > 0` (état inter-trame de c) :
  - `e = Q_prev[b] − Q[b] + a[b] − a_prev[b]` ;
  - pour le coefficient d'indice `k` : `v = |y_prev[k]| · {256, 304, 362, 431}[e & 3]` ;
  - `sh = e >> 2` ; `pm = sh ≥ 0 ? (v << min(sh, 8)) >> 8 : v >> (8 − sh)` ; `pm = min(pm, 31)`.
- **Pour chaque coefficient**, dans l'ordre de parcours :

```
m = 2·queue1 + queue2 ;  si prédiction inter-trame : m = (m + 3·pm + 1) >> 1
nc = {0,1,2,3,3,4,4,4,4}[m] si m < 9, sinon 5
s = M(coef, 6·ac + nc)
E = 7 avec MULE_COEF_A8 (alphabet de 8 symboles), 15 sinon (16 symboles, et v2)
si s < E : u = s
sinon    : k = M(cesc, ac) ;  u = E + 2^k − 1 + R(k)        (R(0) = 0)
si t pair : |k| = 2u ;      signe lu (R(1) = 1 : négatif) seulement si u > 0
si t impair : |k| = 2u + 1 ; signe toujours lu
t = état suivant après le niveau k (tables ci-dessus)
X = k · (Δ/2) · rms_b ;  queue2 = queue1 ;  queue1 = u
v4, si b ≥ 12, k = 0 et nf > 0 :
   lcg comme pour le bruit ;  z = (lcg >> 16) − 32768
   X = ((z · G[nf]) >> 15) · (Δ/2) · rms_b / 256,   G = {0, 222, 157, 111, 78, 55, 39, 28}
```

**v4, bruit des zéros** : dans une bande codée à partir de la bande 12 (2,8 kHz), un coefficient au niveau 0 reçoit un bruit uniforme d'écart type `0,5 · 2^(−(nf−1)/2)` fois `(Δ/2)·rms_b` (de −6 à −24 dB ; `G[nf]` vaut ce gain fois √3 en Q8). Le générateur `lcg` avance seulement pour ces coefficients. L'encodeur choisit `nf` d'après ce que ses zéros laissent de côté (`core/enc.c`, `nf_level`, moins 6 dB).

### 5.4 Résidus signés (énergies, allocation)

`val(s) = s − 7` si `s < 15`.

Sinon :
- `k = M(eaesc, 0)` ;
- `v = 2^k − 1 + R(k)` ;
- `|val| = v + 8` ;
- le signe est négatif si `R(1) = 1`.

### 5.5 Stéréo

Pour chaque bande avec `ms[b] = 1`, et pour tous ses coefficients :
- `L = (M + S)/√2` ;
- `R = (M − S)/√2`.

## 6. Synthèse

MDCT orthonormée : `y[i] = sqrt(2/M)·Σ_k X[k]·cos(2π/N·(i + 1/2 + N/4)·(k + 1/2))`, avec `N = 2M`.

**Fenêtres** :
- pente montante de longueur s : `w(i) = sin(π/2 · sin²(π(i + 1/2)/(2s)))` ;
- demi-fenêtre longue (1024 échantillons) de pente s : `(1024 − s)/2` zéros, la pente, puis des uns ;
- `s = 1024` si la trame voisine de ce côté est longue, `128` si elle est courte ;
- fenêtre courte : pente de 128 montante, puis descendante.

**Recouvrement**. L'accumulateur `acc` couvre 2048 échantillons à partir du début de la trame courante. Pour chaque trame :

1. si la trame précédente était longue : ajouter à `acc[0..1023]` sa demi-IMDCT droite en attente, fenêtrée par la demi-fenêtre descendante dont la pente dépend du type de **cette** trame ;
2. trame longue : IMDCT de 2048 ; ajouter la moitié gauche × la demi-fenêtre montante (pente selon le type précédent) à `acc[0..1023]`, et garder la moitié droite en attente ;
   trame courte : pour k = 0 à 7, IMDCT de 256 de la fenêtre k × la fenêtre courte, ajoutée à `acc[448 + 128k ..]` ;
3. émettre `acc[0..1023]`, puis décaler l'accumulateur de 1024 échantillons.

Chaque trame produit 1024 échantillons par canal. La première sortie correspond au pre_skip.

Les contextes (queues, prédiction inter-trame `y_prev`) portent sur l'index `u` et non sur le niveau `k`. L'état inter-trame `y_prev` conserve `min(u, 65535)` : l'index est **saturé à 65535** (16 bits). Ce n'est perceptible que pour des variations de plus de 90 dB d'une trame à l'autre, mais c'est normatif, puisque cette valeur entre dans le contexte.

## 7. Limites et historique

Limites connues :
- fréquence de 44,1 kHz et stéréo seulement ;
- la reconstruction et la synthèse ne sont décrites ici qu'en valeurs réelles (§5.3, §6). Leur version exacte, en entiers, est celle de `core/dec.c` : coefficients en Q24, IMDCT par une FFT de n/4 points, tables de `core/fx_tables.h`.

Historique (aucun fichier v0 ou v1 conservé ; le décodeur refuse les versions et les tables qu'il ne connaît pas) :
- **v0** : 480 contextes `coef`, avec l'index `5·(6·ac + nc)`, dont 96 seulement étaient atteignables ;
- **v1** : 96 contextes, compression identique au bit près. Quantification **scalaire** `X = y·Δ·rms_b` (|y| codé, signe si |y| > 0), table de CDF 1 ;
- **v2** (P4, 17/11/2026) : quantification **TCQ** (§5.3), table de CDF 2 entraînée sur 200 extraits indépendants. Gain mesuré sur le jeu de test, à débit égal, par rapport à v1 avec le même encodeur : ODG +0,06 à 128 kb/s et +0,04 à 160, sans régression (`docs/VARIANTS-BC.md`). En écoute ABX, transparent à 160 kb/s sur les 6 extraits critiques (`eval/results/G2-ABX.md`).
- **v4** (21/11/2026, dans `main` depuis le 22/11/2026) : même en-tête que la v3, octet 8 à 4 ; par canal et par trame, 3 bits bruts avant les énergies (niveau du bruit des zéros) ; bruit dans les zéros des bandes codées à partir de la bande 12 ; bruit en pente dans les bandes de bruit des trames longues à partir de la bande 12, borné à ±6 dB. L'encodeur ajoute la garde tonale (choix d'encodeur). Sur le jeu de test (30 extraits), au même débit contre la v3 : ODG +0,022 vers 121 kb/s et +0,019 vers 151, ViSQOL +0,025 et +0,013, Zimtohrli −3,2 % et −1,9 %, ODG avancé −0,009 et −0,005 ; gain presque nul vers 180 kb/s (`eval/results/N-LOG.md`, `docs/V4.md`).
- **v3** (19/11/2026) : en-tête de 22 octets (octets 20 et 21) ; treillis de 64 états dont l'état se poursuit d'une bande à l'autre (Viterbi conjoint sur le groupe dans l'encodeur) ; coefficients sur 8 symboles, échappement à 7, avec leurs propres CDF initiales (`core/init_cdf_a8.h`, liées au drapeau, l'octet 19 restant à 2). Sur le jeu de test, à débit égal contre la v2 : ODG +0,036 à 128 kb/s et +0,015 à 160, ODG avancé +0,041 et +0,017, une régression (`eval/results/B-LOG.md`). Décodeur : −8 % d'instructions sur Cortex-M3 (`eval/results/C-LOG.md`).
