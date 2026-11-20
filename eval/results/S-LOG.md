# Répartition des coefficients avant quantification (20/11/2026)

`eval/coef_stats.py` : trace de l'encodeur (format v3, réglages par défaut, q −7) sur les
66 extraits de `dev`, 52,5 millions de coefficients codés (97 % en trames longues). Valeurs
avant quantification en unités du pas D (les niveaux de la TCQ sont au pas D/2). Le script
n'écrit rien ; chaque extrait est analysé à part (une première version, qui concaténait tout,
a été tuée par manque de mémoire).

## 1. Forme de la distribution

β : forme de la gaussienne généralisée ajustée par les moments (1 = laplacienne, 2 = gaussienne,
moins de 1 = queue plus lourde).

| Classe d'allocation | Part des coefficients | rms | kurtosis | β |
|---|---|---|---|---|
| 1 à 2 | 42,8 % | 0,67 D | 5,97 | 1,11 |
| 3 à 5 | 47,9 % | 1,84 D | 16,1 | 0,71 |
| 6 à 8 | 4,9 % | 8,45 D | 34,1 | 0,38 |
| 9 à 11 | 0,2 % | 28,6 D | 14,9 | 0,32 |

Les classes basses sont laplaciennes (kurtosis 5,97 pour 6 en théorie) : le modèle du
simulateur (`tcq_sim.py`, `tcq_rules_sim.py`) leur convient. Les classes 3 à 5, près de la moitié
des coefficients, ont une queue nettement plus lourde, et les classes hautes (bandes bien
dotées, sons tonals) bien plus encore : quelques pics au milieu de valeurs proches de zéro. Le
mélange de toutes les classes n'a pas de sens (β 0,29).

## 2. Petites valeurs

- |x| < D/4 : 29,9 % ; < D/2 : 50,4 % ; < D : 73,1 % ; < 2D : 89,5 %.
- Niveaux nuls : 35,2 % ; niveaux impairs (règle impaire, signe toujours écrit) : 45,1 %.
- Signes écrits : 64,8 % des coefficients.
- Niveau du Viterbi qui n'est pas le plus proche de sa règle (choix guidé par le débit) : 5,6 %,
  dont 62,4 % vers zéro : une zone morte décidée au cas par cas.

## 3. Signes

| | |
|---|---|
| P(+) | 0,5000 |
| même signe que la raie précédente (même bande, les deux non nuls) | 0,491 |
| même signe que la même raie à la trame longue précédente | 0,499 |
| H(signe \| raie précédente, trame précédente) | 0,9998 bit (|x| ≥ 2D : 0,9996) |

Un contexte de signe économiserait 0,02 % des bits de signe, soit moins de 0,01 % du flux. Les
signes valent un bit brut chacun : **piste fermée**. La légère anti-corrélation entre raies
voisines vue sur trois extraits (0,472, trompette surtout : une sinusoïde alterne les signes de
ses raies voisines dans la MDCT) se dilue sur le corpus.

## 4. Voisins

- Corrélation de rang des amplitudes |x| : 0,395 avec la raie précédente, 0,385 avec la même raie
  à la trame précédente (échantillons de 1,3 million de paires) ; corrélation des valeurs signées
  d'une trame à l'autre : −0,03.
- Les amplitudes se ressemblent, les signes non : c'est exactement ce qu'exploitent les contextes
  du codeur entropique (deux raies précédentes, terme inter-trame), qui valent environ 13 %.

## Conclusions

- **Confortés** : le signe en bit brut ; les contextes d'amplitude ; la zone morte implicite du
  Viterbi (λ).
- **Fermé** : la prédiction ou la compression des signes.
- **À corriger dans les simulateurs** : ils tirent des laplaciennes, ce qui ne représente que les
  classes basses. Une source en gaussienne généralisée de β ≈ 0,7 (et un mélange selon la classe)
  rendrait leurs prédictions (nombre d'états, nombre de règles) plus fidèles au codec ; les
  ordres de grandeur ne devraient pas changer.

## Les simulateurs du treillis avec une source de forme β 0,7

`tcq_sim.py` et `tcq_rules_sim.py` ont une option `--beta` (0,7 par défaut ; 1 redonne le tirage
laplacien de `B-LOG.md`). Gain d'erreur sur le scalaire à entropie égale (dB), β 1 → β 0,7 :

| | 1,25 bit | 2,0 bits |
|---|---|---|
| 8 états, redémarré (v2) | −0,05 → −0,64 | +0,68 → +0,27 |
| 8 états, chaîne | +0,04 → −0,61 | +0,82 → +0,39 |
| 8 états, chaîne naïve | −0,14 → −0,83 | +0,67 → +0,24 |
| 32 états, chaîne | +0,17 → −0,52 | +0,95 → +0,54 |
| 64 états, chaîne | +0,23 → −0,49 | +1,01 → +0,59 |
| 4 règles, 64 états, chaîne | +0,23 → −0,46 | +0,99 → +0,59 |

- **Le classement ne change pas** : la chaîne bat le redémarrage, la chaîne naïve reste la pire,
  le gain monte avec le nombre d'états ; quatre règles gagnent un peu plus qu'avec β 1 (+0,03 à
  +0,08 dB sur deux règles à 1,25 bit, rien à 2 bits), toujours loin du seuil.
- **Le niveau absolu s'effondre** : avec une source à queue lourde, la TCQ du simulateur perd
  0,5 à 0,65 dB sur le scalaire à 1,25 bit. Cause probable : le Viterbi du simulateur ne minimise
  que l'erreur (λ = 0), sans terme de débit. Sur une source où la moitié des valeurs sont
  presque nulles, il se place sur la règle impaire, sans zéro, et paie un signe et un niveau non
  nul pour des valeurs qui n'en valaient pas la peine. Dans le codec, le Viterbi compte les bits
  (λ 0,3 ; λ 0 y coûtait déjà 4,8 % de débit) et la TCQ gagne (+0,06 d'ODG, environ 0,4 dB de SNR
  à débit égal). Le simulateur sous-estime donc la TCQ réelle, d'autant plus que la source est
  piquée : ses écarts entre variantes restent utilisables, pas ses niveaux absolus.
- Pour un simulateur fidèle, il faudrait un Viterbi avec terme de débit (coût de chaque index
  selon un modèle d'entropie), comme dans le codec.
