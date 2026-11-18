# MULE : proposition pour la combinaison A

Ce document précise la combinaison A de `CODEC-DESIGN-NOTES.md` §5 : transformée façon Tremor, énergies par bande, forme normalisée quantifiée en scalaire, codage entropique adaptatif et allocation explicite. Le développement se fait d'abord sur PC. Le portage sur Cortex-M3 (Echo Mini) viendra ensuite.

## 0. Contraintes confirmées

- Le DAC de l'Echo Mini accepte le **44,1 kHz nativement**. Aucun rééchantillonnage n'est nécessaire.
- **Le CPU n'est pas le facteur limitant**, puisque le FLAC 24 bits/192 kHz passe sans problème (environ 10 M MAC/s). La **RAM** reste à surveiller.
- Le firmware a déjà un **parseur Ogg** (`echo-mini-newfw/fw/hifi/oggpage.c`). MULE sera encapsulé dans Ogg (voir §9).
- L'encodeur est écrit en Python + NumPy, en s'appuyant sur des bibliothèques rapides quand elles existent.

## 1. Principes directeurs

1. **Le format est le contrat.** On écrit une spécification (`spec/FORMAT.md`) et un décodeur C de référence. L'encodeur peut changer librement tant qu'il produit des flux valides.
2. **L'état du décodeur se déduit uniquement d'entiers décodés.** Les contextes, les prédictions et l'adaptation des modèles ne lisent jamais une valeur flottante reconstruite. Un décodeur flottant et un décodeur en virgule fixe lisent donc le même flux de façon identique, et seul le PCM de sortie diffère de quelques LSB.
3. **Les modules sont séparés** : transformée, énergie, forme normalisée, codage entropique. La TCQ (B) ou la PVQ (C) ne remplaceront que le quantificateur.
4. **Le décodeur reste compatible avec la virgule fixe** : pas de fonction transcendante par coefficient, seulement une `exp2` et une `rsqrt` par bande, qui deviendront des tables.

## 2. Organisation du code

| Couche | Langage | Rôle |
|---|---|---|
| `core/` | C99, sans allocation dynamique | rANS, modèles adaptatifs, syntaxe, déquantification, IMDCT, décodeur. C'est le code qui ira sur la cible. |
| `py/mule/` | Python + NumPy/SciPy | Analyse, psychoacoustique, allocation, RDO, décisions de l'encodeur |
| liaison | cffi | L'encodeur appelle **le même** code C pour les modèles et le rANS, ce qui évite toute divergence |
| `eval/` | Python + outils externes | Corpus, codecs de référence, métriques, rapports |

```
mule-audio/
  spec/FORMAT.md
  core/    rans.[ch] model.[ch] bands.[ch] mdct.[ch] dequant.[ch] decoder.[ch] ogg.[ch]
  tools/   mule-dec (→ WAV), mule-info
  py/mule/ mdct.py transient.py psy.py alloc.py quant.py stereo.py encoder.py
  eval/    corpus.py refcodecs.py metrics.py run_eval.py
  tests/
```

Garde-fous de complexité utilisables dès le PC :
- compiler `core/` avec `arm-none-eabi-gcc -mcpu=cortex-m3 -Os` et suivre `size` (.text/.rodata) ;
- exécuter le décodeur sous QEMU `mps2-an385` (Cortex-M3 émulé) et y compter les instructions. Tremor y servira de référence.

## 3. Transformée

- MDCT de **2048 (long) / 256 (court)**, recouvrement complet, **fenêtre Vorbis** `sin(π/2·sin²(·))`.
- **Trame fixe de 1024 échantillons** (23,2 ms à 44,1 kHz), qui contient soit 1 bloc long, soit **8 blocs courts** (comme en AAC).
- Transitions long/court à la manière de Vorbis : chaque demi-fenêtre prend la pente du voisin, sans bloc start/stop explicite.
- **Regroupement des blocs courts** : un masque de 7 bits indique où commence chaque groupe. Énergies et allocation sont données par (groupe, bande). **Mesure P1** (`eval/results/P1-BLOCKS.md`) : avec une seule énergie pour les 8 fenêtres, à la manière de CELT, la commutation ne supprime presque pas le pré-écho (9 % des attaques restent audibles, contre 1,3 % avec 8 groupes). Le regroupement est donc indispensable dès la v1. L'encodeur fusionne les fenêtres d'énergie voisine, et au minimum coupe le groupe au niveau de l'attaque.
- Toutes les tailles de transformée sont des **puissances de 2** : l'appareil a des accélérateurs MDCT matériels pour 2048, 1024, 512 et 256. Ils serviront au portage.
- Détecteur de transitoires : rapport d'énergie haute fréquence sur des sous-blocs de 128 échantillons.
- L'IMDCT passe par une FFT complexe de N/4 : 256 points en long (4⁴, radix-4) et 32 points en court.
- La fréquence de coupure est l'indice `B_max` (en-tête, modifiable par trame).
- À étudier plus tard : `tf_change` par bande (Haar sur les blocs courts).

## 4. Grille de bandes

On reprend la grille de CELT exprimée en **unités de 8 bins** (172 Hz à 44,1 kHz) :

```
bords (unités) : 0 1 2 3 4 5 6 7 8 10 12 14 16 20 24 28 34 40 48 60 78 100 116
→ 22 bandes jusqu'à 20 kHz ; largeurs en long : 8×8, 16×4, 32×3, 48, 48, 64, 96, 144, 176, 128 bins
```

En bloc court, une unité vaut 1 bin par fenêtre. Une bande compte donc **le même nombre de coefficients en long et en court**, et les tables d'allocation et de modèles sont partagées. Il faudra mesurer s'il vaut la peine de scinder les bandes au-dessus de 8 kHz.

## 5. Énergies

- Valeur codée : `L_b = log2(rms par coefficient)`, une par bande, par canal et par groupe.
- **Un seul étage, pas de 1,5 dB** : `Q_b = round(4·L_b)`. Un bit de raffinement, déduit de l'allocation, ne sera ajouté que si les mesures le justifient.
- **Prédiction en entiers** : `pred_b = (α·Q_prev[b] + (32−α)·Q[b−1]) >> 5`. L'encodeur choisit α pour chaque trame parmi {0, 16, 26, 31} (2 bits). α = 0 est imposé dans les paquets clés.
- Le résidu est codé par un modèle adaptatif, avec pour contexte la classe de bande × min(|r_{b−1}|, 2).
- Coût estimé : environ 5 kb/s.

## 6. Allocation explicite et quantification de la forme

> **Depuis le format v2 (P4, 17/11/2026), la forme est quantifiée par TCQ** (combinaison B de `CODEC-DESIGN-NOTES.md`), et non plus en scalaire : voir `spec/FORMAT.md` §5.3 et `docs/VARIANTS-BC.md`. Ce qui suit décrit la conception d'origine (v1).

- `a_b` ∈ [0, ~40] par bande, codé en différence d'une bande à la suivante.
- Forme normalisée à un rms de 1 : `x = X / rms_q`. Pas de quantification : `Δ_b = 2^((A0 − a_b)/4)`. Chaque +4 sur `a_b` donne +6 dB de SNR, soit environ 1 bit par coefficient.
- `a_b = 0` : la bande n'est pas codée (bruit ou repliement).
- Quantification `y = Q(x/Δ_b)`, entièrement à la main de l'encodeur (zone morte, RDOQ).
- Optimisation à étudier plus tard : prédire `a_b` à partir d'un masque grossier calculé sur les énergies décodées, et ne transmettre que la correction.

**Reconstruction au décodeur.** Ce point a été **révisé par la mesure en P2** (`eval/results/P2-ESTIMATE.md`) :
1. bande codée (`a_b > 0`) : `X̂ = y·Δ_b·rms_q`, **sans bruit sur les zéros et sans renormalisation**. La conservation de l'énergie (remplissage plafonné à `nf·Δ²`, puis renormalisation) prévue au départ coûtait environ 0,2 d'ODG PEAQ sur les sons tonals : le bruit injecté entre les partiels s'entend. Le décodeur y gagne aussi, puisqu'il n'a plus de `rsqrt` par bande ;
2. bande avec `a_b = 0` : bruit (LCG) à l'énergie `rms_q`. Le repliement depuis une bande inférieure reste à évaluer ;
3. côté encodeur, la zone morte retenue est de **0,1**. Une valeur de 0,2 ne convient qu'avec le remplissage par bruit.

## 7. Codage entropique

- **rANS sur 32 bits**, mots de 16 bits, probabilités sur 15 bits. Le décodage n'utilise **aucune division**.
- Le paquet est entièrement en RAM (§9). L'encodeur calcule les probabilités dans l'ordre (même code C que le décodeur), puis code le paquet à l'envers. L'état rANS est vidé à chaque paquet, soit 4 octets par paquet.
- **Modèles CDF adaptatifs** façon AV1 : `cdf += (cible − cdf) >> taux`, avec un taux qui croît après chaque réinitialisation. Alphabets de 16 symboles au plus.
- **Coefficients** : |y| est codé sur l'alphabet {0…14, ESC}, suivi d'un Exp-Golomb à préfixe adaptatif en cas d'échappement. Le signe est codé à p = ½.
- **Contexte façon Duda (σ prédit)** : `classe = T[a_b][min(2|y_{k−1}| + |y_{k−2}|, 15)]`. T est une table ROM d'environ 640 octets. Il y a 16 classes, soit environ 512 octets de RAM par type de canal.
- Les **CDF initiales sont entraînées** sur le corpus (environ 1 à 2 Kio de ROM).
- Expériences prévues en P4 : contexte inter-trame (|y| de la trame précédente, mis à l'échelle en entiers), EPD avec κ ≈ 0,5, alphabet plus grand.
- Le codeur est caché derrière une interface. On peut le remplacer par un range coder façon `od_ec` (AV1) sans toucher aux modèles, notamment à cause du brevet Microsoft sur une variante du rANS adaptatif.

## 8. Stéréo par bande

- v1 : un drapeau L/R ou M/S par bande, plus `B_int`, l'indice de début de l'intensity. Au-dessus, on ne code que la forme de M, avec les énergies de L et de R.
- v2 : une rotation θ par bande, qui généralise M/S.

## 9. Encapsulation Ogg

Ce choix découle du parseur `oggpage.c` du firmware :
- `pg_packet()` recopie **un paquet entier** dans un tampon statique. Le tampon Opus fait 8 Kio, et un paquet trop long est rejeté.
- Pour le seek, le cœur A cherche une page dont la granule est ≤ cible − 1 s, puis le cœur B y saute et décode en jetant ce qu'il décode jusqu'à connaître sa position.
- Les tags sont lus par le cœur A (`tags.c`), qui reconnaît le format `OpusTags`.

Mise en paquets :
- `MULEHead` : signature de 8 octets, version, canaux, fs, pre_skip, B_max ;
- `MULETags` : **même format qu'`OpusTags`** (signature, vendor, commentaires, `METADATA_BLOCK_PICTURE` en option) ;
- paquets audio : **4 trames (≈ 93 ms) par paquet**, avec un **plafond strict de 8 Kio** que l'encodeur garantit (il découpe en cas de besoin). La granule est la position en échantillons, et `pre_skip` + granule de fin assurent la lecture sans blanc, comme en Opus.
- **Paquet clé environ toutes les 0,93 s** (≤ 10 paquets) : modèles réinitialisés, α = 0, drapeau dans le premier octet et position de 4 octets en échantillons. Après un saut, le décodeur jette les paquets jusqu'au premier paquet clé, puis la première trame de celui-ci (pré-roll de la MDCT). L'intervalle de moins de 1 s est compatible avec le saut « ≤ cible − 1 s » du cœur A.

Changements à prévoir dans le firmware au moment du portage : un `HP_CODEC_MULE`, la détection (`player.c:281`), la signature des tags (`tags.c:602`), et l'ajout de MULE aux conditions Opus/Vorbis de `player.c:749` et `:757`. `oggpage.c` ne change pas.

## 10. Syntaxe d'une trame, dans l'ordre de décodage

```
[premier octet du paquet : drapeau clé, nombre de trames ; si clé : position u32]
par trame :
  type de bloc (long/court) [+ masque de groupes]
  α, nf, drapeau repli/bruit
  stéréo : drapeaux M/S par bande, B_int
  énergies Q[c][g][b]       (résidus prédits)
  allocation a[c][g][b]     (en différence)
  coefficients y            (bande par bande ; balayage en court à valider)
```

## 11. Encodeur

1. Psychoacoustique v1 : énergies par bande, fonction d'étalement, tonalité, seuil absolu. On obtient un masque M_b.
2. Allocation : bruit ≈ M_b × f(qualité). C'est un VBR par qualité, avec la seule contrainte d'un paquet ≤ 8 Kio.
3. RDOQ sur y, puis recherche locale sur `a_b` en minimisant D + λR, avec R calculé par les vrais modèles.
4. Décisions de stéréo, de blocs courts, de groupes, de α et de nf par essais.
5. Vérification miroir : l'encodeur fait tourner le décodeur C sur sa sortie et compare avec la reconstruction qu'il attend.

## 12. Budget estimé du décodeur

| Poste | Estimation |
|---|---|
| RAM | recouvrement (8 Kio) + spectre (8 Kio) + FFT (2 Kio) + modèles (~2 Kio) + PCM (4 Kio) + paquet (8 Kio) ≈ **30 Kio** |
| ROM données | fenêtres, twiddles, table T, CDF initiales ≈ **5 Kio** |
| Code | **< 20 Kio** visés |
| CPU | IMDCT ≈ 2 Mcycles/s + entropie ≈ 5 Mcycles/s, du même ordre que le FLAC 24/192 |

## 13. Phases

| Phase | Contenu | Critère de sortie |
|---|---|---|
| **P0** | Corpus, codecs de référence (Vorbis, Opus), métriques (ViSQOL, PEAQ, NMR), `run_eval.py` | Tableau débit/qualité reproductible pour les références |
| **P1** | MDCT, fenêtres, commutation de blocs, transitoires (Python) | Reconstruction parfaite < 1e-6, pas de pré-écho avec une quantification fictive |
| **P2** | Énergies, allocation, scalaire, bruit/repliement, débit **estimé** par −log₂p avec les modèles adaptatifs simulés | **G1** : à qualité égale, débit estimé ≤ Vorbis q4 + 10 %. Mesure du coût de la réinitialisation des modèles. **Atteint** : 124 kb/s pour la qualité de Vorbis à 128 (PEAQ) ; réinitialisation 2,4 %, ramenée sous 1 % par les CDF entraînées |
| **P3** | `FORMAT.md` v0, `core/` en C, cffi, vrais fichiers Ogg | Aller-retour exact, rANS testé par fuzzing, vecteurs de référence, vérification miroir. **Fait** : décodeur C = encodeur à 1e-8 près, débit réel = estimation, seek et lecture sans blanc vérifiés (`eval/results/P3-BITSTREAM.md`) |
| **P4** | Stéréo, RDOQ, psychoacoustique v2, échelle de qualité, expériences de contexte | Courbes débit/qualité pour chaque expérience |
| **P5** | Comparaison formelle à 128 et 160 kb/s : métriques, puis ABX | **G2** : ≥ Vorbis à débit égal. Sinon on passe au quantificateur B (TCQ). |
| **P6** | Décodeur en virgule fixe sur PC, QEMU M3, taille du code, RAM | Rapport de budget, puis portage sur la cible |

## 14. Risques

- **Bandes peu remplies** : la renormalisation a été abandonnée en P2 (voir §6). Le point faible mesuré est désormais celui des sons tonals clairsemés (triangles, glockenspiel), d'environ −0,3 d'ODG face à Vorbis.
- **Réinitialisation des modèles toutes les 0,93 s** : son coût sera mesuré en P2. Les CDF initiales entraînées le compensent.
- **Blocs courts et regroupement** : c'est la partie la plus complexe de la syntaxe. Le regroupement est indispensable (P1). Il reste à mesurer en P2 ce que coûtent les énergies supplémentaires, puisqu'environ 4 % des trames sont courtes.
- **Paquets ≤ 8 Kio** : les transitoires à haut débit peuvent forcer à découper un paquet. L'encodeur gère ce cas, le décodeur n'a rien de spécial à faire.
