# Idées pour un format v3

Le format v2 est figé : le décodeur du firmware le lit, et tous les gains récents (axes 1 à 3) ont été obtenus côté encodeur. Cette liste rassemble ce qui demanderait de changer le format. Une v3 regrouperait plusieurs de ces changements d'un coup, avec de nouvelles CDF initiales (nouvel identifiant de table) et une nouvelle écoute ABX.

**Compatibilité** (décision du 17/11/2026) : la v3 peut rompre avec la v2. MULE est encore un prototype, aucune bibliothèque réelle n'est encodée, et le décodeur du firmware ne gardera qu'un seul format. Quand le code sera mûr, MULE aura son propre dépôt GitHub.

Critères pour le cœur B de l'Echo Mini, par ordre d'importance : **mémoire** du décodeur (la priorité), qualité, puis calcul (pas prioritaire pour l'instant).

## Gains probables, coût faible

1. **Bande passante jusqu'à 22 kHz.** La dernière bande s'arrête au coefficient 928 (19,95 kHz), alors qu'Opus monte à environ 20,4 kHz. C'est inaudible, mais PEAQ retire environ **0,025 d'ODG à 128 kb/s** pour cela (`E2-LOG.md`). Il suffirait d'une 23e bande de 928 à 1024, presque toujours remplie de bruit : quelques bits par trame, aucune mémoire en plus. Testé et écarté, c'est juste une artefact de PEAQ.
2. **Niveau du bruit de remplacement transmis à part.** L'axe 2 a montré qu'abaisser de 3 dB l'énergie des bandes non codées améliore PEAQ, mais en faussant l'énergie, ce que ViSQOL semble pénaliser. Un gain de bruit codé séparément (2 bits par trame ou par groupe de bandes, par exemple 0 / −1,5 / −3 / −4,5 dB) garderait l'énergie juste tout en réglant la sonie du bruit. Coût décodeur : une multiplication par bande.
3. **Pente spectrale du bruit de remplacement.** Dans une large bande aiguë remplie de bruit, le bruit est plat, alors que le signal descend souvent vers les aigus. Une pente codée sur 2 ou 3 bits par bande remplie (ou par trame) éviterait un bruit trop brillant en haut de bande.
4. **Contextes tenant compte de l'état du treillis.** La parité de l'état TCQ est connue du décodeur et pourrait affiner le contexte des coefficients. Gain attendu modeste (le codage entropique est proche de sa limite), coût nul en mémoire.

## Gains possibles, coût moyen

5. **Résolution temps-fréquence par bande dans les trames courtes** (le `tf_change` de CELT). Dans une trame de blocs courts, les bandes graves perdent toute résolution fréquentielle. Recombiner les 8 blocs courts d'une bande (transformée de Haar ou de Hadamard) rendrait de la résolution aux graves pendant une attaque. Utile pour la voix, les percussions et le piano. Coût décodeur : quelques additions par coefficient, pas de mémoire.
6. **Blocs intermédiaires de 512 points.** Entre les trames longues (2048) et les 8 blocs courts (256), une taille de 512 traiterait mieux les attaques douces, celles qui ont résisté au contrôle de pré-écho. L'accélérateur MDCT de l'appareil gère déjà 512 points. Coût : des fenêtres de transition en plus, sans mémoire supplémentaire notable.
7. **Remplacement anti-effondrement pour les trames courtes** (l'`anti-collapse` de CELT). Quand une bande d'un bloc court est quantifiée à zéro alors que la bande a de l'énergie, injecter un peu de bruit dans ce bloc évite les trous temporels audibles. Coût décodeur : faible.
8. **Énergies plus fines dans les graves.** Le pas de 1,5 dB est le même partout. Un raffinement d'un bit dans les bandes 0 à 7 (pas de 0,75 dB), à la manière de l'énergie fine de CELT, aiderait les sons graves tenus, là où l'axe 1 a trouvé le défaut des triangles.

## Plus lourds, à n'envisager que si un besoin se confirme

9. **Prédiction à long terme (hauteur)** pour la voix et les sons tonals stables, comme le pré-filtre de hauteur d'Opus. Gain réel sur ces signaux, mais il faut un historique de sortie (environ 4 Kio par canal) et un filtre par échantillon : contraire à la priorité mémoire.
10. **Stéréo d'intensité dans les aigus** aux bas débits : une seule bande codée, et un angle par bande. Utile sous 128 kb/s seulement. La rotation stéréo par bande avait été mesurée en P4 sans gain (−0,16 % d'entropie perceptuelle).
11. **Autres fréquences** (48 kHz) **et mono.** Inutile pour une bibliothèque en 44,1 kHz, mais le mono pourrait servir aux livres audio et podcasts (moitié de mémoire pour les tampons de synthèse).

## Côté décodeur, sans changement de qualité

12. **Mémoire.**
    - L'index inter-trame peut passer de 16 à 8 bits, saturé à 255 au lieu de 65 535 : −2 Kio, au prix d'un contexte un peu moins précis pour les très grandes valeurs.
    - Un décodage trame par trame, plutôt que paquet par paquet, réduirait le tampon PCM du codec de 32 Kio à 4 Kio. Ce changement n'est pas un changement de format : il peut être fait dans le décodeur v2.
13. **Coût du décodage entropique** (63 % des instructions) :
    - mise à jour des CDF moins fréquente (par exemple tous les 2 symboles) ;
    - moins d'entrées par CDF (alphabets de 8 au lieu de 16, avec échappement) ;
    - modèles statiques pour les flux peu sensibles (type de bloc, alpha, stéréo).

    À mesurer en débit perdu contre millions d'instructions gagnés, quand la charge du cœur B deviendra une priorité.
14. **En-têtes de paquet.** L'état rANS initial coûte 4 octets par paquet. En v2, passer à 8 trames par paquet le divise déjà par deux sans changer le format (−0,17 kb/s), mais double le tampon PCM du firmware. Une v3 pourrait le réduire à 2 ou 3 octets, avec un état initial normalisé.

## Ce que disent les mesures (fin de l'axe 2, `eval/results/E2-LOG.md`)

L'écart restant avec Opus en ODG de base (0,05 à 128 kb/s, 0,03 à 160 kb/s sur `dev`) tient à :
- la distorsion concentrée dans certaines trames : attaques, voix, rock dense et saturé ;
- la bande passante (+0,024 à 128 kb/s).

Tous les leviers de l'encodeur seul ont été essayés. S'y ajoute une piste :

15. **Bandes aiguës plus étroites.** Entre 6 et 10 kHz, les bandes font 64 à 144 coefficients (1,4 à 3 kHz) avec une seule énergie, et le bruit y dépasse le masque sur le rock dense. Couper les bandes 17 à 21 en deux (5 bandes de plus) affinerait l'énergie et l'allocation dans les aigus. Coût : quelques bits d'énergie par trame, et 10 entrées de plus dans les tables d'état (négligeable).

## Ordre proposé

Si une v3 est lancée : **1 + 2 + 3** d'abord (simples, sans mémoire, gain PEAQ direct), puis **5 + 7** (les attaques, point faible restant), puis **15, 6 et 8** selon les mesures. Les points 9 à 11 seulement sur demande. Le point 12 (trame par trame) peut être fait dès maintenant en v2.

## Pistes ajoutées (discussion du 18/11/2026)

### À mesurer d'abord, sans changer le format

- **M1. Intervalle des paquets clés.** `keyframe` est un réglage de l'encodeur ; l'octet 17 de l'en-tête n'est qu'indicatif. Comparer 40, 80 et 160 trames : débit gagné (réinitialisation des CDF, `valide = 0`) contre temps de recherche (30 à 40 ms aujourd'hui).
- **M2. Borne du modèle harmonique.** Bits de coefficients dans les trames longues avec `valide = 0` (premier paquet après une clé, trames suivant des blocs courts) contre `valide = 1`. Le contexte inter-trame capte déjà les harmoniques stables : le gain possible du point 20 se trouve dans cet écart, et dans le vibrato.
- **M3. Allocation optimisée sur toute la trame.** Le choix RD a−1 / a / a+1 (`rd_lambda`, `core/enc.c`) se fait bande par bande, de façon gloutonne. Or le choix pour la bande b change les queues de contexte de la bande b+1 et, en mode 0, le coût différentiel de `a[b+1]`. Un Viterbi sur les bandes (3 états par bande) trouverait l'optimum de la trame. Encodeur seul.
- **M4. Viterbi sur les décisions de trame** (type de bloc, α, M/S), qui ont de vraies dépendances d'une trame à l'autre (énergies et allocations prédites). Encodeur seul.
- **M5. Coût futur des contextes dans le Viterbi TCQ** : tenir compte de l'effet de `u` sur le contexte inter-trame de la trame suivante. Gain attendu faible, puisque seule une statistique se propage. En dernier.
- **M6. Réglage joint des paramètres de l'encodeur** (`tcap_db`, `mid_db`, `fft_noise_db`, `rd_lambda`, `tcq_lam`), par CMA-ES ou optimisation bayésienne sur `dev`. On garde la règle actuelle : accord de plusieurs métriques sur `test`, puis ABX. Risque : suroptimiser les angles morts des métriques.
- **M7. Mesures préalables aux points 22 et 23** : entropie des résidus d'énergie avec une interpolation entre trames voisines contre la prédiction actuelle (α) ; entropie conditionnelle des index avec un contexte des deux côtés (n−1 et n+1) contre le contexte actuel.
- **M8. Contexte inter-trame lissé.** Mesurer l'entropie conditionnelle des index avec `|y_prev[k]|` contre une moyenne glissante exponentielle `m[k] = α·m[k] + (1−α)·|y[k]|`, pour α = 0,5 ; 0,7 ; 0,85, ainsi qu'avec le maximum des deux. Sur un signal synthétique (notes tenues), environ 7 % des bits de coefficients en moins à α = 0,85 ; à confirmer sur `dev`, où le gain sera plus faible.

### Changements de format

16. **Continuité de l'état TCQ entre bandes.** Aujourd'hui `t = 0` au début de chaque bande (spec §5.3). Le premier coefficient est donc forcé dans l'union paire, et ça pèse sur les bandes 0 à 7 (8 coefficients en trame longue), là où se trouvait le défaut des triangles. Garder l'état fait du treillis une seule chaîne par trame. Coût décodeur : nul.
17. **Plus d'états dans le treillis** (16, 32, 64, voire 256). Gain de granularité théorique : environ 1 dB à 8 états, 1,36 dB à 256 (Marcellin et Fischer, cité par Kudryashov). On en a obtenu à peu près la moitié de la théorie à nos débits. Coût décodeur : une table plus grande. Coût encodeur : Viterbi proportionnel au nombre d'états, à contenir avec les accélérations de la TCQ de VVC (départ retardé, élagage, seuils ; arXiv 2008.11420). Faisable d'abord avec le Viterbi Python.
18. **Codage binarisé des coefficients, à la VVC.** Drapeaux de significativité, de parité et de dépassement de seuil, puis reste en Golomb-Rice. Contextes choisis selon l'état du treillis (ce qui reprend le point 4). Une probabilité mise à jour par symbole binaire au lieu de 15 entrées de CDF : moins de calcul (63 % des instructions vont au décodage entropique, point 13) et moins de mémoire pour les modèles. À mesurer : débit perdu face aux CDF à 16 symboles entraînées, contre instructions et octets gagnés. Pourrait financer le point 17.
19. **Repliement guidé par l'encodeur, à la IGF** (MPEG-H), pour les bandes à `a = 0` :
    - un bit bruit ou copie par bande ;
    - 1 à 2 bits de décalage de source, choisi par corrélation croisée et stabilisé dans le temps ;
    - un niveau de blanchiment ;
    - copie normalisée depuis le tampon de coefficients de la trame, mise à l'énergie de la bande.

    Attention à la leçon de P2 : du bruit ou une copie tonale entre des partiels s'entend. La décision doit donc revenir à l'encodeur. Coût décodeur : une normalisation par bande, sans mémoire. Prioritaire si l'on vise des débits inférieurs à 128 kb/s.
20. **Modèle harmonique dans les contextes des coefficients** (comme dans le TCX d'EVS) : une hauteur transmise en quelques bits par trame, et des contextes qui attendent des valeurs fortes aux positions harmoniques. Variante sans information transmise : hauteur estimée par le décodeur sur les `|y|` de la trame précédente (calcul en plus). Selon le résultat de M2.
21. **Composantes tonales façon ATRAC3** : position et quelques coefficients (au plus 8), retirés avant la quantification et ajoutés avant l'IMDCT. Elles aplatissent le résidu des bandes dominées par un pic et protègent la source du repliement (point 19). Coût décodeur : des additions. Priorité basse à 128 kb/s.
22. **Ordre hiérarchique des informations annexes dans un paquet.** On code les énergies (et éventuellement l'allocation) des trames 0 et 3, puis celles des trames 1 et 2, prédites à partir de leurs deux voisines. C'est l'idée des B-frames appliquée aux seules informations annexes. Mémoire négligeable, IMDCT dans l'ordre normal. Selon M7.
23. **Contexte inter-trame des deux côtés** (index de n−1 et de n+1). Environ 4 Kio de plus pour garder les index de n+1 : contraire à la priorité mémoire. Seulement si M7 montre un gain net.
24. **Rafraîchissement progressif** au lieu d'une réinitialisation complète au paquet clé, comme les groupes de prédicteurs d'AAC Main : la prédiction inter-trame et celle des énergies sont coupées sur un groupe de bandes différent à chaque trame. Les CDF adaptatives restent réinitialisées d'un coup. Seulement si M1 montre que les paquets clés coûtent cher.
25. **Dictionnaire de 2 à 4 découpages en bandes**, choisi par trame sur 1 ou 2 bits, avec une correspondance fixe entre découpages pour garder la prédiction des énergies. Il complète le point 15, plutôt qu'un maillage temps-fréquence libre.
26. **Haar sur plusieurs niveaux à l'intérieur des bandes**, en trame longue comme en trame courte (une forme de quadtree, qui généralise le point 5). Décision RD de l'encodeur, quelques additions par coefficient au décodeur.
27. **Moyenne glissante à la place de `y_prev`** (selon M8) : même tampon de 16 bits, une multiplication-addition par raie, même remise à l'échelle et mêmes règles de validité (remise à zéro aux paquets clés, cas des trames courtes). Elle corrige les oscillations de phase de la MDCT et le bruit d'un tirage unique, au prix d'un retard sur les attaques. Variante : α par classe de bandes.

### Écartées après discussion

- **TW-MDCT** (USAC) : il faut une estimation de hauteur et un rééchantillonnage en sortie, trop chers pour le décodeur.
- **Synthèse sinusoïdale paramétrique** (HILN, SSC) : oscillateurs coûteux, et elle n'atteint pas la transparence.
- **Maillage temps-fréquence libre ou paquets d'ondelettes** : il faut décrire le maillage, les transitions entre trames sont délicates, et la prédiction des énergies et les contextes ne marchent plus.
- **B-frames ou treillis bidirectionnel au décodeur** : la MDCT se prédit mal d'une trame à l'autre, le réordonnancement coûte de la mémoire, et l'anticipation est déjà gratuite dans le Viterbi de l'encodeur.
- **Treillis dans le temps** (raie par raie, d'une trame à l'autre) : le gain de granularité dépend du nombre d'états, pas de la direction. Le point 16 règle la seule perte liée à la longueur.
- **PVQ avec projection de Duda** : déjà mesurée, moins bonne que A (`VARIANTS-BC.md`).

### Ordre proposé pour ces pistes

1. **Mesures gratuites** : M1, M2, M3, M8.
2. **Treillis** : 16, puis 17 (Python d'abord).
3. **Décodeur** : 18, à mesurer en débit contre instructions et mémoire ; il libère du calcul pour 17.
4. **Débits plus bas** : 19 et 20, si l'objectif descend sous 128 kb/s.
5. **Le reste** (21 à 26) selon les mesures, notamment M7 et M8.

### Références

**Treillis et codage des coefficients (16, 17, 18, M3, M5)**
- Marcellin et Fischer, « Trellis coded quantization of memoryless and Gauss-Markov sources », IEEE Trans. Inf. Theory 38(1), 1990, p. 82-93. L'article fondateur de la TCQ.
- Kudryashov, « Linear code-based vector quantization for independent random variables », arXiv 0805.2379 : gain de granularité de 1,36 dB avec un treillis à 256 états.
- Cappellari, « Trellis-Coded Quantization Based on Maximum-Hamming-Distance Binary Codes », arXiv 0704.1411 : changer les transitions du treillis ne rapporte rien, les gains viennent du codage entropique.
- Schwarz et al., « Quantization and Entropy Coding in the Versatile Video Coding (VVC) Standard », IEEE TCSVT 31(10), 2021, p. 3891-3906, doi:10.1109/TCSVT.2021.3072202. Accès libre (CC BY 4.0) : https://refubium.fu-berlin.de/handle/fub188/33130. **Référence principale du point 18** : quantification dépendante, contextes, binarisation.
- « Low Complexity Trellis-Coded Quantization in Versatile Video Coding », arXiv 2008.11420 : accélérations de l'encodeur (départ retardé, élagage, seuils) ; résultats en configurations AI et RA des CTC du JVET.
- Contextes choisis selon l'état du treillis : brevet US 11184642.

**Reconstruction spectrale (19, 20, 21)**
- Disch et al., « Intelligent Gap Filling in Perceptual Transform Coding of Audio », 141e convention AES, Los Angeles, 2016, papier 9661. La présentation de référence de l'IGF.
- IGF, brevets Fraunhofer : US 10147430 (sélection des tuiles par corrélation), US 11769512 (décalage de la source), US 10236007 (blanchiment).
- Modèle harmonique d'EVS : « Harmonic model for MDCT based audio coding with LPC envelope », EUSIPCO 2015 (Fraunhofer).
- HVQ d'EVS (Ericsson, « Harmonic Vector Quantization ») : pics spectraux et plancher de bruit au lieu d'enveloppe et résidu.
- ATRAC3, composantes tonales : décodeur `libavcodec/atrac3.c` ; Sony, « Technologies in ATRAC3 ».
- Opus/CELT, RFC 6716 §4.3 : repliement et spreading, `tf_change`, anti-collapse (aussi pour les points 5 et 7).

**Contextes et modèles de variance (M8, 27)**
- Duda, « Adaptive exponential power distribution with moving estimator for nonstationary time series », arXiv 2003.02149 : mise à jour par moyenne glissante de σ^κ. **Base de M8.**
- Duda, « Improving distribution and flexible quantization for DCT coefficients », arXiv 2007.12055 : distribution EPD avec κ ≈ 0,5, prédiction de σ par le contexte.
- Ozerov, Liutkus, Badeau, Richard, « Coding-Based Informed Source Separation: Nonnegative Tensor Factorization Approach », IEEE TASLP 21(8), 2013 : la NMF comme modèle de variance pour la quantification.

**Pavage temps-fréquence (5, 25, 26)**
- Niamut et Heusdens, « Flexible frequency decompositions for cosine-modulated filter banks », ICASSP 2003 ; « Subband merging in cosine-modulated filter banks », IEEE Signal Processing Letters, 2003.
- Valin, brevet US 9008811 : résolution temps-fréquence adaptative par bande (`tf_change`).

**Accès aléatoire et prédiction entre trames (22, 23, 24, M1)**
- AAC Main, groupes de réinitialisation des prédicteurs : ISO/IEC 13818-7 ; `libavcodec/aacdec` ; note MPEG sur les reprises de décodage (https://mpeg.chiariglione.org/node/301).
- USAC et MPEG-H : `usacIndependencyFlag`, `AudioPreRoll()` (Immediate Playout Frames) ; brevets Fraunhofer US 10614824 (AudioPreRoll) et Dolby US 12315524 (IPF).

**Évaluation**
- Torcoli, Kastner, Herre, « Objective Measures of Perceptual Audio Quality Reviewed: An Evaluation of Their Application Domain Dependence », IEEE/ACM TASLP 29, 2021, doi:10.1109/TASLP.2021.3069302, arXiv 2110.11438.
- Kastner et Herre, « An Efficient Model for Estimating Subjective Quality of Separated Audio Source Signals », WASPAA 2019, p. 95-99 (le 2f-model). Paramètres pour PQevalAudio : https://audiolabs-erlangen.com/resources/2019-WASPAA-SEBASS.
- Chinen et al., « ViSQOL v3: An Open Source Production Ready Objective Speech and Audio Metric », QoMEX 2020, arXiv 2004.09584 (voir ses limites : silences, monotonie, faible sensibilité sur la musique).
- Zimtohrli : https://github.com/google/zimtohrli ; arXiv 2509.26133.
- Schoeffler et al., « webMUSHRA — A Comprehensive Framework for Web-based Listening Tests », Journal of Open Research Software 6(1), 2018, doi:10.5334/jors.187.
