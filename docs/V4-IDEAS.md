# Une v4 ? Étude du 19/11/2026

Cible inchangée : **128 à 160 kb/s**. Plus bas, s'approcher d'Opus demanderait de complexifier
beaucoup le codec (intensité, stéréo paramétrique, remplissage, pliage, réduction de bande).

Point de départ (format v3, `test`, à débit égal) : à 128 kb/s, ODG −0,17 contre −0,12 pour
Opus ; MULE est devant en ODG avancé, en ViSQOL et en NMR. L'écart restant est diffus et logé
dans l'enveloppe temporelle du rock dense (`eval/results/D-LOG.md`) ; à l'écoute ABX, la v2
était déjà indiscernable d'Opus.

## Les idées examinées

Une liste de pistes reçue le 19/11/2026, confrontée à ce qui avait déjà été mesuré :

| Idée | Déjà mesuré | Verdict |
|---|---|---|
| Contextes conçus par apprentissage, rANS inchangé | contexte inter-trame 2 % ; tous ses raffinements < 0,5 % (M1 à M8, point 4) | sonde B |
| PVQ sur les bandes peu tonales, TCQ ailleurs | PVQ à θ récursif (`VARIANTS-BC.md`) : perdante, surtout sur les sons tonals ; les énergies à part donnent déjà la conservation d'énergie | écartée sans sonde : deux quantificateurs au décodeur pour des bandes à peu de bits |
| Treillis plus riche (état = parité + classe, treillis par bande, codage conjoint) | contextes selon l'état −0,42 % (point 4) ; 64 contre 32 états +0,003 ; 48 états moins bons que 32 | écartée : la classe spectrale relève des contextes, pas du treillis ; reste ≈ 0,5 dB théorique en TCVQ, décodeur bien plus lourd |
| Remplissage de bruit coloré ou modulé | à 128 kb/s, seules les bandes au-dessus de 16 kHz sont remplies (`D-LOG.md`) ; pente spectrale essayée : rien | écartée à 128 kb/s (utile à bas débit) |
| Meilleur modèle psychoacoustique | modèle 2 de MPEG, étalement de Terhardt, addition en loi de puissance : écartés ; le masquage temporel n'avait jamais été essayé | sonde A |
| Bandes variables | Haar dans les bandes (point 26) : +0,003 ; bruit d'aigus déjà sous Opus | écartée |
| Stéréo avancée (intensité, repliement, paramétrique) | choix L/R ou M/S par bande ; rotation KLT par bande −0,16 % (P4) ; Opus n'utilise l'intensité qu'à bas débit | sonde C |

## Les sondes (branche `v4-probes`, `eval/v4_probes.py`, journaux dans `eval/results/m-logs/v4*`)

**A. Masquage temporel dans le modèle de l'encodeur** (encodeur seul ; `dev`, 66 extraits, à
débit égal contre la v3) :

| Variante | ODG @128 | ODG avancé | 2f | ViSQOL | NMR | régressions |
|---|---|---|---|---|---|---|
| A1, γ 0,5 : masque × platitude temporelle de la bande dans la trame | −0,016 | −0,015 | −1,1 | −0,008 | −0,19 dB | 3 |
| A1, γ 1 | −0,031 | −0,025 | −2,7 | −0,012 | −0,33 dB | 9 |
| A2, post-masquage à −10 dB de la trame précédente | −0,178 | −0,123 | −9,8 | +0,004 | −1,00 dB | 25 |
| A2, à −20 dB | −0,027 | −0,023 | −0,4 | +0,001 | −0,04 dB | 5 |

Toutes moins bonnes. Abaisser le masque des bandes dont l'énergie varie dans la trame dépense
5 à 9 % de bits de plus à réglages égaux, sans que l'enveloppe temporelle s'améliore pour PEAQ
(2f en baisse). Le post-masquage libère des bits mais laisse passer du bruit audible pour tous
les modèles. Le modèle actuel, dont les trames de 23 ms et la borne de pré-écho tiennent déjà
compte du temps, est près de son optimum pour ces métriques.

**B. Contextes appris** (trace de la v3 à q −7, 118,5 kb/s sur `dev`) : un tuple fin par
coefficient (classe d'allocation, deux index précédents, terme inter-trame, parité de l'état,
type de bloc, classe de bande, première raie de la bande : 39 908 tuples vus sur 60 extraits de
`train`), regroupé en K contextes par k-means sur les distributions (divergence KL), codé sur
`dev` avec les vrais modèles adaptatifs :

| Règle | débit total | extraits meilleurs |
|---|---|---|
| apprise, 96 contextes (taille actuelle) | −0,30 % | 54/66 |
| apprise, 192 | −0,44 % | 55/66 |
| apprise, 384 | −0,52 % | 57/66 |
| borne statique des tuples fins | −1,18 % | |

Moins de 1 %, au prix d'une table de près de 40 000 entrées au décodeur (et de 2 à 4 fois
plus de modèles adaptatifs) : contraire à la priorité mémoire du cœur B.

**C. Borne de la stéréo** (bits des coefficients du second canal codé, `dev` à q −7) :

| Au-dessus de | canal S des bandes M/S | + second canal des bandes L/R |
|---|---|---|
| 4 kHz | 5,2 % du débit | 21,2 % |
| 8 kHz | 2,4 % | 11,6 % |
| 12 kHz | 0,9 % | 4,5 % |

L'intensité ne peut économiser sans détruire l'image que dans les bandes corrélées, celles que
l'encodeur code déjà en M/S : au plus 2 à 3 % du débit au-dessus de 8 kHz, soit environ +0,02
d'ODG à la pente mesurée, avant la perte d'image et le coût des angles. Les bandes L/R sont
décorrélées (c'est pourquoi l'encodeur les y garde) ; les sources panoramiquées, la rotation
par bande les captait déjà, pour −0,16 %.

**D. Débit variable : une cible de bruit par trame** (encodeur seul : q n'est pas transmis ;
`dev`, à débit moyen égal). Le VBR de MULE vise le même rapport bruit/masque dans chaque trame.
Le réservoir de bits (AAC, xHE-AAC) sert les débits constants, sans objet hors ligne ; le bonus
aux transitoires de libopus avait été essayé à l'axe 2 (levier H : +0,004, non adopté) ; ses
`dynalloc` et `alloc_trim` tiennent lieu du masque explicite que MULE a déjà. Restait une
répartition selon la difficulté de la trame, à la manière d'un encodage en deux passes : q
décalé selon l'écart du niveau de la trame, ou de son entropie perceptuelle, à leur moyenne
glissante (environ 5 s), dans ±6 dB.

| Variante | ODG @128 | ODG avancé | 2f | ViSQOL | NMR | régressions |
|---|---|---|---|---|---|---|
| niveau, 0,1 dB par dB | +0,004 [−0,009 ; +0,022] | +0,003 | −2,0 | −0,001 | +0,29 dB | 6 |
| niveau, 0,2 dB par dB | −0,002 | +0,000 | −3,3 | −0,002 | +0,34 dB | 11 |
| entropie perceptuelle, 1 dB par doublement | +0,003 | +0,003 | −2,2 | −0,000 | +0,18 dB | 5 |
| entropie perceptuelle, 2 dB | +0,001 | +0,002 | −2,9 | −0,001 | +0,20 dB | 9 |

Au niveau du bruit de mesure, 2f en baisse et des régressions : le même rapport bruit/masque
partout reste le meilleur choix, comme le prédit la théorie pour une gêne additive.

## Conclusion

À 128-160 kb/s, aucune piste n'atteint les seuils du projet (2 % de débit pour un changement de
format, +0,01 d'ODG pour l'encodeur). **Pas de v4 justifiée** : la v3 reste le format. Les
écarts restants avec Opus se mesurent en centièmes d'ODG, sur lesquels les métriques ne
s'accordent pas et que l'oreille n'a pas distingués. Si un jour la cible descendait sous
128 kb/s, l'ordre serait inverse : intensité, remplissage de bruit et pliage deviendraient les
premiers leviers (écart de 0,7 d'ODG avec Opus à 64 kb/s).
