# Variantes B (ECTCQ) et C (PVQ améliorée)

Dans `CODEC-DESIGN-NOTES.md` §5, B et C **ne remplacent que le quantificateur de la forme normalisée** de A. La transformée, la commutation de blocs, les énergies, l'allocation, la stéréo, la psychoacoustique et le codage entropique adaptatif restent ceux de A (réglages P4). La comparaison se fait donc à chaîne identique.

## 1. Faisabilité en Python (`py/mule/quant_bc.py`, `eval/bc_feas.py`)

Protocole : l'encodeur Python en mode estimation (reconstruction selon les règles du décodeur, débit donné par les vrais modèles adaptatifs). 4 extraits de 4 s (abba, orgue, castagnettes, violon), réglages q −6, −9 et −12. On compare le NMR et le SNR à **débit égal** avec A, par interpolation sur la courbe débit/qualité de chaque extrait.

### B : TCQ à 8 états (treillis de JPEG 2000 partie 2), codée par entropie

- Niveaux `k·δ`, avec `δ = tcq_scale·Δ` (0,5 par défaut) ; sous-ensembles `D_j = {k ≡ j mod 4}`.
- Les états pairs utilisent `D0 ∪ D2` (k pair), les états impairs `D1 ∪ D3` (k impair, jamais 0). Le sous-ensemble choisi détermine l'état suivant.
- Le Viterbi minimise `(x − k)² + λ·R(k)`, avec λ = `tcq_lam` = 0,6 et un R statique approché.
- Index transmis : `m = |k|/2` (union paire) ou `(|k|−1)/2` (union impaire), codé avec les modèles et contextes de A. Le signe est toujours envoyé dans l'union impaire. Le décodeur suit l'état à partir des niveaux décodés.

| Extrait | ΔNMR (dB, négatif = mieux) | ΔSNR (dB) |
|---|---|---|
| abba | −0,39 | +0,67 |
| castagnettes | −0,65 | +0,24 |
| orgue | −0,34 | +0,70 |
| violon | −0,36 | +0,04 |
| **moyenne** | **−0,44** | **+0,41** |

**Faisable et prometteur.** Le gain est régulier sur les quatre extraits. Il est inférieur au gain de granularité théorique (environ 1 dB à haut débit), ce qui est cohérent à nos débits, avec beaucoup de petits niveaux. En Python, B est 16 fois plus lent que A : il sera porté en C.

### C : PVQ, θ récursif, projection de Duda, index non uniforme

- K impulsions : `K = round(0,8·n·kscale/Δ)`, déduit de l'allocation, donc sans information supplémentaire.
- Recherche PVQ gloutonne. Les bandes de plus de `pvq_split` (16) coefficients sont découpées récursivement en deux par un angle θ, à la manière de CELT, qui fixe la répartition de l'énergie et des impulsions. θ est envoyé en bits bruts (au plus 16 niveaux).
- Projection de Duda : le décodeur reconstruit `sign(y)|y|^p` normalisé, et l'encodeur cherche sur `sign(x)|x|^(1/p)`.
- Le vecteur d'impulsions est codé avec les modèles adaptatifs de A (« index non uniforme »). On n'exploite pas la contrainte Σ|y| = K, ce qui donne un léger surcoût. La reconstruction conserve l'énergie.

| Variante | ΔNMR (dB) | ΔSNR (dB) |
|---|---|---|
| C (p = 1, split 16) | +2,57 | −2,99 |
| C, kscale 0,7 | +3,66 | −4,38 |
| **C, sans découpage** | **+1,34** | −2,25 |
| C, p = 0,75 | +3,88 | −4,31 |
| C, p = 1,25 | +3,00 | −3,45 |

**Nettement moins bon que A** dans cette version, de +1,3 à +3,9 dB de NMR à débit égal :

- le découpage récursif coûte, car θ part en bits bruts et les impulsions sont mal réparties entre les moitiés ;
- la projection de Duda dégrade les résultats, que p soit inférieur ou supérieur à 1 ;
- causes probables, à vérifier en C :
  - la conservation de l'énergie, déjà pénalisée en P2 pour le scalaire : sur les bandes peu remplies, l'énergie se concentre sur quelques impulsions ;
  - le codage des impulsions, qui n'exploite pas K ;
  - la correspondance entre K et l'allocation.

Le portage en C servira à explorer davantage de réglages (correspondance de K, découpage, codage de θ), mais l'écart de départ est important.

## 2. Portage en C (variantes expérimentales du flux)

`MULEHead`, octet 18 : bits 0–3 = trames par paquet (indicatif) ; **bits 4–5 = quantificateur expérimental** (0 = A scalaire, 1 = B TCQ, 2 = C PVQ). Le décodeur de référence lit les trois. Seul A correspond à la spécification normative `spec/FORMAT.md` v1.

Encodeur : `Params.quant` (`"tcq"`, `"pvq"`), `tcq_lam`, `pvq_split`, qui correspondent aux champs `quant`, `tcq_lam` et `pvq_split` de `mule_enc_params`. Décodeur : `core/dec.c` lit l'octet 18. Tests d'aller-retour : `tests/test_variants_bc.py`. Évaluation : variantes `mule-B…` et `mule-C…` de `eval/refcodecs.py`.

### Portage C de C : la contrainte Σ|y| = K est exploitée

Après la dernière impulsion, les coefficients restants sont implicitement nuls, et le dernier coefficient prend le reste (rien n'est codé pour eux). θ part en bits bruts, et une feuille avec K = 0 n'a aucun coefficient. `kscale` est redondant avec le réglage de qualité (doubler K revient à ajouter 4 à a) : il est fixé à 1.

## 3. Évaluation sur le jeu `dev` (`eval/results/bc_dev.csv`, 66 extraits, PEAQ + NMR, réf. = A après P4)

| Variante | ODG @128 | ODG @160 | ODG avancé @128 | @160 | NMR @128 | Débit à réglage égal | Extraits < −0,05 |
|---|---|---|---|---|---|---|---|
| B (λ 0,6) | −0,008 | −0,016 | +0,042 | +0,019 | +0,52 | −3,4 % | 8 (violon −0,14, triangles −0,11…) |
| **B λ 0,3** | **+0,042** [+0,030, +0,052] | +0,001 | **+0,035** | **+0,025** | **+0,47** | −0,4 % | **1** (triangles −0,13) |
| B λ 1,0 | −0,089 | −0,077 | +0,008 | −0,007 | +0,21 | −4,8 % | 59 |
| B sans allocation optimisée | −0,019 | −0,023 | +0,002 | 0,000 | +0,27 | +2,7 % | 5 |
| C (sans découpage) | −0,003 | −0,027 | −0,044 | −0,041 | −0,82 | +11,5 % | 12 (triangles −0,64, glockenspiel −0,43, orgue −0,26) |
| C, découpage 32 | −0,028 | −0,053 | −0,073 | −0,063 | −1,10 | +12,7 % | 19 |
| C, découpage 16 | n.d. | −0,085 | n.d. | −0,089 | −1,78 | +14,1 % | 35 |

Valeurs absolues à débit égal (`run_eval.at_rates`) :

| | ODG @128 | ODG @160 | ODG avancé @128 | @160 |
|---|---|---|---|---|
| A | −0,329 | −0,122 | −0,392 | −0,154 |
| B λ 0,3 | **−0,287** | −0,121 | −0,357 | **−0,129** |
| C | −0,332 | −0,148 | −0,436 | −0,195 |

**Lecture** :
- **B est meilleur que A à λ faible.** Plus λ est petit, plus la quantification est fine, et mieux c'est : un λ élevé fait sauter des niveaux, ce que PEAQ pénalise sur les sons tonals, exactement comme pour la zone morte de A en P2. Un balayage plus fin de λ est en cours.
- B profite de l'allocation optimisée de A : sans elle, il est moins bon.
- **C reste en dessous de A**, et le découpage récursif l'aggrave. Le problème est surtout tonal (triangles, glockenspiel, orgue) : la conservation d'énergie concentre l'énergie des bandes clairsemées sur quelques impulsions, et la correspondance entre K et l'allocation dépense trop. Quelques extraits orchestraux denses profitent de C (joy_division +0,09, quatuor +0,09, Beethoven +0,07).

### Balayage de λ pour B (`bc_dev2.csv`, jeu `dev`, réf. = A)

| λ | ODG @128 | ODG @160 | ODG avancé @128 / @160 | NMR @128 / @160 | Débit | Régressions |
|---|---|---|---|---|---|---|
| 0 (TCQ pure, sans terme de débit) | +0,018 | −0,027 | −0,006 / +0,006 | +0,01 / +0,25 | +4,8 % | 15 |
| 0,15 | +0,046 | −0,009 | +0,021 / +0,019 | +0,31 / +0,47 | +2,0 % | 3 |
| **0,3** | **+0,042** | **+0,001** | **+0,035 / +0,025** | **+0,47 / +0,59** | −0,4 % | **1** (triangles −0,13) |
| 0,45 | +0,020 | −0,001 | +0,041 / +0,026 | +0,54 / +0,61 | −2,2 % | 4 |
| 0,6 | −0,008 | −0,016 | +0,042 / +0,019 | +0,52 / +0,55 | −3,4 % | 8 |
| 1,0 | −0,089 | −0,077 | +0,008 / −0,007 | +0,21 / +0,17 | −4,8 % | 59 |

L'optimum se situe à **λ ≈ 0,3**.

## 4. Validation de B (λ 0,3) sur le jeu `test` (`bc_test.csv`, 30 extraits non vus, avec ViSQOL)

| B contre A | @128 | @160 |
|---|---|---|
| ODG de base | **+0,063** [+0,051, +0,080] | **+0,037** [+0,025, +0,048] |
| ODG avancé | +0,056 [+0,047, +0,066] | +0,036 [+0,031, +0,041] |
| ViSQOL | +0,005 | +0,005 |
| NMR | +0,45 dB | +0,57 dB |

Débit à réglage égal : −0,4 %. **Aucune régression.**

Valeurs absolues à débit égal sur `test` :

| | ODG @128 | ODG @160 | ODG avancé @128 | @160 | ViSQOL @128 | NMR @160 |
|---|---|---|---|---|---|---|
| Vorbis | −0,449 | −0,164 | −0,631 | −0,339 | 4,474 | −3,01 |
| Opus | **−0,118** | **0,000** | −0,446 | −0,241 | 4,539 | −4,30 |
| A (MULE après P4) | −0,299 | −0,090 | −0,481 | −0,203 | 4,601 | −5,72 |
| **B (TCQ λ 0,3)** | −0,236 | −0,053 | **−0,425** | **−0,168** | **4,606** | **−6,29** |

## 5. Conclusions et décisions à prendre

- **B est meilleur que A**, sur `dev` comme sur `test`, avec toutes les métriques et sans régression sur `test`. Il réduit d'environ un tiers l'écart avec Opus en ODG de base, et dépasse Opus en ODG avancé, ViSQOL et NMR.
- **Coût pour le décodeur** (sur le M3) : par coefficient, une machine à 8 états (une table de 16 entrées), le calcul de la parité et un décalage d'un bit. C'est négligeable. Le pas de reconstruction devient D/2. Rien d'autre ne change : contextes, modèles et syntaxe sont identiques à A.
- **Coût pour l'encodeur** : un Viterbi à 8 états par bande, soit environ 2 fois le temps de A, qui reste très au-dessus du temps réel.
- **Décision qui te revient** : adopter B comme format v2. Ce serait un changement de format : le décodeur v1 ne lit pas B. Il faudrait alors réentraîner les CDF sur B (identifiant de table 2), puisque les statistiques des index TCQ diffèrent un peu, et repasser l'ABX.
- **C (PVQ) n'est pas retenu en l'état.** Il est moins bon que A, surtout sur les sons tonals. Pistes, si tu veux le reprendre : correspondance K(a) dépendant de la tonalité, pas de conservation d'énergie sur les bandes clairsemées (ou « spreading » à la CELT), θ codé de façon adaptative.

Pour reproduire :
- `VISQOL= .venv/bin/python eval/run_eval.py --set dev mule_-6 … mule-Bl03_-6 …` ;
- `eval/p4_compare.py results.csv --base mule --vs mule-Bl03`.

Variantes : `eval/refcodecs.py` (`B`, `Bl0`, `Bl015`, `Bl03`, `Bl045`, `Bl10`, `Brd0`, `C`, `C32`, `C16`).

## 6. Décision (17/11/2026) : B devient l'unique quantificateur du format v2

Décision prise après l'écoute ABX : B à 160 kb/s est transparent sur les 6 extraits critiques ; A l'est sur 5, les triangles étant au seuil.

Ce qui a été fait :
- `spec/FORMAT.md` **v2** : TCQ normative (§5.3), version 2, table de CDF 2.
- `core/enc.c` et `core/dec.c` : la TCQ est le seul chemin. Le scalaire (A) et la PVQ (C) sont retirés du code de production (ils restent dans l'historique git, commit `879cc59`).
- `py/mule/encoder.py` : `quant = "tcq"` par défaut. Le Viterbi vectorisé de `quant_bc.tcq` prend **les mêmes décisions** que le C (même départage des égalités). `tests/test_cenc.py` vérifie que les opérations sont identiques. `"scalar"` et `"pvq"` restent des prototypes d'estimation, sans flux binaire.
- **CDF de la table 2** entraînées sur `data/train` (200 extraits) à partir des opérations de l'encodeur C de production (`eval/train_cdf.py`) : −0,10 % de débit sur `dev` par rapport à la table 1.
- Bilan sur `test` (`eval/results/v2_test.csv`) : ODG −0,234 @128 / −0,053 @160, ODG avancé −0,425 / −0,168, ViSQOL 4,607 / 4,634, NMR −3,17 / −6,29 (identique à B avec la table 1, à 0,002 près).
