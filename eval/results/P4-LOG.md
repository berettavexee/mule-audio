# Journal de P4

Jeu `dev` (66 extraits), PEAQ de base et avancé, NMR. Comparaisons à débit égal faites avec `eval/p4_compare.py`.

## Référence `dev` (`p4_refs_dev.csv`, `p4_base_dev.csv`)

| | ODG @128 | @160 | ODG avancé @128 | @160 | NMR @128 | @160 |
|---|---|---|---|---|---|---|
| Vorbis | −0,444 | −0,199 | −0,559 | −0,287 | −2,01 | −4,41 |
| Opus | **−0,205** | **−0,081** | **−0,427** | **−0,220** | −3,20 | −5,26 |
| MULE v1 | −0,405 | −0,195 | −0,530 | −0,228 | **−2,91** | **−5,99** |

L'écart avec Opus est plus grand sur `dev` (environ 0,2 d'ODG à 128) que sur le corpus P0 (0,14).

## A1 : diagnostic des sons tonals (`eval/p4_diag.py`)

NMR par demi-bande de Bark, MULE (q −9) contre Vorbis q4.5 :

- **triangles** : MULE est moins bon entre 65 et 500 Hz (−2 à −8 dB contre −15 à −22), mais **dépense trop au-dessus de 6 kHz** (−10 à −17 dB contre −2 à −7) ;
- **glockenspiel** : MULE perd sur les partiels fondamentaux entre 1,0 et 4 kHz (NMR proche de 0 contre −12). Il ne reçoit que 41 kb/s, contre 69 pour Vorbis ;
- **orgue** (173 contre 114 kb/s) et **violon** (125 contre 92 kb/s) : à 7,6 kHz, MULE est à −10 dB contre +2 à +4 dB pour Vorbis. Graves et médiums sont moins précis.

Conclusion : **les bits sont mal répartis**. Le décalage de masquage tonal de Johnston, `14,5 + z`, vaut environ 35 dB à 8 kHz : il dépense trop dans les aigus, et ces bits manquent dans les graves et les médiums.

## E1 : point de reconstruction décalé — rejeté

Centroïde mesuré de `|x|/Δ − |y|` par valeur de |y|, à q −9, sur 6 extraits :

| | |y| = 1 | |y| = 2 | |y| ≥ 3 |
|---|---|---|---|
| plage | −0,005 à +0,018 (glockenspiel −0,10) | +0,01 à +0,04 | +0,04 à +0,08 |

Avec la zone morte de 0,1, la reconstruction `|y|·Δ` est déjà au centroïde à 0,05 près. Un décalage positif fait **baisser** le SNR (abba : 21,65 → 21,36 dB avec δ = (0,1 ; 0,05)). Le gain maximal envisageable, environ 4 % du bruit sur les |y| ≥ 3, ne justifie pas un changement de format. Le prototype `Params.recon` est conservé mais n'est pas utilisé.

## A3a : plafond du décalage tonal (`tcap_db`) — **accepté à 25 dB**

| Variante | ODG @128 | ODG @160 | ODG avancé @128 | @160 | NMR @128 | Débit à réglage égal | Extraits < −0,05 |
|---|---|---|---|---|---|---|---|
| tc25 | **+0,015** [+0,002, +0,030] | **+0,030** [+0,018, +0,040] | +0,050 | +0,030 | +0,38 dB | −6,0 % | **0** |
| tc20 | +0,002 [−0,018, +0,025] | +0,036 | +0,068 | +0,040 | +0,48 dB | −9,4 % | 6 : violon −0,25, clavecin −0,20, trompette −0,17, emerson −0,11, glockenspiel −0,08, piano −0,06 |

Plus gros gains de tc25 : orgue +0,095 (avec −25 % de débit), miranda_sex_garden +0,067, kraftwerk +0,059, aphex +0,055. `Params.tcap_db = 25` par défaut.

Le plafond de 20 dB va trop loin pour les instruments tonals solistes : leurs partiels aigus ont réellement besoin d'un SMR élevé.

## Encodeur C (`core/enc.c`) — **en production**

- Il reprend l'encodeur Python décision par décision. **Les opérations de codage sont identiques**, symbole par symbole (`tests/test_cenc.py` : 7 signaux de test × 3 jeux de réglages ; en plus, 4 extraits réels vérifiés à la main).
- Les égalités de coût (drapeau M/S d'une bande quasi silencieuse, α, mode d'allocation) sont départagées avec la même tolérance des deux côtés (`TIE_EPS = 1e-9`). Sans elle, l'ordre de sommation différent faisait diverger les flux (balayage mono, trame 32).
- **Vitesse : 50 à 58 fois l'encodeur Python**, environ 0,1 s pour un extrait de 15 s, soit environ 150 fois le temps réel. Une évaluation `dev` de 3 variantes × 4 réglages (792 encodages) prend désormais 5 min 50 s, et le temps est surtout passé dans PEAQ.
- `eval/refcodecs.py` utilise le C par défaut. `mule-py…` utilise l'encodeur Python, encore nécessaire pour `rdoq`, `psy=snr`, `nf_tonal_db` et `recon`. `tools/mule_enc.py` passe aussi par le C.

## B4a : décalages par plage de bandes (référence = tc25)

| Variante | ODG @128 | ODG @160 | ODG avancé @128 | NMR @128 | Débit | Régressions | |
|---|---|---|---|---|---|---|---|
| low14 (graves +14 au lieu de +10) | −0,005 [−0,012, +0,003] | −0,009 | −0,001 | −0,20 | +2,4 % | 0 | rejeté (aide l'orchestre +0,16 et les triangles +0,09) |
| **mid4** (bandes 8–13, +4 dB) | **+0,037** [+0,027, +0,044] | **+0,027** | +0,038 | +0,61 | +4,5 % | 0 | **accepté** (glockenspiel +0,11) |
| mid6 (référence = mid4) | −0,003 | −0,002 | +0,005 | +0,07 | +2,2 % | 0 | rejeté |
| mid4w (bandes 8–16, référence = mid4) | +0,012 [+0,001, +0,022] | +0,001 | +0,016 | +0,52 | +4,1 % | 0 | **accepté, gain marginal** |

Réglages par défaut : `tcap_db = 25`, `mid_db = 4`, `mid_hi = 17`.

## P4.2a : contextes et vitesse d'adaptation, sans perte (`p4_rate_p42a.csv`, CDF uniformes, q −9 et −12)

| Variante | Débit | Décision |
|---|---|---|
| inter3 (prédiction inter-trame lissée sur k−1, k, k+1) | −0,23 % | rejeté |
| sctx (trames courtes : fenêtre précédente du groupe) | 0,00 % | rejeté |
| ac2 / ac4 (classe d'allocation a÷2 / a÷4) | +0,58 % / −0,18 % | rejetés |
| r3 (rate de base 3 au lieu de 4) | **−0,69 %** | à revalider avec les CDF entraînées |
| rbig0 (pas de +1 pour les alphabets > 4) | **−0,68 %** | idem (même effet que r3 sur les flux à 16 symboles) |
| r5 / rslow (seuils 7/15) / rlong (seuils 31/63) | +2,78 % / +0,65 % / −0,25 % | rejetés |

Les contextes actuels sont déjà bien choisis : les raffinements de contexte gagnent moins de 0,25 %. Le seul levier notable est une adaptation plus rapide des alphabets de 16 symboles.

Mesures supervisées par un sous-agent : exécution, détection des erreurs, vérification du nombre de lignes et des valeurs manquantes.

## C2 : rotation stéréo par bande — rejetée (`eval/p4_stereo_pe.py`)

Entropie perceptuelle des trames longues sur `dev` (66 extraits) :
- L/R seul : 55,2 Mbit ;
- **meilleur choix L/R ou M/S par bande (le format actuel) : 51,29 Mbit** ;
- avec en plus une rotation KLT quantifiée sur 16 angles, coût de l'angle compris : 51,21 Mbit, soit **−0,16 %** seulement (orgue −1,1 %, triangles −1,0 %, tame_impala −0,7 %).

Un changement de format ne se justifie pas. L'intensity (C3) ne servirait que sous 128 kb/s, hors de la cible : elle est écartée aussi.

## D4 : allocation prédite par la variation d'énergie — rejetée

On ajoute `β·ΔQ` à la référence, en fréquence comme en temps (`proto_alloc_beta`, CDF uniformes, q −9) :

| | β = 0 | 0,25 | 0,5 |
|---|---|---|---|
| abba, allocation (kb/s) | 5,99 | 6,78 | 6,80 |
| One More Time | 5,27 | 5,92 | 6,03 |
| orchestre | 4,39 | 4,36 | 4,31 |

L'allocation suit le rapport signal/masque, et non l'énergie.

**Bilan du codage entropique** : contextes, stéréo et allocation sont proches de la saturation. Les gains restants devront venir de l'encodeur (psychoacoustique, allocation optimisée).

## P4.3a : psychoacoustique, réglages propres à l'encodeur (`p43a.csv`, réf. = tc25 + mid4w)

| Variante | ODG @128 | ODG @160 | ODG avancé @128 / @160 | NMR @128 | Débit | Décision |
|---|---|---|---|---|---|---|
| fft (tonalité sur un spectre FFT de Hann, bruit de référence −2,5 dB) | +0,011 [+0,008, +0,014] | +0,008 | +0,009 / +0,005 | +0,11 | −0,6 % | passe le critère |
| **fft4** (idem, bruit de référence 4,0 dB) | **+0,012** [+0,006, +0,020] | **+0,012** [+0,003, +0,023] | +0,011 / +0,009 | +0,11 | **−5,2 %** | **accepté** |
| tm6 / tm12 (post-masquage 6 / 12 dB par 1024 échantillons) | +0,003 / +0,002 | −0,001 / +0,001 | −0,013 / 0,000 | −0,32 / −0,05 | −1,9 / −0,3 % | rejetés |
| msh2 (hystérésis M/S, 2 bits) | +0,001 | +0,002 | 0,000 | +0,03 | 0 | rejeté |
| pk12 (pic/moyenne > 12 dB : jamais de bruit) | +0,001 (n.s.) | +0,004 (n.s.) | +0,004 | −0,12 | +1,2 % | rejeté (triangles +0,12, clavecin +0,07) |
| dzt0 (zone morte 0 en bande tonale) | +0,004 | −0,002 | −0,006 | −0,07 | +0,8 % | rejeté |

`fft_tonal` est aussi porté dans l'encodeur Python, avec des opérations identiques au C, et devient le réglage par défaut (`fft_noise_db = 4`).

## P4.2b : vitesse d'adaptation avec les CDF entraînées — rejetée (`p4_rate_p42b.csv`)

| Variante (seuils) | Débit |
|---|---|
| rbig0 (4/15/31/0) | +0,71 % |
| r3 (3/15/31/1) | +0,70 % |
| r3big0 / rbig0long | +2,44 % (identiques : les CDF entraînées démarrent à count = 16) |

Avec des CDF initiales entraînées, adapter plus vite ne fait que bruiter les modèles. Le gain mesuré avec des CDF uniformes (−0,7 %) venait seulement de l'apprentissage après réinitialisation. **Aucun changement de format n'est retenu en P4.2.**

## P4.4 : allocation optimisée débit-distorsion (`rd_lambda`) et échelle de tonalité (`p44a.csv`)

Pour chaque bande, l'encodeur choisit entre a−1, a et a+1 en minimisant J = bruit/masque + λ·bits. Les bits sont exacts : ils viennent d'une copie des modèles adaptatifs que l'encodeur fait évoluer comme le décodeur.

| Variante | ODG @128 | ODG avancé @128 | Moyenne des deux @128 / @160 | NMR @128 | Débit | Décision |
|---|---|---|---|---|---|---|
| rd10 | −0,007 | +0,013 | +0,003 / −0,002 | +0,16 | +5,0 % | rejeté |
| rd14 | −0,007 | +0,014 [+0,010, +0,017] | +0,003 / 0,000 | +0,25 | −0,2 % | rejeté |
| **rd20** | +0,000 | **+0,024** [+0,011, +0,033] | **+0,012 / +0,009** | **+0,28** | −5,0 % | **accepté, gain marginal** (aucune régression ; orchestre +0,06, triangles +0,03) |
| ts15 (échelle de tonalité 15) | −0,001 | −0,009 | | −0,09 | +2,7 % | rejeté (orgue −0,07) |
| ts30 | −0,016 | +0,002 | | +0,05 | −3,0 % | rejeté (violon −0,12, trompette −0,10, clavecin −0,07) |

`rd_lambda` n'existe que dans l'encodeur C. Dans `Params`, `None` signifie « valeur de production du C » (2,0). L'encodeur Python ne le fait pas, et `tests/test_cenc.py` le désactive explicitement (0) pour comparer les deux encodeurs.

## Incident : plantage de `mule-dec` lors d'une évaluation

Un SIGSEGV de `mule-dec` est survenu une fois pendant la première exécution de p44a. **Il n'a pas pu être reproduit** :
- 1 584 fichiers réencodés et décodés, sans échec ;
- 528 fichiers décodés par un `mule-dec` compilé avec ASan et UBSan, sans aucune alerte ;
- l'encodeur est déterministe (528 × 2 encodages identiques).

Mesures prises :
- `mule-dec` vérifie désormais les bornes de chaque page Ogg (fichier tronqué : refus propre) et agrandit son tableau de paquets au lieu de le dimensionner d'avance ;
- `refcodecs` copie tout fichier qui fait échouer le décodeur dans `eval/results/crash/` (avec ses paramètres), puis réessaie une fois ;
- règle de travail : plus aucune compilation dans `build/` pendant une évaluation (expériences dans `MULE_BUILD=build_dev`).

## Bilan de P4 sur le jeu `test` (`p4_test.csv`, 30 extraits jamais utilisés pour régler, ViSQOL + PEAQ + NMR)

| à débit égal | ODG @128 | ODG @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | NMR @128 | @160 |
|---|---|---|---|---|---|---|---|---|
| Vorbis (libvorbis 1.3) | −0,449 | −0,164 | −0,631 | −0,339 | 4,474 | 4,619 | −0,60 | −3,01 |
| Opus 1.6 | **−0,118** | **0,000** | **−0,446** | −0,241 | 4,539 | **4,654** | −2,38 | −4,30 |
| MULE v1 (encodeur P3) | n.d. (< 132 kb/s) | −0,173 | n.d. | −0,283 | n.d. | 4,633 | n.d. | −3,79 |
| **MULE après P4** | −0,299 | −0,090 | −0,481 | **−0,203** | **4,601** | 4,629 | **−2,72** | **−5,72** |

- **Les gains de P4 tiennent sur des extraits jamais vus** : à 160 kb/s, l'ODG passe de −0,173 à −0,090 (+0,083) et l'ODG avancé de −0,283 à −0,203 face à v1. À réglage égal, le débit baisse d'environ 9 %.
- MULE est devant Vorbis sur toutes les métriques. Il est devant Opus sur l'ODG avancé à 160, sur ViSQOL à 128 et sur le NMR. **Opus reste devant sur l'ODG de base** : +0,18 à 128, +0,09 à 160.
- **Objectifs du plan** :
  - ODG de base ≤ −0,35 à 128 et ≤ −0,20 à 160 : **atteints** sur `test` (−0,30 et −0,09) ;
  - avance en ODG avancé et en NMR : gardée ;
  - pire écart d'un extrait face à Vorbis ≥ −0,10 : à vérifier par extrait ;
  - **ABX (G2) : à faire** (kit `data/listen/g2/`).

## Leviers retenus en P4 (encodeur seul, format v1 inchangé)

1. `tcap_db = 25` : plafond du décalage de masquage tonal.
2. `mid_db = 4`, `mid_hi = 17` : décalage de masquage entre 1,4 et 8 kHz.
3. `fft_tonal`, `fft_noise_db = 4` : tonalité mesurée sur un spectre FFT de Hann.
4. `rd_lambda = 2` : allocation optimisée débit-distorsion, avec des coûts exacts (encodeur C).

**Aucun changement de format n'a été retenu.** Contextes, vitesse d'adaptation, rotation stéréo et prédiction de l'allocation ont tous été mesurés et rejetés. Le décodeur v1 et `spec/FORMAT.md` restent valables. Le réentraînement des CDF (P4.7) n'est pas fait, conformément à ta consigne (« plus tard si nécessaire ») ; l'étude du gain possible figure plus bas.

## P4.7 : étude du réentraînement des CDF — inutile pour A

Tables entraînées sur les 200 extraits du jeu `train` (tirés au hasard dans la bibliothèque, disjoints de `dev` et `test`), débit mesuré sur `dev` contre les tables actuelles (36 extraits P0) :
- q −9 : **−0,03 %** ;
- q −12 : **−0,05 %**.

Les tables actuelles généralisent déjà. Elles ne sont pas remplacées, et l'identifiant de table reste 1. Les tables d'étude sont dans `eval/results/init_cdf_train.npz`. À refaire seulement si le format change (passage à B).

## Variantes B et C — B adopté comme format v2 (17/11/2026)

Voir `docs/VARIANTS-BC.md` (§5 et §6). **B (TCQ, λ 0,3) bat A sur `test`** : ODG +0,063 @128 / +0,037 @160, ODG avancé +0,056 / +0,036, sans régression. C (PVQ) reste en dessous de A.
