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

