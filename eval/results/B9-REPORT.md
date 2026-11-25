# Nuit du 24 au 25/11/2026 : réglages par débit (CMA-ES) et pentes face à Zimtohrli

Résumé : **rien à adopter tel quel.** Les réglages trouvés par CMA-ES ne tiennent pas hors de leur
corpus de recherche, sauf peut-être à 96 kb/s (Zimtohrli +2 à 3 %, PEAQ et NMR un peu moins
bons : désaccord, donc ABX). La mesure des pentes montre un écart réel entre notre modèle et
Zimtohrli (7 à 11 % de distance en jeu), mais le gain va dans le sens où Zimtohrli diverge de
PEAQ et de NMR : retirer des bits au-dessus de 13 kHz.

Juges : Zimtohrli (distance x 10^4, plus bas = mieux), PEAQ basique et avancé (ODG), NMR (dB,
plus bas = mieux). Pas de ViSQOL. Production = `--bitrate` (C75 : `opa_mode` 3, `opa_alpha` 0,75,
`rc_k` 2, `rc_max` 15).

## 1. Les recherches CMA-ES (`eval/m6_tune.py --space b9`)

Objectif Zimtohrli sur la moitié paire de `dev` (33 extraits), débit encadré R ± 6,25 %,
population 10, 13 générations, 9 réglages. Fichiers : `m6_search_b9_{96,128,160}.csv`,
`m6_best_b9_{96,128,160}.json`.

| réglage | production | 96 kb/s | 128 kb/s | 160 kb/s |
|---|---|---|---|---|
| `tcap_db` | 15,3 | 18,4 | 14,1 | 13,9 |
| `mid_db` | 6,1 | 5,3 | 7,4 | 9,3 |
| `low_db` | 15,0 | 16,3 | 18,4 | 20,5 |
| `fft_noise_db` | 3,4 | 4,5 | 3,7 | 3,1 |
| `rd_lambda` | 2,42 | 2,67 | 2,16 | 2,13 |
| `tcq_rdl` | 0,48 | 0,60 | 0,66 | 0,65 |
| `pre_db` | 9,7 | 10,3 | 9,7 | 9,6 |
| `opa_alpha` | 0,75 | 0,67 | 0,74 | 0,63 |
| `nf_off_db` | −6,0 | −4,3 | −5,0 | −4,8 |
| Zimtohrli, recherche | | 4,783 → 4,669 (−2,4 %) | 2,102 → 2,076 (−1,2 %) | 1,071 → 1,046 (−2,3 %) |

Points communs : `tcq_rdl` plus haut et bruit de remplissage plus fort (plus de zéros, plus de
bruit). `low_db` et `mid_db` montent avec le débit.

## 2. Validation (moitié impaire de `dev`, `test`)

`eval/results/b9val_{dev,test}.csv` : production (`mule-brC75`) contre le meilleur point du
débit (`mule-brB9r<R>`, `eval/refcodecs.py`), trois points chacun autour du débit, interpolés.
Écart nouveau − production, **+ = mieux**, IC bootstrap 95 % (\* : exclut 0).

| | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|
| `dev` impair @96 | **+3,0 %** \* | −0,012 \* | 0,000 | −0,23 dB \* |
| `test` @96 | **+2,2 %** \* | −0,015 \* | −0,011 \* | −0,23 dB \* |
| `dev` impair @128 | +0,1 % | −0,025 \* | −0,010 \* | −0,13 dB \* |
| `test` @128 | −0,1 % | −0,044 \* | −0,013 \* | −0,22 dB \* |
| `dev` impair @160 | −2,2 % | −0,025 \* | −0,014 \* | −0,21 dB \* |
| `test` @160 | +1,4 % | −0,042 \* | −0,014 \* | −0,19 dB \* |

Sur `dev` impair les débits sont un peu sous la cible (point 96 légèrement extrapolé) ; sur
`test` les trois débits sont encadrés.

- 128 et 160 kb/s : Zimtohrli neutre ou incohérent, PEAQ et NMR moins bons partout. Le gain de
  la recherche était du surapprentissage sur ses 33 extraits. **Rejeté.**
- 96 kb/s : Zimtohrli confirme (+2 à 3 %, significatif sur les deux jeux), PEAQ et NMR un peu
  moins bons. Désaccord : **candidat à l'ABX**, rien de plus.

## 3. Campagne de 300 morceaux à 128 kb/s

`data/campaign/report_mule-mule_brC75-mule_brB9r128-opus-aac.md` (900 encodages de plus :
`mule-brB9r128` à 112, 128 et 144 kb/s ; production et concurrents repris de la campagne
précédente). Moyennes à débit égal :

| codec | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|
| production (brC75) | 2,606 | −0,144 | −0,323 | −3,54 |
| brB9r128 | 2,602 | −0,187 | −0,336 | −3,34 |
| Opus | 3,236 | −0,135 | −0,438 | −2,07 |

Production contre brB9r128, apparié (+ = la production meilleure) :

| juge | écart [IC 95 %] | morceaux où la production gagne |
|---|---|---|
| Zimtohrli | −0,004 [−0,014, +0,008], non significatif | 46 % |
| PEAQ basique | **+0,043** [+0,040, +0,047] | 94 % |
| PEAQ avancé | **+0,013** [+0,012, +0,014] | 94 % |
| NMR | **+0,20 dB** [+0,17, +0,23] | 81 % |

Pas de gain Zimtohrli sur 300 morceaux et une régression nette et systématique de PEAQ (94 % des
morceaux) et de NMR. Confirme le rejet à 128 kb/s.

## 4. Pentes de notre modèle face à Zimtohrli (`eval/slopes.py`)

Principe : à débit fixe (niveleur coupé), les masques de chacune des 7 régions de Zimtohrli
décalés de ±3 dB (`band_db`, nouveau réglage d'encodeur, 0 par défaut : production inchangée) ;
pente dZ/dR et courbure par région ; si notre modèle dépensait les bits comme Zimtohrli le
voudrait, toutes les pentes seraient égales. Réallocation optimale à débit constant (modèle
quadratique), vérifiée sur la moitié impaire de `dev`. Fichiers : `slopes_{96,128,160}.csv`,
`slopes_summary.json`, `slopes_check_{96,128,160}.csv`.

Pentes à 128 kb/s (dZ x 10^4 par kb/s ; plus négatif = un kb/s y rapporte plus) :

| région | 0-250 | 250-1k | 1k-2,8k | 2,8k-6k | 6k-10k | 10k-13k | 13k-20k | uniforme |
|---|---|---|---|---|---|---|---|---|
| pente | −0,255 | −0,028 | −0,078 | −0,076 | −0,078 | −0,100 | −0,036 | −0,073 |

Même forme aux trois débits : le grave (0-250 Hz, peu de bits, très courbé) et 10-13 kHz sont
sous-dotés aux yeux de Zimtohrli ; 250 Hz-1 kHz et surtout 13-20 kHz sont sur-dotés.

Réallocation proposée (kb/s déplacés) et gain :

| | 0-250 | 250-1k | 1k-13k | 13k-20k | gain prédit (`dev` pair) | mesuré (`dev` impair) |
|---|---|---|---|---|---|---|
| 96 kb/s | +0,7 | −0,7 | +7,3 | −7,3 | −14 % | **−10,8 %** |
| 128 kb/s | +0,9 | −1,5 | +4,9 | −4,3 | −7,9 % | **−7,7 %** |
| 160 kb/s | +0,8 | 0,0 | +11,3 | −12,1 | −11 % | **−3,0 %** |

Vérification (moitié impaire de `dev`, à débit égal, interpolé ; débits de mesure 82, 110 et
135 kb/s, niveleur coupé) :

| | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|
| @96 base → réalloc | 5,873 → 5,239 | −0,518 → −0,522 | −0,844 → −0,848 | −1,06 → −1,29 dB |
| @128 | 2,657 → 2,452 | −0,257 → −0,274 | −0,402 → −0,410 | −4,42 → −4,72 dB |
| @160 | 1,486 → 1,441 | −0,093 → −0,182 | −0,199 → −0,218 | −7,05 → −7,71 dB |

(NMR plus bas = mieux : la réallocation améliore aussi NMR. PEAQ baisse, peu à 96 et 128, nettement
à 160.)

Lecture :
- **L'écart entre notre modèle et Zimtohrli est réel et mesurable** : 8 à 11 % de distance à
  96-128 kb/s, prédit et retrouvé sur des extraits non vus. C'est bien plus que ce que la
  recherche CMA-ES sur nos 9 réglages trouvait (1 à 2 %) : nos réglages actuels ne savent pas
  déplacer les bits par région.
- **Le gain vient surtout de 13-20 kHz** (masques +3,4 à +6 dB, butée de ±6 dB atteinte à 96 et
  160) : Zimtohrli juge que nous y dépensons trop. C'est la zone où les juges divergent
  (« le piège des 20 kHz », billet 4) : PEAQ basique, qui en tient compte, baisse, fortement à
  160 kb/s.
- NMR s'améliore avec la réallocation (contrairement aux réglages CMA-ES) : c'est le premier
  changement qui fait gagner Zimtohrli et NMR ensemble.
- À 96 et 160 kb/s, la réallocation dépense plus à q égal (+4 à +5 kb/s) : son interpolation
  au débit de la base a un poids de 0,08, en bord d'intervalle. À reprendre avec des points
  mieux placés.

## Propositions (rien n'est adopté)

1. **ABX à 96 kb/s**, production contre `brB9r96`, sur 2 ou 3 extraits où les juges divergent le
   plus.
2. **Réallocation par région, en deux temps** :
   - sans toucher à 13-20 kHz (0-250 Hz et 1-13 kHz seulement), pour voir si PEAQ suit
     Zimtohrli et NMR quand on laisse l'aigu tranquille ;
   - puis l'aigu seul, en ABX : c'est là que l'oreille doit trancher.
   En mode `--bitrate` (niveleur actif), à débit égal, sur `dev` impair, `test` et la campagne.
3. Pas de table de réglages par débit pour l'instant : seule la tendance « `low_db` monte avec le
   débit » survit, et elle est faible.

Changements locaux non commités : `band_db[22]` (`core/mule_enc.h`, `core/enc.c`,
`py/mule/params.py`, `py/mule/native.py`, `tests/test_params.py` ; 71 tests passent),
variantes `brB9r*` (`eval/refcodecs.py`), famille `mule_brB9r128` (`eval/campaign.py`),
`eval/slopes.py`.

## 5. Réallocation sans toucher à l'aigu (25/11/2026, `brS<R>`)

Les décalages de la section 4 sur les six régions sous 13 kHz, 13-20 kHz laissé à 0
(`eval/refcodecs.py`, `brS96`, `brS128`, `brS160`), en mode `--bitrate` (niveleur actif), contre
la production, à débit égal (interpolé), **+ = mieux**, IC bootstrap 95 %. Fichiers :
`eval/results/sval_{dev,test}.csv` (production reprise de `b9val_*`).

| | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|
| `dev` impair @96 | **+5,2 %** [+1,2, +7,7] | +0,004 | −0,002 | +0,02 dB |
| `test` @96 | **+5,3 %** [+3,9, +6,4] | +0,002 | −0,006 | **+0,10 dB** |
| `dev` impair @128 | **+3,7 %** [+1,7, +7,8] | **+0,008** | −0,005 | 0,00 dB |
| `test` @128 | **+3,7 %** [+3,0, +4,5] | +0,005 | −0,002 | **+0,09 dB** |
| `dev` impair @160 | +1,9 % [−1,7, +9,3] | −0,011 | −0,006 | **+0,19 dB** |
| `test` @160 | **+5,3 %** [+4,7, +6,3] | **−0,017** | 0,000 | **+0,22 dB** |

(`dev` impair : les débits de la production sont sous la cible à 128 et 160, valeurs un peu
extrapolées ; `test` est encadré partout.)

À q égal, Zimtohrli s'améliore sur **tous** les extraits (63 sur 63 à 128 kb/s, médiane −7 à
−9 %), pour +1,5 à +3,9 % de débit ; le niveleur ne compense pas tout, d'où l'interpolation.

Lecture : sans l'aigu, **Zimtohrli et NMR gagnent ensemble, PEAQ reste neutre** à 96 et 128 kb/s
(écarts de ±0,01, sous le seuil). À 160 kb/s, PEAQ basique perd un peu (−0,017 sur `test`) :
léger désaccord. C'est le premier candidat de la série qui passe la règle d'adoption à 96 et
128 kb/s sur les deux jeux non vus. Étape suivante proposée : la campagne de 300 morceaux aux
trois débits, puis un ABX à 160 kb/s si PEAQ y reste en retrait.

## 6. Campagne de 300 morceaux, réallocation sous 13 kHz (`brS<R>`, 25/11/2026)

`data/campaign/report_mule_brC75-mule_brS96-mule_brS128-mule_brS160-opus-aac.md` (2 700
encodages, aucun échec ; chaque `brS<R>` à R − 16, R et R + 16 kb/s, comparé à son débit).
Moyennes à débit égal :

| kb/s | codec | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|---|
| 96 | production (brC75) | 5,879 | −0,347 | −0,733 | −0,12 |
| 96 | **brS96** | **5,570** | −0,345 | −0,734 | −0,21 |
| 96 | Opus | 5,843 | −0,333 | −0,834 | +0,64 |
| 128 | production | 2,606 | −0,144 | −0,323 | −3,54 |
| 128 | **brS128** | **2,484** | −0,138 | −0,324 | −3,62 |
| 128 | Opus | 3,236 | −0,135 | −0,438 | −2,07 |
| 160 | production | 1,326 | −0,009 | −0,127 | −6,66 |
| 160 | **brS160** | **1,251** | −0,029 | −0,127 | −6,88 |
| 160 | Opus | 2,142 | −0,001 | −0,236 | −3,95 |

brS contre production, apparié (+ = brS meilleur ; part des morceaux où brS gagne) :

| kb/s | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|
| 96 | **−5,3 %** (97 %) | **+0,003** (72 %) | −0,001 (49 %) | **+0,09 dB** (74 %) |
| 128 | **−4,7 %** (99 %) | **+0,005** (60 %) | **−0,001** (40 %) | **+0,08 dB** (80 %) |
| 160 | **−5,7 %** (98 %) | **−0,021** (14 %) | 0,000 (60 %) | **+0,21 dB** (100 %) |

Morceau par morceau : à 96 et 128 kb/s, aucune régression notable (Zimtohrli au pire +3,9 et
+5,7 % sur un morceau, PEAQ au pire −0,04, aucun morceau sous −0,05). À 160 kb/s, PEAQ basique
perd plus de 0,05 sur 16 morceaux (pire −0,16, c089), Zimtohrli +12 % sur un (c124).

À 96 kb/s, brS fait passer MULE devant Opus sur Zimtohrli (5,57 contre 5,84 ; MULE gagne sur
65 % des morceaux), là où la production était à égalité.

**Bilan** : à 96 et 128 kb/s, les trois juges vont dans le même sens (Zimtohrli nettement, PEAQ
et NMR un peu) : la règle d'adoption est remplie. À 160 kb/s, PEAQ basique s'y oppose
(−0,021, 86 % des morceaux) : désaccord, à trancher à l'oreille (pas de kit ABX préparé, à la
demande de l'auteur).

Les 16 morceaux où brS160 perd plus de 0,05 de PEAQ basique (pire c089, Moussorgski, −0,16) :
**10 des 11 premiers sont de la musique classique**, surtout du piano (Martin Roscoe deux fois,
Liszt, Chopin, Moussorgski, Max Richter, Harnoncourt). Leur ODG de base est entre −0,1 et −0,4 :
pas près de la saturation de PEAQ. Sur ces mêmes morceaux, PEAQ avancé ne bouge pas (±0,005),
Zimtohrli gagne 2,5 à 7 % et NMR 0,1 à 0,4 dB. Le désaccord est celui de PEAQ basique seul,
sur le piano et l'orchestre calmes (même famille que c117 Purcell et c095 Pires, campagne C75).

## 7. L'aigu (13-20 kHz) seul et la réallocation complète (`brH<R>`, `brF<R>`)

`eval/results/hval_{dev,test}.csv`, même protocole que la section 5 (+ = mieux).

brH, masques de 13-20 kHz relevés (+6 dB à 96 et 160, +3,4 dB à 128) :

| | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|
| `dev` impair @96 | **+3,6 %** | **−0,011** | −0,011 | **+0,32 dB** |
| `test` @96 | **+4,9 %** | **−0,014** | **−0,021** | **+0,27 dB** |
| `dev` impair @128 | **+4,3 %** | **−0,030** | −0,003 | **+0,33 dB** |
| `test` @128 | **+3,0 %** | **−0,034** | **−0,009** | **+0,33 dB** |
| `dev` impair @160 | **+4,1 %** | **−0,077** | **−0,010** | **+0,63 dB** |
| `test` @160 | **+2,7 %** | **−0,112** | **−0,020** | **+0,64 dB** |

brF, la réallocation complète (brS + brH) :

| | Zimtohrli | PEAQ basique | PEAQ avancé | NMR |
|---|---|---|---|---|
| `test` @96 | **+8,7 %** | **−0,013** | **−0,033** | **+0,29 dB** |
| `test` @128 | **+6,0 %** | **−0,033** | **−0,014** | **+0,39 dB** |
| `test` @160 | **+3,0 %** | **−0,136** | **−0,030** | **+0,72 dB** |

(`dev` impair : même sens ; à 160 kb/s Zimtohrli y est neutre, −0,5 %.)

Lecture :
- Retirer des bits au-dessus de 13 kHz fait gagner **Zimtohrli et NMR** (NMR plus encore que
  brS) et perdre **les deux PEAQ**, de plus en plus fort avec le débit (−0,11 à 160 kb/s). C'est
  un vrai désaccord entre juges, pas un effet de bord : PEAQ pénalise la bande passante perdue,
  Zimtohrli et NMR jugent ces bits mieux employés ailleurs.
- Les gains de brS et de brH s'additionnent presque pour Zimtohrli (5 + 5 → 8,7 % à 96 kb/s) ;
  pour PEAQ, brF hérite des pertes de brH.
- L'aigu ne se tranche pas avec ces juges : il demande une écoute, en premier lieu à 96 kb/s
  (plus petite perte PEAQ, plus grand gain Zimtohrli). Pas de kit préparé.

## 8. Un zéro dans les deux règles de la TCQ (simulation, `eval/tcq_zero_sim.py`)

Modèle de `eval/tcq_sim.py` (gaussienne généralisée de forme β découpée en bandes MULE, un
Viterbi par trame), avec un Viterbi débit-distorsion (coût des index estimé en trois passes),
enveloppe sur 9 pas et 4 λ. Gain d'erreur quadratique de la règle impaire à la VVC (0, ±1, ±3…
en demi-pas, parité de l'index) sur la TCQ de MULE, à entropie égale (dB, + = mieux) :

| entropie (bit/coef) | 0,3 | 0,5 | 0,75 | 1 | 1,5 | 2 |
|---|---|---|---|---|---|---|
| β 1,1 (classes 1-2), 8 états | +0,07 | +0,05 | +0,03 | +0,01 | −0,04 | −0,08 |
| β 1,1, 64 états | +0,08 | +0,06 | +0,04 | +0,02 | −0,02 | −0,06 |
| β 0,7 (classes 3-5), 8 états | +0,45 | +0,52 | +0,44 | +0,36 | +0,17 | +0,01 |
| β 0,7, 64 états | +0,46 | +0,54 | +0,49 | +0,40 | +0,18 | +0,02 |

Lecture :
- Le zéro dans la règle impaire rapporte **jusqu'à 0,5 dB** sur une source à queue lourde
  (β 0,7, presque la moitié des coefficients de MULE : `S-LOG.md`) **sous 1 bit par
  coefficient**, et presque rien sur une source laplacienne (classes 1-2). Au-dessus de 1,5 bit,
  rien ou une petite perte (la règle impaire n'est plus régulière autour de zéro), comme attendu.
- Le gain dépend donc du débit réel de chaque classe. Ordre de grandeur (rms de `S-LOG.md` :
  0,67 D pour les classes 1-2, 1,84 D pour les classes 3-5) : les classes 3-5 seraient plutôt
  vers 1,5-2,5 bits, où le gain tombe à +0,2 dB ou moins. **À mesurer** : l'entropie réelle par
  classe (trace de l'encodeur), puis la moyenne pondérée des gains, avant tout prototype.
- Limites : entropie d'ordre 1 (les contextes du codec ne sont pas modélisés), erreur
  quadratique et non psychoacoustique. Pour comparaison, la TCQ entière (v2) avait rapporté
  environ 0,4 dB de SNR à débit égal et +0,06 d'ODG.
- Le changement toucherait le format (v6) : à ne lancer que si la mesure pondérée dépasse
  environ 0,1 dB.

### Le signe « triché » (même simulation, `--methods bias vvc --states 64 --frames 100`)

L'encodeur poussé vers un signe pour les ±D/2 de la règle impaire (−1 coûte 2 bits de plus à la
première passe, puis les fréquences suivent, cinq passes), codé à sa fréquence. Gain sur MULE (dB) :

| entropie (bit/coef) | 0,3 | 0,5 | 0,75 | 1 | 1,5 | 2 |
|---|---|---|---|---|---|---|
| β 1,1, signe triché | +0,00 | +0,00 | 0,00 | 0,00 | 0,00 | −0,01 |
| β 1,1, zéro dans Q1 | +0,07 | +0,05 | +0,03 | +0,01 | −0,03 | −0,07 |
| β 0,7, signe triché | +0,12 | +0,10 | +0,08 | +0,06 | +0,01 | −0,01 |
| β 0,7, zéro dans Q1 | +0,45 | +0,53 | +0,48 | +0,39 | +0,17 | +0,03 |

Le biais ne tient pas : la part de +1 parmi les ±1 de la règle impaire revient à 0,50-0,51. Le
Viterbi préfère payer le signe plutôt que perdre le choix de la branche (le signe de ±D/2 choisit
le sous-ensemble, donc l'état suivant). Le petit gain à β 0,7 vient probablement des deux passes
de plus (le coût des index mieux estimé), pas de signes prévisibles. **Piste close** ; le zéro
dans Q1 reste le seul candidat de ce côté, au même critère que plus haut (entropie réelle par
classe à mesurer d'abord).

### Le zéro dans Q1 sur les vrais coefficients de `dev` (`eval/tcq_zero_dev.py`)

Les valeurs que l'encodeur quantifie (sa trace, `--bitrate` 128 kb/s de production), 33 extraits
de `dev` (un sur deux), une trame sur huit : 3,55 millions de coefficients, 5 183 chaînes
(trame, canal, groupe). Requantifiées par la TCQ de MULE et par la règle à la VVC, 64 états,
Viterbi débit-distorsion, entropie de l'index sachant la classe d'allocation et la règle.

Point de fonctionnement réel (niveaux de l'encodeur) : **1,87 bit par coefficient**, erreur
0,281 (en (D/2)²). Classe 0 : 7,8 % des coefficients, 95 % de zéros ; classe 1 : 15,6 %, 61 % de
zéros ; classes 2 et plus : **76,6 %**, 30 % de zéros seulement.

| entropie (bit/coef) | 1,50 | 1,68 | 1,87 (codec) | 2,06 |
|---|---|---|---|---|
| zéro dans Q1 sur MULE, erreur (dB, + = mieux) | −0,58 | −0,37 | **−0,21** | −0,15 |

À erreur égale, la règle à la VVC demande **+0,03 bit par coefficient** (+1,7 % des bits
d'index, environ 2 kb/s de plus à 128 kb/s).

Lecture : **le zéro dans Q1 perd sur les vrais coefficients.** Nos coefficients sont codés vers
1,9 bit, au-dessus de la zone où la simulation trouvait un gain (sous 1 bit) ; les trois quarts
sont dans des classes où les zéros sont minoritaires, et la règle impaire irrégulière y coûte plus
que le signe économisé. Le modèle synthétique (une seule forme β par simulation) surestimait la
part des coefficients à bas débit. Seules les classes 0 et 1 (23 % des coefficients) pourraient y
gagner ; un zéro dans Q1 réservé à ces classes (la classe est connue du décodeur) rapporterait au
mieux une fraction de ces 23 %, sans doute sous 1 % du débit des coefficients. **Piste close** pour
le cas général ; la variante par classe n'est à reprendre que si l'on rouvre le format.
