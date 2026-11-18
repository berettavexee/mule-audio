# MULE : format du flux, version 2

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

### MULEHead (20 octets)

| Octets | Champ | Valeur |
|---|---|---|
| 0–7 | signature | `MULEHead` |
| 8 | version | 2 (quantification TCQ de la forme ; historique des versions au §7) |
| 9 | canaux | 2 |
| 10–11 | pre_skip | 1024 |
| 12–15 | fréquence | 44100 (le format n'est réglé que pour 44,1 kHz) |
| 16 | bandes codées | 22 |
| 17 | trames entre paquets clés | indicatif (40) |
| 18 | trames par paquet | indicatif (4) |
| 19 | jeu de CDF initiales | 2 = `core/init_cdf.h` actuel (v2, entraîné sur les statistiques de la TCQ). **Le décodeur refuse un flux dont il n'a pas les tables** : les CDF initiales font partie du format, et un réentraînement produira un nouvel identifiant |

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

**Initialisation** au paquet clé : les CDF entraînées de `core/init_cdf.h` avec `count = 16`, ou la CDF uniforme `cdf[i] = 32768·i / n` avec `count = 0` pour un flux sans table.

| Flux | Symboles | Contextes |
|---|---|---|
| btype | 2 | 1 |
| alpha | 4 | 1 |
| stereo | 2 | 3 |
| energy | 16 | 9 |
| alloc | 16 | 6 |
| amode | 2 | 1 |
| cesc | 16 | 16 |
| coef | 16 | 96 |
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

**Sinon** : quantification **TCQ** (treillis à 8 états, celui de JPEG 2000 partie 2). Pas `Δ = 2^((9 − a[b])/4)`, `ac = min(a[b] div 3, 15)`. L'état `t` du treillis vaut **0 au début de chaque bande**.

Tables du treillis, pour l'état `t` et la branche `br` ∈ {0, 1} :

```
SUIVANT[t][br]    = {0,1} {2,3} {4,5} {6,7} {0,1} {2,3} {4,5} {6,7}
SOUSENS[t][br]    = {0,2} {1,3} {2,0} {3,1} {2,0} {3,1} {0,2} {1,3}
```

Un niveau `k` (entier signé) appartient au sous-ensemble `j = k mod 4` (reste dans 0..3). Depuis l'état `t`, l'état suivant est `SUIVANT[t][br]`, pour la branche `br` telle que `SOUSENS[t][br] = j`. Les états pairs n'utilisent que des niveaux pairs, les états impairs que des niveaux impairs.
- **Prédiction inter-trame**, si la trame est longue, `valide[c]` et `a_prev[b] > 0` (état inter-trame de c) :
  - `e = Q_prev[b] − Q[b] + a[b] − a_prev[b]` ;
  - pour le coefficient d'indice `k` : `v = |y_prev[k]| · {256, 304, 362, 431}[e & 3]` ;
  - `sh = e >> 2` ; `pm = sh ≥ 0 ? (v << min(sh, 8)) >> 8 : v >> (8 − sh)` ; `pm = min(pm, 31)`.
- **Pour chaque coefficient**, dans l'ordre de parcours :

```
m = 2·queue1 + queue2 ;  si prédiction inter-trame : m = (m + 3·pm + 1) >> 1
nc = {0,1,2,3,3,4,4,4,4}[m] si m < 9, sinon 5
s = M(coef, 6·ac + nc)
si s < 15 : u = s
sinon     : k = M(cesc, ac) ;  u = 15 + 2^k − 1 + R(k)      (R(0) = 0)
si t pair : |k| = 2u ;      signe lu (R(1) = 1 : négatif) seulement si u > 0
si t impair : |k| = 2u + 1 ; signe toujours lu
t = état suivant après le niveau k (tables ci-dessus)
X = k · (Δ/2) · rms_b ;  queue2 = queue1 ;  queue1 = u
```

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
