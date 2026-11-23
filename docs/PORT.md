# Portage sur l'Echo Mini (cœur B, Cortex-M3)

## Cible

Le cœur B (HiFi) de l'Echo Mini :
- Cortex-M3 **sans FPU**, à 100 MHz ou plus ;
- 128 Kio de code (HIGHRAM0) et 148 Kio de données (HIGHRAM1) ;
- accélérateur `HIFIACC` : FFT complexes de 64 à 512 points, entrée en ordre bit-inversé, sans mise à l'échelle.

Le Vorbis du firmware s'en sert déjà pour son IMDCT par la méthode en N/4 (`fw/hifi/hififft.c`). Le firmware se lie sans libm (`-nostdlib -lgcc`).

## 6. Décodeur en virgule fixe (`core/dec.c`)

- **Un seul décodeur, en entiers**, référence du format et décodeur du cœur B (`mule_dec_*`, sortie int16, ni flottant ni libm). Le décodeur flottant qui servait de référence pendant le portage a été retiré le 17/11/2026 ; les mesures ci-dessous ont été faites contre lui.
- **Coefficients en Q24** : `X = k · 2^((Q − a + 5)/4)`, soit une mantisse prise dans une table de 4 entrées (Q30) et un décalage, calculés une fois par bande.
- **Bruit** des bandes non codées : racine carrée entière sur 64 bits et une division par bande.
- **M/S** : multiplication par 1/√2 en Q31.
- **IMDCT** :
  - pré-rotation `w = exp(−2iπ(m + 1/8)/n)`, avec la même définition que les tables `fft_tw2048`/`fft_tw256` du firmware ;
  - FFT complexe de n/4 points (512 ou 64) ;
  - post-rotation et dépliage direct en quatre quarts (correspondance établie numériquement et vérifiée) ;
  - la pré-rotation divise par 2 pour laisser de la marge à la FFT sans mise à l'échelle, la post-rotation remultiplie par 2 ;
  - `fx_fft` est le remplaçant logiciel de `HIFIACC` : même ordre d'entrée, même absence de mise à l'échelle.
- **Fenêtres** : pentes en Q31 générées par `tools/gen_fx_tables.py` (`core/fx_tables.h`). Accumulateurs en int32 Q24 ; sortie `(acc + 2^8) >> 9` saturée sur 16 bits.
- **Exactitude** (mesurée pendant le portage) : par rapport au décodeur flottant d'alors, l'écart était de **1 LSB au plus**, d'environ 0,05 LSB en moyenne quadratique, et le rapport signal/écart va de 85 à 115 dB, sur tous les signaux de test et extraits mesurés. Le seek donne la même sortie que le décodage continu.

## 7. Mémoire

- **État du décodeur : 49 112 octets**, en mémoire fournie par l'appelant (`mule_dec_init`), sans allocation dynamique :

| Poste | Octets |
|---|---|
| Modèles | 4 824 |
| Accumulateur 2 × 1600 × int32 | 12 800 |
| Moitié en attente 2 × 1024 × int32 | 8 192 |
| Coefficients 2 × 1024 × int32 | 8 192 |
| Index inter-trame 2 × 1024 × uint16 | 4 096 |
| Travail : demi-IMDCT 4 Kio, FFT 4 Kio, index 2 Kio | 10 240 |

- La pile ne contient que quelques petites variables locales (moins de 1 Kio).
- L'index inter-trame est **saturé à 65 535**, ce qui est normatif (spécification §5.3) : les encodeurs en tiennent compte.
- **Code et constantes** (Cortex-M3, `-O2`) : **23,5 Kio** au total, dont environ 8 Kio de code, 4,9 Kio de CDF initiales et 11 Kio de tables de virgule fixe. Sur l'appareil, `fx_w2048`/`fx_w256` peuvent être remplacées par les `fft_tw` du firmware, et `fx_fft_tw` devient inutile avec la FFT matérielle : −6,6 Kio.
- À prévoir dans l'image du codec : un tampon de paquet de 8 Kio et un tampon PCM de 8 trames (32 Kio), soit environ 90 Kio au total sur les 148 Kio disponibles.

## 8. Mesures sous QEMU (`bench/qemu/run.sh`, machine `mps2-an385` = Cortex-M3)

Protocole :
- le décodeur en virgule fixe est compilé comme pour le cœur B (`-mcpu=cortex-m3 -mthumb -O2`) ;
- l'extrait encodé est embarqué dans le binaire ;
- les instructions sont comptées par le temporisateur CMSDK en mode `-icount shift=0` (une instruction par nanoseconde virtuelle, un tic de 25 MHz pour 40 instructions) ;
- une empreinte FNV-1a de la sortie est comparée à celle du même décodeur sur PC.

**L'empreinte est identique sur la cible et sur le PC** : la sortie est exacte au bit près.

Extrait abba, 10 s, q −12 (150,6 kb/s, 432 trames) :

| Version | Instructions par trame | dont lecture du flux | dont synthèse | Pire trame |
|---|---|---|---|---|
| première version | 1 250 000 | 816 000 | 435 000 | 1 420 000 |
| **optimisée** | **922 000** | 584 000 | 338 000 | 1 044 000 |
| format v3 (19/11/2026, 152,8 kb/s) | 840 050 | — | — | 951 400 |
| format v4 (21/11/2026, 155,5 kb/s) | 871 920 | — | — | 963 560 |
| format v5 (22/11/2026, 156,7 kb/s) | 888 503 | — | — | 961 720 |

Format v3 : le décodeur lit la v3 et la v2 ; 49 368 octets d'état. Il n'est pas encore porté sur l'appareil : les mesures des §9 et suivants sont celles de la v2.

Format v4 (dans `main` depuis le 22/11/2026, `docs/V4.md`) : le décodeur lit la v4, la v3 et la v2 ; 49 372 octets d'état ; code de `core/dec.c` 18 433 octets contre 16 989 en v3 (+1,4 Kio, aucune table ajoutée). Mesuré avec le même décodeur sur un flux v3 et un flux v4 du même extrait : +4,3 % d'instructions par trame sur abba à q −12, +6,6 % sur abba à q −7 (112 kb/s), +3,1 % sur Belenos à q −7 (160 kb/s) ; pire trame +2 à +3,6 %. Le surcoût vient du bruit des zéros (un tirage par coefficient nul) et du bruit en pente (une puissance de 2 par raie) : de l'ordre de 2 à 4 MHz sur le cœur B. Sortie exacte au bit près contre le PC.

Format v5 (dans `main` depuis le 22/11/2026, `docs/V5.md`) : le décodeur lit v5, v4, v3 et v2 ; 49 424 octets d'état (+52 : un modèle `nflev` et un indicateur) ; code de `core/dec.c` pour Cortex-M3 17 743 octets (`make m3size`), aucune table ajoutée. Le repliement (`fold_band`) n'a aucun tableau local ; il fait deux divisions 64 bits par coefficient replié, seulement dans les bandes sans bits des trames courtes. Mesuré sous QEMU avec le même décodeur v5 sur un flux v4 (encodeur du 22/11/2026, `bc0ebad`) et un flux v5 du même extrait, 10 s, empreintes identiques à celles du PC :

| Extrait | v4 : instructions par trame (pire trame) | v5 | écart |
|---|---|---|---|
| abba, q −12 (156,5 kb/s) | 880 401 (988 360) | 888 503 (961 720) | +0,9 % (−2,7 %) |
| abba, q −7 (112,7 kb/s) | 850 265 (956 520) | 861 719 (929 560) | +1,3 % (−2,8 %) |
| Belenos, q −7 (143,6 kb/s) | 950 450 (989 840) | 950 994 (990 160) | +0,1 % (0,0 %) |
| castagnettes, q −7 (114,9 kb/s) | 821 892 (932 640) | 832 886 (952 280) | +1,3 % (+2,1 %) |

Le surcoût (0 à 1,3 % par trame, de l'ordre de 0,5 MHz sur le cœur B) vient du repliement et du modèle du niveau de bruit, et pour partie des trames courtes plus nombreuses de l'encodeur v5 ; la pire trame bouge de −3 à +2 %. État : 49 412 octets sur la cible. Pas encore porté sur l'appareil.

Optimisations, toutes sans effet sur la sortie (empreinte identique, tests verts) :
- recherche de symbole par bornes successives, avec une multiplication par candidat ;
- mise à jour des CDF en deux boucles sans branchement, partagée avec l'encodeur ;
- calculs par bande hissés hors de la boucle des coefficients (échelle, facteur inter-trame) ;
- index des coefficients incrémental, sans division ;
- dépliage de l'IMDCT direct ;
- fenêtres traitées par plages.

**Charge** : environ 922 000 × 43,07 trames/s ≈ **40 millions d'instructions par seconde**. Avec 1,3 à 1,5 cycle par instruction sur un M3 (charges en 2 cycles, `SMULL` en 3 à 5), il faut compter **50 à 60 MHz** en FFT logicielle. La FFT matérielle retirerait environ 150 000 instructions par trame (environ 45 MHz). Mesure sur l'appareil au §9 : **59 MHz** en moyenne, avec la FFT sur `HIFIACC`.

Pistes d'optimisation restantes :
- la mise à jour des CDF, qui touche 15 entrées par symbole : on pourrait traiter deux entrées de 16 bits à la fois dans un registre de 32 bits, ou passer en assembleur ;
- le contexte inter-trame (multiplication 64 bits par coefficient) ;
- la FFT logicielle à la place de `HIFIACC`.

## 8 bis. Optimisations du 23/11/2026 : mémoire, et une variante pour Cortex-M0

Toutes exactes au bit : empreintes identiques au PC sur les 68 flux de `bench/qemu/exact.sh` (abba, castagnettes, Belenos et glockenspiel à q −12, −4 et +4, puis tous les vecteurs de test v2 à v5), `make test` vert.

**Mémoire** (la priorité du cœur B) :
- les index de la trame courante (`ycur`, lecture du flux) et la moitié gauche de l'IMDCT (`y`, synthèse) partagent leur place (une union) : −2 Kio ;
- `MULE_FFT_MEM_EXTERNAL` : la FFT de l'IMDCT travaille dans une mémoire fournie par l'appelant (`mule_dec_set_fft_mem`), sur l'appareil celle de `HIFIACC` ; plus de copie aller-retour, et −4 Kio d'état ;
- `MULE_DEC_STATE_MAX` (`mule.h`) : la taille maximale de l'état, vérifiée à la compilation, pour réserver la mémoire statique au plus juste. État : 47 364 octets sur M3 (49 412 avant), 43 268 avec `MULE_FFT_MEM_EXTERNAL`.

Le tampon PCM du codec (32 Kio) n'est pas une cible : il porte la transition sans blanc entre pistes, et sa taille est commune à tous les codecs du firmware.

**Calcul sur M3** : la pré-rotation compte son index en ordre binaire inversé au lieu de le recalculer (92 000 → 27 000 instructions par trame), le gain 2^28 des blocs courts est un décalage, les produits du bruit sont ramenés à 32 bits là où leurs bornes le permettent. abba q −7 : 864 000 → 780 000 instructions par trame (−10 %).

**Variante Cortex-M0** (`-DMULE_NO_LONG_MUL`, le même `core/dec.c`) : le M0 n'a ni multiplication 32 × 32 → 64 ni division, et la bibliothèque C les fait en général sur 64 × 64 bits. La variante :
- calcule chaque produit 64 bits exact à partir de quatre produits 16 × 16, en 17 instructions Thumb-1 (`smul64`, assembleur en ligne) ;
- passe la FFT entière en assembleur (`mule_fft_v6m`) : les demi-mots du facteur de rotation coupés une fois par k, les papillons d'un étage dans l'ordre k puis i (des paires disjointes : mêmes résultats) ;
- utilise une division 64 / 32 par décalages sur les seuls bits du quotient, et des produits 64 × 32 sans la bibliothèque C.

Sur ARMv7-M, et en C sur PC, les mêmes fonctions retombent sur le produit et la division ordinaires. Le chemin C de la variante est vérifié contre la référence par fuzzing différentiel (`tools/fuzz/build_lf.sh`).

Instructions par trame, abba q −7, 10 s (`bench/qemu/prof.sh`, le code M0 exécuté sur la machine M3 de QEMU, dont il est un sous-ensemble) :

| Section | M3 | M0, décodeur générique | M0, variante |
|---|---|---|---|
| lecture du flux | 428 000 | 1 103 000 | 713 000 |
| bandes de bruit et repliées | 34 000 | (comprises ci-dessus) | 140 000 |
| pré-rotation | 27 000 | 324 000 | 148 000 |
| FFT logicielle | 154 000 | 1 075 000 | 481 000 |
| post-rotation | 44 000 | 354 000 | 209 000 |
| fenêtres et addition | 44 000 | 220 000 | 134 000 |
| sortie | 58 000 | 110 000 | 109 000 |
| **total** | **780 000** | **3 125 000** | **1 904 000** (−39 %) |

Code de `core/dec.c` : 19,8 Kio sur M3, 25,3 Kio pour la variante M0 (22,0 Kio pour le décodeur générique compilé pour M0). À 43 trames par seconde, la variante demande environ 82 millions d'instructions par seconde avec la FFT logicielle, environ 61 millions avec une FFT matérielle. Deux essais sans gain, retirés : une routine assembleur par multiplication complexe, appelée depuis les rotations (l'appel et le passage par tableau coûtent ce que l'assembleur gagne) ; la mise à jour des CDF par paires d'entrées de 16 bits dans un mot de 32 bits (exacte, mais les masques par paire coûtent plus que les deux boucles sans branchement : +7 % sur M3, +35 % sur M0). Reste à essayer : les boucles de rotation entières en assembleur (environ −70 000 instructions par trame sur M0).

## 9. Intégration au firmware et premiers essais sur l'appareil

**Intégration** (dépôt `echo-mini-newfw`, branche de test `Mule`, ETUDE §159 et §160) :
- le décodeur est copié dans `third_party/mule` ;
- `fw/hifi/codec_mule.c` en fait l'image 11 du cœur B : lecture Ogg par `oggpage.c`, FFT de l'IMDCT sur `HIFIACC` ;
- le cœur A reconnaît l'extension `.mule` et lit les tags `MULETags` (le format d'`OpusTags`) ;
- la recherche passe par la page Ogg que trouve le cœur A, puis par le paquet clé suivant ; le décodage reprend à l'échantillon près ;
- image du codec : 29,8 Kio de code et de tables, 91 Kio de données (l'état, un paquet, 8 trames de PCM) ;
- dans l'émulateur du firmware, la sortie est exacte au bit près contre `mule-dec -H` (test `mule-exact`), et la recherche est vérifiée par `mule-seek` ;
- fuzzing du codec du cœur B (cible `mule`, 8 instances pendant 30 minutes) : il a trouvé le défaut des allocations et énergies non bornées, corrigé depuis (spec §5.1 et §5.2) ; ensuite, 549 287 exécutions sans aucun plantage.

**Essai du 18/11/2026** (image de test 0.106mu1, journal `work/hwlog/2026-11-18_0.106mu1/`) :
- **matériel écouté** : *Discovery* (Daft Punk, 14 pistes, 61 minutes), encodé avec `mule-enc` depuis le FLAC, au débit par défaut. Résultat : **139 kb/s** en moyenne (FLAC : 914 kb/s), 64 Mo pour l'album, ReplayGain de piste et d'album par `mule-gain -a` ;
- **séance** : environ 7 minutes de lecture sur les pistes 1 à 4, avec une vingtaine de recherches, avant et arrière ;
- **aucune erreur de décodage**, aucun paquet rejeté ; l'IMDCT est toujours passée par `HIFIACC`, jamais par la FFT logicielle de secours ;
- **aucun sous-remplissage du cœur B** (0 sur les 14 bilans de lecture). Le petit sous-remplissage du tampon du DAC noté à chaque recherche (environ 5 Ko) n'est pas propre à MULE : il existe à presque chaque recherche avec les autres codecs, WavPack compris ;
- **enchaînement sans blanc** (piste 1 → 2) : réussi, avec 529 ms de son encore en réserve au moment du changement, et aucune coupure ;
- **recherche** : toujours au bon endroit, ouverture en 30 à 40 ms, comme les autres formats Ogg ;
- **tags** : titre, artiste, album, numéro de piste, artiste de l'album, genre et année, tous lus.

**Charge du cœur B**, mesurée par le firmware sur 436 s de lecture (14 bilans) :

| | |
|---|---|
| Moyenne pondérée par la durée | **58,8 MHz** |
| Moyennes par bilan | 52 à 69 MHz (90 MHz sur un fragment d'une seconde après une recherche) |
| Temps par palier d'horloge | 100 MHz : 76 % ; 80 MHz : 14 % ; 50 MHz : 6 % ; 200 MHz : 4 % (montées brèves, au démarrage et après chaque recherche) |

C'est comparable à Opus sur le même appareil (50 à 55 MHz à 130-145 kb/s, au palier de 67 ou 80 MHz), et environ deux fois Vorbis (29 à 36 MHz, avec la même FFT matérielle). Les 33 à 39 millions d'instructions par seconde mesurés sous QEMU (§8) donnent donc **1,5 à 1,8 cycle par instruction** sur le cœur B. C'est bien moins que les 2,65 à 3,4 mesurés pour le MP3, que j'avais repris à tort pour estimer 90 à 110 MHz ; l'estimation initiale de ce document (50 à 60 MHz, avec 1,3 à 1,5 cycle par instruction) était la bonne.

**Points ouverts** :
- la **mémoire lors des changements de piste** : elle n'apparaît pas dans le journal ; reste l'avis de l'auditeur ;
- après cette séance, la vérification en lecture seule du système de fichiers du baladeur a signalé des **erreurs FAT** (rien n'a été réparé). Elle était propre juste avant, après la copie de l'album. Entre les deux, le baladeur a installé l'image, écrit ses propres fichiers (journal, file de lecture, bibliothèque) et servi de disque USB. Le décodeur MULE n'écrit rien sur le disque : la piste est du côté du firmware (code FAT, ou débranchement pendant une écriture). Le détail est à relever avec `fsck.vfat -n`, puis à traiter dans le firmware ;
- le firmware de la branche `Mule` (README, ETUDE §159-§160) cite encore l'estimation de 90 à 110 MHz ; à corriger avec ces mesures.

