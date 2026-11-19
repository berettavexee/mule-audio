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
| 5 | **Le cimetière des bonnes idées** | Les impasses chiffrées : TNS, modèle 2 de MPEG, PVQ, Haar, masquage temporel, débit variable, intensité stéréo ; pourquoi une idée « évidente » ne rapporte rien quand le reste est déjà bon | README, `H-LOG.md`, `docs/V4-IDEAS.md` |
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
