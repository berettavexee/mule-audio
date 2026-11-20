# Série « MULE, ou comment marche un codec audio moderne »

Plan du 19/11/2026. Fil conducteur : chaque billet montre une brique d'un codec, ce qu'elle
rapporte (chiffres à l'appui) et ce qui n'a pas marché. Ton du README : autodérision, honnêteté,
« utilisez Opus ». Sons de démonstration : EBU SQAM (castagnettes, glockenspiel, trompette,
voix) ou signaux synthétiques, jamais de musique sous droits. Chaque chiffre renvoie à un
journal du dépôt.

## Découpage

| # | Titre de travail | Idée centrale | Matériau |
|---|---|---|---|
| 1 | **Anatomie d'un codec moderne, en le construisant** | Le trajet complet d'une trame, de l'échantillon au paquet : transformée, bandes, énergie et forme, masque, allocation, bruit, stéréo, flux | `docs/ARTICLE.md`, `spec/FORMAT.md`, `core/enc*.c` |
| 2 | **Quantifier en treillis** | La TCQ sans maths lourdes : un pas divisé par deux gratuitement grâce à la parité ; puis l'histoire de la v3 (l'enchaînement seul ne rapporte rien, le Viterbi conjoint fait le gain, 48 états font moins bien que 32) | `docs/VARIANTS-BC.md`, `eval/results/B-LOG.md` |
| 3 | **La compression vient du modèle, pas du codeur** | rANS en une page, puis contextes et adaptation ; le codeur est à 0,01 % de l'idéal, tout le gain est dans la modélisation ; les contextes appris : −0,5 % | README, `eval/entropy_gain.py`, `C-LOG.md`, `docs/V4-IDEAS.md` |
| 4 | **Quand les machines écoutent à notre place** | PEAQ, ViSQOL, NMR, 2f : comment on mesure, comment elles se contredisent, le piège des 20 kHz, l'extrapolation exploitée par CMA-ES, l'ABX qui ne distingue rien à 128 kb/s | `E2-LOG.md`, `M-LOG.md`, `G2-ABX.md`, `G3-ABX.md`, `D-LOG.md` |
| 5 | **Le cimetière des bonnes idées** | Les impasses chiffrées : TNS, modèle 2 de MPEG, PVQ, Haar (le `tf_change` d'Opus), masquage temporel, débit variable, intensité stéréo ; pourquoi une idée « évidente » ne rapporte rien quand le reste est déjà bon | README, `H-LOG.md`, `docs/V4-IDEAS.md` |
| 6 | **Du PC au baladeur** | Un décodeur en entiers seulement : virgule fixe et erreur de 0,05 LSB, Cortex-M3 sous QEMU, 59 MHz sur l'appareil, et le fuzzing qui trouve un défaut en 20 secondes | `docs/PORT.md`, `C-LOG.md`, `F-LOG.md` |

Les billets 4 et 5 sont les plus originaux (rares ailleurs) ; le 1 est le socle des autres.

Adopte un ton avec beaucoup d'autodérision, rédige à la première personne, tu as le droit d'utiliser un peu de vulagarité.


## Billet 1 : « Anatomie d'un codec moderne, en le construisant »

Environ 3 000 à 3 500 mots, 7 figures. Public : développeurs curieux, sans prérequis en
traitement du signal.

### 0. Accroche

J'ai réalisé le portage du codec Ogg Vorbis et Ogg Opus sur le Echo Mini de Snowsky.
Pendant se portage, j'ai fait fasse à deux problémes lié au hardware du Echo Mini. Il est motorisé par 
un Cortex-M3 qui n'est pas doté d'une unité en virgule flotante et son coeur B dédié à l'audio n'a accès
en directe qu'a très peu de RAM.

Ogg Vorbis utilise des codebook et des tables de iMDCT (inverse Modified Discrete Cosine Transform, MDCT inverse)
qui prennent beaucoup de place en mémoire et il est donc nécessaire de les étallés sur deux banques mémoires.
Cela laisse très peu de place pour avoir des tampons ou des anneaux d'entrée et de sortie. Le codec d'origine 
trichait en utilisant l'option de compilation low_memory qui dégradé de manière audible la qualité.

Ogg Opus n'utilise pas de codebook, mais PVQ (Pyramid vector quantization) c'est une technique compliquée pour
encoder des vecteurs unitaire de dimension N de manière compacte. Honnêtement, j'ai pas comprit grand chose 
au sujet de leur fonctionnement.

Un autre point important, le Echo Mini comme beaucoup de balladeur embarque des puces d'accélération hardware.
Il fait quasiment tout la partie synthèse d'un MP3 en hardware (on s'en fiche un peu). Mais il peut faire 
des opérations plus lourd qu'il serait interessant d'utiliser FFT/iFFT, iMDCT, notamment pour le AAC et le Vorbis.
Sur Tremor l'implémentation à virugle fixe du Vorbis, l'iMDCT est 4 fois plus rapide qu'en logiciel.

Vorbis n'en profite pas car ses paquet n'ont pas les mêmes taille que celle de l'AAC et tous doit être faite en soft.

Je me suis donc lancé dans le défit un peu fou d'écrire mon propre codec audio avec le cahier des charge suivant:
- On ne cherche à faire que du transcodage de CD pour une écoute sur balladeur. Pas de vidéo à 48Khz, de conf call
  de perte de paquet à cause du réseau, de faible latence, etc.
- Virgule fixe, parce que le hardware n'a pas de FPU
- En mesure d'utiliser les accélérateurs hardware
- Vorbis et Opus ont des conceptions parfois un peu tordus pour contourner les brevets logiciels de l'époque.
  Ces brevets ce sont éteint, on peut donc faire simple.
- Viser la transparent sur un écoute CD entre 128Kbps à 160Kbps soit entre les perf de Opus et Vorbis

Pour rigoler j'ai appelé le projet Mule, parce que c'est un codec hybride entre Vorbis, Opus et AAC.

### 1. Le principe : jeter ce qu'on n'entend pas (≈ 300 mots)

- Sans perte (FLAC) contre perceptif : on ne reproduit pas le signal, mais ce qu'on en perçoit.
- Les trois idées qui font tout : passer en fréquences, savoir ce qui est masqué, mettre le
  bruit de quantification juste sous ce seuil.
- **Figure 1** : schéma encodeur / décodeur, briques nommées avec leur origine (AAC, Vorbis,
  Opus : le tableau « What it is made of » du README, en image).

### 2. Couper le temps : trames et fenêtres (≈ 350 mots)

- Trames de 1 024 échantillons (23,2 ms) qui se recouvrent de moitié ; fenêtres « Vorbis » à
  puissance complémentaire.
- Le dilemme temps-fréquence : une fenêtre longue de 2 048 points voit bien les fréquences mais
  étale une attaque, d'où les **8 blocs courts de 256 points** et le détecteur de transitoires
  (énergie au-dessus de 3 kHz qui saute de 10 dB).
- Le pré-écho expliqué par l'exemple des castagnettes.
- **Figure 2** : une attaque de castagnette codée en fenêtre longue puis en blocs courts (forme
  d'onde et bruit de codage étalé ou contenu).

### 3. Passer en fréquences : la MDCT (≈ 350 mots)

- L'intuition : 2 048 échantillons deviennent 1 024 coefficients, et le recouvrement annule les
  artefacts (TDAC), sans formule.
- Pourquoi pas la FFT : réelle, échantillonnée de façon critique, recouvrement sans couture.
- **Figure 3** : spectre MDCT d'une trame de trompette avec les **22 bandes** superposées,
  étroites dans les graves, larges dans les aigus ; l'échelle des Bark, ce que l'oreille sépare.

### 4. Séparer l'énergie de la forme (≈ 400 mots)

- L'idée de CELT / Opus : coder d'abord l'énergie de chaque bande (pas de 1,5 dB), puis la
  « forme » normalisée.
- Pourquoi c'est malin : même si la forme est grossière, **l'énergie reste juste**. L'oreille
  pardonne une forme approximative, pas un trou d'énergie.
- La prédiction des énergies (trame précédente, bande voisine) : annoncée, détaillée au billet 3.
- **Encadré** : une bande sans bits est remplie de bruit au bon niveau (*noise filling*) ; à
  128 kb/s, cela ne touche presque que les bandes au-dessus de 16 kHz.

### 5. Le cœur : le masque psychoacoustique (≈ 600 mots)

- Masquage simultané : un son fort cache les sons faibles voisins ; la fonction d'étalement en
  dB/Bark.
- Tonalité : un son pur masque moins qu'un bruit ; MULE retire au seuil 5,5 dB (bruit) à
  14,5 + z dB (tonal), d'après la platitude spectrale.
- Seuil absolu d'audition, et les corrections empiriques qui ont payé : +10 dB de marge sous la
  bande 8, des masques **raie par raie dans les graves** (jusqu'à +0,2 d'ODG sur un orchestre),
  le contrôle du pré-écho repris d'AAC.
- **Figure 4** (la figure clé) : pour une trame, le spectre du signal, le seuil de masquage et
  le bruit de codage après quantification, juste en dessous.
- À retenir : *l'encodeur ne cherche pas à reproduire le signal, il cherche à cacher son
  erreur*.
- Renvoi au billet 5 : modèle 2 de MPEG, masquage temporel, essayés sans succès.

### 6. Distribuer les bits : l'allocation (≈ 400 mots)

- Du masque au pas de quantification : pour chaque bande, le pas qui place son bruit au niveau
  du masque.
- La quantification en treillis, nommée seulement (billet 2).
- Le réglage débit-distorsion : essayer a−1, a, a+1 en comptant les vrais bits (l'idée du
  lagrangien λ, sans formule).
- Le débit variable : chaque trame vise la même qualité et prend ce qu'il lui faut ; redistribuer
  autrement ne rapporte rien (mesuré, billet 5).
- **Figure 5** : bits par bande, sur une trame et sur un morceau : où va le budget.

### 7. La stéréo : deux canaux pour le prix d'un et demi (≈ 300 mots)

- L/R ou M/S décidé bande par bande, selon le moindre coût en entropie perceptuelle ; 41 % des
  coefficients en M/S sur `dev`.
- Ce qu'on n'a pas fait et pourquoi : l'intensité rapporterait au plus 2 à 3 % à 128 kb/s, et
  Opus la réserve aux bas débits.
- **Figure 6** : carte temps-fréquence des choix M/S sur un extrait.

### 8. Mettre en boîte : codage entropique et conteneur (≈ 250 mots)

- Les symboles passent dans un codeur rANS à 134 modèles adaptatifs : une phrase, et l'annonce
  du billet 3 (« c'est là que se gagnent 50 % des bits »).
- Paquets de 4 trames, paquet clé toutes les 0,93 s pour la recherche, conteneur Ogg comme
  Vorbis et Opus ; la lecture sans blanc entre pistes vient gratuitement.

### 9. Le décodeur, en miroir (≈ 200 mots)

- Il ne fait que lire, sans psychoacoustique : d'où l'asymétrie avec l'encodeur (4 fois le temps
  réel d'un côté, quelques MHz de l'autre).
- Il ne connaît que des entiers, au bit près du PC au baladeur : teaser du billet 6.

### 10. Conclusion (≈ 250 mots)

- Le tableau contre Opus et Vorbis à 128 et 160 kb/s, honnête : Opus devant sur PEAQ basique,
  MULE devant sur les autres métriques, tout se joue en centièmes.
- Le message : rien n'est magique, chaque brique rapporte des chiffres précis.
- **Figure 7** : courbes débit / qualité de MULE v2, MULE v3, Opus et Vorbis.
- Annonce du billet 2 (le treillis) ; lien vers le dépôt GitHub (s'il est public d'ici là).

### À produire pour le billet 1

- Figures 3 à 7 générées depuis les outils et CSV existants (extraits SQAM) ; figures 1 et 2
  à dessiner (schémas).
- Exemples sonores facultatifs (castagnette en fenêtre longue puis en blocs courts, exagérée à
  bas débit pour que la différence s'entende).
- Une passe de vérification : chaque chiffre relié à son journal.


## Billet 2 : « Quantifier en treillis, ou comment diviser un pas par deux sans payer »

Environ 3 000 à 3 500 mots, 7 figures. Même public et même ton que le billet 1 (première
personne, autodérision). Fil conducteur : l'idée qui a le plus rapporté au projet est la plus
vieille, et elle vient des modems.

### 0. Accroche (≈ 250 mots)

- Rappel du billet 1 : arrondir, c'est ajouter du bruit (D²/12) ; diviser le pas par deux enlève
  6 dB de bruit, mais coûte environ un bit par coefficient.
- La promesse : la TCQ obtient presque la finesse du demi-pas au prix du pas entier.
- Le paradoxe : le plus gros gain mesuré du projet (+0,06 puis +0,036 d'ODG) vient d'une idée de
  1990, présente dans JPEG 2000, absente des codecs audio grand public (à vérifier).

### 1. Le problème : arrondir coûte cher (≈ 300 mots)

- Le quantificateur scalaire : une grille régulière, une erreur entre −D/2 et +D/2, chaque
  coefficient arrondi seul.
- La limite théorique : à haut débit, quantifier plusieurs nombres ensemble gagne au plus
  1,53 dB sur le scalaire (gain de granularité) ; la TCQ à 8 états en récupère environ 1 dB, sans
  dictionnaire (au contraire de la quantification vectorielle de Vorbis).
- **Figure 1** : la grille scalaire au pas D et la zone d'erreur ±D/2.

### 2. L'astuce : deux règles graduées qui s'entrelacent (≈ 500 mots)

- Niveaux au demi-pas (k·D/2), répartis en 4 familles selon k modulo 4 (D0 à D3).
- Deux unions : k pairs (D0 ∪ D2), k impairs (D1 ∪ D3). Chacune a un pas de D, donc coûte comme
  le scalaire ; décalées d'un demi-pas, elles forment ensemble la grille fine.
- La règle du jeu : à chaque coefficient, une seule des deux règles graduées est permise, et
  c'est le choix précédent qui décide laquelle. Le décodeur la retrouve à partir des valeurs
  déjà décodées : aucune information en plus.
- Détail : l'union impaire n'a pas de zéro, le signe est donc toujours envoyé.
- **Figure 2** (Excalidraw) : la droite des niveaux colorée par famille, les deux règles
  graduées au-dessus.

### 3. Le treillis : 8 états et des règles de passage (≈ 400 mots)

- La machine à états : depuis l'état t, la branche br mène à (2t + br) mod 8, avec une famille
  imposée (tables de JPEG 2000 partie 2).
- L'origine : la modulation codée en treillis d'Ungerboeck (modems), puis la TCQ de Marcellin et
  Fischer (1990).
- Le coût au décodeur : une table de 16 entrées, une parité, un décalage par coefficient.
- **Figure 3** (Excalidraw) : le treillis à 8 états sur quelques coefficients, branches
  étiquetées par famille.

### 4. Viterbi : choisir tout le chemin d'un coup (≈ 450 mots)

- Pourquoi on ne peut pas décider coefficient par coefficient : un bon choix maintenant peut
  condamner le suivant.
- Viterbi : pour chaque état, le meilleur chemin qui y arrive (erreur² + λ × bits), puis on
  remonte le meilleur. Analogie du GPS et des carrefours.
- Le réglage de λ (`dev`) : λ = 0, +4,8 % de débit et 15 régressions ; λ = 0,3, l'optimum, une
  régression ; λ = 1, 59 régressions (sauter des niveaux s'entend sur les sons tonals).
- Coût à l'encodeur : environ 2 fois le scalaire.
- **Figure 4** : une vraie bande d'un extrait SQAM, depuis la trace de l'encodeur : valeurs à
  quantifier, arrondi scalaire, niveaux choisis par la TCQ, chemin des états.

### 5. Ce que ça a rapporté : le format v2 (≈ 350 mots)

- Sur `test`, à débit égal : +0,063 d'ODG à 128 kb/s, +0,037 à 160, aucune régression ; l'écart
  avec Opus en ODG de base diminue d'environ un tiers.
- ABX à 160 kb/s : scalaire transparent sur 5 extraits critiques sur 6 (triangles à 12/16, au
  seuil), TCQ sur 6 sur 6.
- La concurrente, la PVQ d'Opus : perdante, surtout sur les sons tonals (triangles −0,64,
  glockenspiel −0,43).
- **Figure 5** : ODG à 128 et 160 kb/s, scalaire, TCQ, PVQ, Opus, Vorbis.

### 6. La v3 : plus d'états, et un seul Viterbi pour toute la trame (≈ 600 mots)

- Le défaut de la v2 : le treillis repartait de l'état 0 à chaque bande, et il lui fallait trois
  coefficients pour ouvrir ses chemins, dans des bandes de 8.
- Le simulateur (1,25 bit par coefficient) : enchaîner naïvement les bandes fait moins bien
  (−0,14 dB) ; tout le gain vient du Viterbi conjoint qui choisit la fin d'une bande avec le
  début de la suivante ; puis des états (32 en chaîne +0,17 dB, 64 +0,23 dB).
- Dans le codec (`dev`) : 8 états +0,015, 16 +0,026, 32 +0,037, 64 +0,040 ; sur `test` +0,036
  avec l'alphabet de 8 symboles.
- L'aparté des 48 états : moins bien que 32 (+0,12 dB contre +0,17) ; les bons treillis viennent
  des codes convolutifs, qui aiment les puissances de deux.
- Coûts : 256 octets d'état au décodeur ; à l'encodeur, un Viterbi 8 fois plus large (1,9 fois le
  temps réel), ramené à environ 4 fois en estimant les choix d'allocation sur 8 états.
- **Figure 6** : gain du simulateur selon le nombre d'états, avec et sans chaîne.
- **Figure 7** : gain en ODG dans le codec selon le nombre d'états (rendements décroissants).

### 7. Ce qui n'a pas marché autour du treillis (≈ 250 mots)

- Des contextes qui connaissent la parité de l'état : −0,42 % de débit, sous le seuil de 1 %,
  pour 3 Kio de RAM.
- Un treillis plus riche (parité + classe de bande) : la classe relève des contextes.
- La TCVQ : environ 0,5 dB de plus en théorie, un décodeur bien plus lourd.
- CMA-ES autour du treillis de 64 états : +0,004, non confirmé sur `test`.

### 8. Conclusion (≈ 200 mots)

- Une idée de 35 ans, venue d'ailleurs (modems, image), a rapporté plus que la psychoacoustique.
- Question ouverte, posée honnêtement : pourquoi aucun codec audio grand public ne l'utilise ?
- Annonce du billet 3 : la compression vient du modèle, pas du codeur.

### À produire pour le billet 2

- Figures 2 et 3 : schémas Excalidraw (`fig1_pipeline.py` et `render.mjs` comme modèle).
- Figure 4 : trace de l'encodeur (niveau, valeur avant quantification, état du treillis).
- Figures 5 à 7 : `bc_test.csv`, `rd_dev.csv`, les CSV `c*_dev`, `eval/tcq_sim.py`.
- À vérifier : la borne de 1,53 dB, la date d'Ungerboeck, la « quantification dépendante » de
  VVC (citée dans le README), l'absence de la TCQ dans les codecs audio grand public.

## Billet 5 : « Le cimetière des bonnes idées », notes pour le plan

Pas encore de plan détaillé ; matériau rassemblé au fil des discussions.

### Les deux stratégies d'Opus contre les transitoires, et pourquoi MULE n'en a gardé qu'une

La spécification d'Opus (RFC 6716, §4.3.4.5) en annonce deux :

1. **plusieurs petites MDCT au lieu d'une grande** : MULE l'a, ce sont ses 8 blocs courts de
   256 points (disposition d'AAC) ; CELT fait de même avec son drapeau de transitoire ;
2. **le changement dynamique de résolution temps-fréquence** (`tf_change`) : une transformée de
   Haar, bande par bande, à l'intérieur d'une trame. Dans une trame de MDCT courtes, elle rend de
   la finesse en fréquence aux bandes graves ; dans une trame longue, elle rend de la finesse en
   temps aux bandes qui en ont besoin. MULE choisit sa résolution trame par trame, pour toutes
   les bandes à la fois ; ses groupes de blocs courts (AAC) regroupent les informations de bord,
   pas la résolution de la transformée.

Ce qui a été mesuré :
- Haar dans les bandes des trames longues (le second sens de `tf_change`, `eval/results/H-LOG.md`) :
  +0,026 d'ODG sur le rock à niveau fixe, des bits perdus partout ailleurs ; avec un niveau choisi
  par trame, +0,003 sur `dev`, sous le seuil de +0,01 : abandonné avant le gel de la v3 ;
- Haar dans les trames courtes (point 5 de `docs/V3-IDEAS.md`) : jamais codé, car le diagnostic
  trame par trame (`eval/results/D-LOG.md`) a montré que l'écart restant avec Opus ne vient pas des
  attaques, et que plus de blocs courts fait baisser la note.

Le message : un outil qui marche chez Opus (trames courtes, bas débit) ne rapporte rien dans
MULE (trames longues, 128 kb/s). Une idée n'est bonne que pour le codec qui en a besoin.

