# P2 : énergies, allocation, quantification scalaire, débit estimé

> **Bilan final de P2 : voir la dernière section, « MULE v3 : G1 atteint ».** La section « Verdict avec PEAQ, puis MULE v2 » explique le diagnostic. La v1 décrite ci-dessous est conservée sous le nom `mule-v1` dans `eval/refcodecs.py`.

Code :
- `py/mule/encoder.py` (encodeur d'estimation) et `py/mule/psy.py` (modèle psychoacoustique v1) ;
- `core/model.c` (modèles CDF adaptatifs sur 15 bits, façon AV1), appelé depuis Python par `py/mule/native.py` via cffi.

Le débit est **estimé**. Chaque valeur codée devient un symbole, et son coût est le −log₂p donné par les vrais modèles adaptatifs, exact à la surcharge rANS près. À cela s'ajoutent les bits bruts (signes, échappements, masques de groupes) et un forfait de 10 bits par trame pour l'en-tête de paquet, le vidage rANS et la position des paquets clés. La reconstruction suit les règles du décodeur.

Lancer : `.venv/bin/python eval/run_eval.py mule_-6 mule_-9 mule_-12 mule_-15`. Le paramètre de la configuration est `q_db`, le bruit visé par rapport au masque.

## Ce qui est implémenté

- Commutation de blocs P1, avec **regroupement adaptatif** des blocs courts : un nouveau groupe commence à chaque saut d'énergie de plus de 6 dB.
- Stéréo L/R ou M/S **par bande**, choisie par entropie perceptuelle. Les bandes M/S utilisent le plus faible des deux masques L et R.
- Énergies : pas de 1,5 dB, prédiction en entiers `(α·Q_prev[b] + (32−α)·Q[b−1]) >> 5` avec α ∈ {0, 16, 26, 31} choisi pour chaque trame. Résidus codés sur 16 symboles avec échappement, 9 contextes.
- Allocation `a_b` calculée à partir du masque, codée en différence d'une bande à la suivante (3 contextes).
- Quantification scalaire de la forme normalisée, zone morte 0,2. Coefficients codés sur {0…14, ESC}, avec 96 contextes : 16 classes d'allocation × 6 classes de voisinage (2|y₋₁| + |y₋₂|).
- Reconstruction : remplissage des zéros par du bruit plafonné (`nf·Δ²`), renormalisation pour conserver l'énergie, et remplacement par du bruit des bandes où a = 0.
- Paquet clé toutes les 40 trames (0,93 s) : modèles et prédicteurs réinitialisés.

## Résultat : les deux métriques ne sont pas d'accord

| Config | kb/s | ViSQOL | NMR (dB) |
|---|---|---|---|
| mule_-6 | 104,3 | 4,598 | +1,32 |
| mule_-9 | 130,9 | 4,624 | −1,41 |
| mule_-12 | 159,4 | 4,644 | −4,20 |
| mule_-15 | 189,4 | 4,656 | −6,88 |

À débit égal :

| | ViSQOL @128 | ViSQOL @160 | NMR @128 | NMR @160 |
|---|---|---|---|---|
| Vorbis (libvorbis 1.3) | 4,548 | 4,641 | −3,51 | −5,92 |
| Opus 1.6 | 4,512 | 4,630 | −3,92 | −6,18 |
| **MULE v1** | **4,621** | **4,644** | −1,11 | −4,26 |

- **D'après ViSQOL, G1 est atteint** : MULE devance les deux références à 128 kb/s et fait jeu égal à 160 kb/s.
- **D'après le NMR interne, G1 n'est pas atteint** : MULE a 2 à 2,5 dB de retard.
- Hypothèse : le remplissage par bruit, qui conserve l'énergie. ViSQOL compare des spectrogrammes et ne voit presque pas de différence entre un signal et un bruit de même enveloppe. Le NMR mesure l'erreur sur la forme d'onde, et remplacer une bande par du bruit y compte comme une erreur double. Indice qui va dans ce sens : la courbe ViSQOL de MULE est très plate, avec déjà 4,60 à 104 kb/s.
- Côté NMR, les écarts se concentrent sur les **extraits tonals et calmes** : orchestre +12,7 dB, triangles +9,9, orgue +6,8, glockenspiel +6,3, violon +5,9, Satie +4,7, quatuor +4,4. Sur les extraits denses (rock, électro, pop), MULE est au niveau de Vorbis à ±1 dB. Côté ViSQOL, les extraits où MULE est le moins bon sont abba (−0,15), orgue (−0,12) et pires_concerto (−0,08). Les meilleurs sont pinkfloyd (+0,64), dp_veridisquo et emerson_fugue (+0,45).
- **La décision demande une troisième source** : l'écoute (jeu préparé dans `data/listen/`) ou PEAQ.

## Mesures demandées pour P2 (q_db = −10, environ 140 kb/s)

On compare à débit égal en utilisant la pente de la courbe de MULE, environ −0,1 dB de NMR par kb/s.

| Variante | kb/s | NMR | Lecture |
|---|---|---|---|
| référence (40 trames entre paquets clés, groupes adaptatifs, stéréo auto, zone morte 0,2) | 139,97 | −2,31 | |
| paquets clés toutes les 20 trames | 142,61 | −2,31 | +1,9 % |
| toutes les 80 trames | 138,45 | −2,31 | −1,1 % |
| **sans réinitialisation** | 136,73 | −2,31 | **la réinitialisation toutes les 0,93 s coûte 2,4 %** |
| 8 groupes | 144,84 | −2,57 | +3,5 % de débit pour −0,26 dB, à peu près neutre |
| 1 groupe | 138,43 | −1,96 | −1,1 %, mais pré-écho (P1) |
| L/R seul | 148,99 | −1,91 | nettement moins bon que le choix auto |
| M/S seul | 147,82 | −3,19 | équivalent au choix auto à débit égal |
| zone morte 0 | 152,72 | −4,42 | **environ 0,8 dB de mieux** à débit égal (à vérifier avec ViSQOL) |
| zone morte 0,3 | 133,69 | −1,40 | environ 0,3 dB de moins bien |

## Répartition du débit (abba, environ 128 kb/s)

Coefficients 86 kb/s, signes et échappements 23, allocation 9,6, énergies 8, stéréo, type de bloc et paquets environ 1,1.

**L'information annexe (énergies + allocation, environ 14 %) est plus lourde que prévu.** C'est la première piste d'économie : prédire l'allocation dans le temps ou à partir des énergies, et ajouter une hystérésis dans l'encodeur.

## Pistes pour la suite, par ordre d'intérêt

1. Trancher entre les deux métriques : écoute ABX sur `data/listen/` et/ou PEAQ.
2. Information annexe : allocation prédite (dans le temps ou à partir de Q), hystérésis sur `a_b`.
3. Extraits tonals : scinder les bandes hautes (au-dessus de 8 kHz), ne remplacer par du bruit que les bandes qui ressemblent à du bruit, régler la zone morte ou la RDOQ.
4. CDF initiales entraînées, pour réduire le coût de 2,4 % des réinitialisations.

## Verdict avec PEAQ, puis MULE v2

PEAQ (GstPEAQ, versions de base et avancée, `third_party/peaq-install`) a été ajouté à la chaîne d'évaluation. Il **rejoint le NMR** : MULE v1 obtenait un ODG de −0,83 à 128 kb/s, contre −0,48 pour Vorbis et −0,30 pour Opus. Les écarts se concentraient sur les extraits tonals et calmes. Comme le soupçonnait l'hypothèse, ViSQOL ne voit pas ce type de dégradation.

Diagnostic sur 12 extraits critiques (`p2_tonal.csv`, `p2_nf.csv`, `p2_ath.csv`, `p2_ton.csv`, `p2_v2.csv`, `p2_snr.csv`), avec l'ODG de base à 128 kb/s :

| Variante | ODG @128 | Conclusion |
|---|---|---|
| v1 | −1,12 | |
| zone morte 0 / bandes tonales jamais remplacées par du bruit | −1,09 / −1,10 | pas la cause |
| SNR constant à la place du masque | bien pire | le modèle psychoacoustique est utile |
| **pas de bruit dans les bandes codées, pas de renormalisation (nf0)** | **−0,93** | le bruit injecté entre les partiels s'entend |
| ATH −10 / −20 dB | −1,09 / −1,20 à débit égal | l'orchestre reçoit autant de bits que Vorbis mais reste à −2,3 : ce n'est pas une question de débit |
| **nf0 + 10 dB de décalage de masquage dans les 8 bandes basses (nf0low)** | **−0,65** | dans les graves, le SNR de MULE était de 16 dB contre 31 pour Vorbis. Avec 8 coefficients par bande, la tonalité est mal estimée, et ces bandes sont plus larges qu'une bande critique. |
| nf0low + ATH −10 ± tonalité plus raide | −0,73 à −0,89 | déplace les bits au mauvais endroit |

Vorbis fait −0,41 sur ce sous-ensemble.

**MULE v2** (réglage par défaut actuel de `encoder.Params`) : `nf = 0`, `renorm = False`, `low_db = 10`. Le remplacement par du bruit des bandes où a = 0 est conservé.

Sur tout le corpus (`p2_mule_v2.csv`) :

| à débit égal | ODG @128 | ODG @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | NMR @128 | @160 |
|---|---|---|---|---|---|---|---|---|
| Vorbis | −0,48 | −0,24 | −0,51 | −0,25 | 4,548 | 4,641 | −3,51 | −5,92 |
| Opus | **−0,30** | **−0,17** | **−0,45** | **−0,23** | 4,512 | 4,630 | −3,92 | −6,18 |
| MULE v1 | −0,83 | −0,57 | −1,03 | −0,50 | 4,621 | 4,644 | −1,11 | −4,26 |
| **MULE v2** | −0,61 | −0,40 | −0,61 | −0,27 | 4,608 | 4,622 | −3,67 | **−6,69** |

Débit dont MULE v2 a besoin pour égaler l'ODG de base des références : **147 kb/s pour Vorbis à 128** (+15 %), 177 pour Opus à 128, 187 pour Vorbis à 160, 198 pour Opus à 160.

**G1 n'est pas encore atteint, mais on s'en approche** :
- l'écart au critère « Vorbis q4 + 10 % » est de 15 % sur l'ODG de base ;
- sur l'ODG avancé, Vorbis est presque rejoint à 160 kb/s ;
- sur le NMR, MULE fait mieux que Vorbis et qu'Opus à 160 kb/s.

L'écart avec Opus est désormais **uniforme**, environ −0,3 d'ODG sur presque tous les extraits, denses compris. Le reste vient donc de l'efficacité globale (information annexe, codage entropique, RDO) plus que d'un défaut localisé.

Constat de conception : **la conservation de l'énergie (renormalisation + remplissage par bruit), une idée centrale de la combinaison A, est pénalisée par PEAQ en quantification scalaire.** Ce point est à reprendre dans `PROPOSAL-A.md` si l'écoute le confirme.

## MULE v3 : G1 atteint

Leviers ajoutés après la v2, mesurés à débit égal sur tout le corpus :

| Levier | Effet |
|---|---|
| Allocation : choix, pour chaque groupe, entre écart à la bande précédente et écart à la trame précédente (1 drapeau), plus hystérésis ±1 | allocation −25 à −40 % |
| Contexte inter-trame : le \|y\| de la trame longue précédente, recalé en entiers et **fusionné** dans le prédicteur de voisinage | −0,3 à −2,9 % de débit, plus sur les sons tenus. En dimension de contexte supplémentaire, il faisait **perdre** (contextes trop dilués) |
| Préfixe Exp-Golomb des échappements codé par un modèle adaptatif | −2,2 % sur l'orgue et le violon, où les échappements pesaient 10 à 11 % |
| Les trois leviers ci-dessus ensemble | ODG @128 de −0,611 à −0,580 |
| **CDF initiales entraînées** (`py/mule/init_cdf.npz`, `eval/p2_train_init.py`) | **−2,9 % à 128 kb/s**, de −2,0 à −3,5 % selon le débit (validation croisée en 2 plis) |
| **Zone morte 0,2 → 0,1** | **ODG @128 de −0,544 à −0,443.** Sans remplissage par bruit, une zone morte large fait vraiment perdre les petits coefficients. Avec 0 : −0,471 |
| RDOQ (arrondi au plus proche ou juste en dessous, λ·R estimé avec les CDF entraînées) | rien (λ 0,7) ou pire (λ 1,4 et 2,5) : laissée **désactivée** |

Évaluation finale (`p2_mule_final.csv`, tout le corpus, trois métriques) :

| à débit égal | ODG @128 | ODG @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | NMR @128 | @160 |
|---|---|---|---|---|---|---|---|---|
| Vorbis (libvorbis 1.3) | −0,479 | −0,243 | −0,511 | −0,250 | 4,548 | 4,641 | −3,51 | −5,92 |
| Opus 1.6 | **−0,301** | **−0,170** | −0,451 | −0,228 | 4,512 | 4,630 | −3,92 | −6,18 |
| **MULE v3** | −0,443 | −0,234 | **−0,453** | **−0,180** | **4,636** | **4,650** | **−4,71** | **−7,90** |

Débit dont MULE a besoin pour la même qualité que :

| Référence | ODG de base | ODG avancé |
|---|---|---|
| Vorbis à 128 | **124 kb/s** | 124 kb/s |
| Vorbis à 160 | 158 kb/s | 150 kb/s |
| Opus à 128 | 149 kb/s | 128 kb/s |
| Opus à 160 | 175 kb/s | 153 kb/s |

**G1 est atteint** : à qualité égale, MULE consomme moins que Vorbis sur les quatre métriques. Sur l'ODG avancé, ViSQOL et le NMR, il est aussi devant Opus. Seul l'ODG de base laisse Opus en tête, d'environ 15 à 20 % de débit.

Par extrait, à 140 kb/s (ODG de base) : MULE fait au moins aussi bien que Vorbis sur **30 extraits sur 36**. Ses points faibles restent les sons tonals clairsemés : triangles (−0,33 contre Vorbis), glockenspiel (−0,26), orgue (−0,19), violon (−0,18). Ses meilleurs résultats sont Vivaldi (+0,56), la parole (+0,21 à +0,27) et le clavecin (+0,18). Opus reste devant sur 30 extraits sur 36, de 0,05 à 0,2 environ.

**Réglage par défaut actuel** (`encoder.Params`) :
- zone morte 0,1 ;
- `nf = 0`, `renorm = False` ;
- `low_db = 10` ;
- allocation `auto` + hystérésis 1 ;
- contexte inter-trame `mix` ;
- échappements adaptatifs ;
- CDF entraînées ;
- groupes adaptatifs ;
- stéréo auto ;
- paquet clé toutes les 40 trames.

## Pistes restantes, par ordre d'intérêt

1. Sons tonals clairsemés (triangles, glockenspiel) : bandes hautes plus fines, ou allocation au niveau de sous-bandes.
2. Modèle psychoacoustique : masquage temporel, meilleure estimation de la tonalité (aujourd'hui une planéité sur peu de coefficients).
3. RDOQ avec un vrai modèle de débit (état adaptatif) et une distorsion perceptuelle.
4. Stéréo : rotation par bande (v2 de la proposition), intensity dans les aigus.
