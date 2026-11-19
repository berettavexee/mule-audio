# MULE, un codec audio taillé pour un baladeur

*MULE est un codec audio avec perte conçu pour un seul appareil : le baladeur Snowsky Echo Mini, dont le cœur de décodage est un Cortex-M3 sans unité de calcul flottant. Cet article explique comment il fonctionne, du fichier au son.*

## Le problème

Sur l'Echo Mini, la musique est décodée par un second processeur, le « cœur B ». C'est un Cortex-M3 qui ne dispose que de 128 Kio pour le code et de 148 Kio pour les données. Vorbis y fonctionne, mais sa mémoire est le vrai point de friction, surtout lors des changements de piste. Opus y est plus lourd en calcul. MULE part de ce constat : un décodeur simple, sans calcul flottant ni allocation dynamique, qui tient en environ 30 Kio de code et 50 Kio d'état, avec une qualité au moins égale à celle de Vorbis à débit égal.

La règle de conception est **un encodeur intelligent, un décodeur bête**. Tout ce qui demande de la réflexion (psychoacoustique, choix des blocs, allocation des bits) se fait sur PC, à l'encodage. Le décodeur se contente d'appliquer les décisions inscrites dans le flux.

## Du temps aux fréquences : la MDCT

Comme MP3, AAC ou Vorbis, MULE travaille dans le domaine fréquentiel. Le signal (44,1 kHz, stéréo) est découpé en trames de 1024 échantillons, et chaque trame est transformée par une **MDCT** de 2048 points en 1024 coefficients. Les fenêtres se recouvrent à moitié et s'annulent mutuellement à la reconstruction : il n'y a aucune discontinuité entre les trames.

Une transformée longue donne une bonne résolution en fréquence, mais elle étale une attaque (castagnettes, piano) sur 46 ms. Le bruit de quantification apparaît alors *avant* l'attaque : c'est le « pré-écho ». Un détecteur de transitoires repère donc les attaques. La trame est alors codée en **8 blocs courts** de 256 points, que l'encodeur peut regrouper quand ils se ressemblent pour ne transmettre qu'une seule énergie. Les fenêtres de transition entre blocs longs et courts sont celles de Vorbis.

## Le spectre en 22 bandes

Les 1024 coefficients sont répartis en **22 bandes**, étroites dans les graves (8 coefficients, soit 172 Hz) et larges dans les aigus (jusqu'à 176 coefficients), à la manière de l'oreille. Chaque bande est décrite par deux informations distinctes.

- Son **énergie**, quantifiée par pas de 1,5 dB. Elle est prédite à partir de la même bande dans la trame précédente et de la bande voisine plus grave, et seul l'écart est transmis.
- Sa **forme** : les coefficients divisés par la racine de l'énergie, donc normalisés. C'est là que va l'essentiel des bits.

Cette séparation, empruntée à CELT (le cœur d'Opus), garantit que l'énergie de chaque bande est toujours juste, même quand sa forme est grossièrement codée.

Pour chaque bande, l'encodeur choisit aussi une **allocation** *a*, qui fixe le pas de quantification de la forme (chaque cran de *a* affine ce pas de 1,5 dB). Une allocation nulle signifie que la bande n'est pas codée du tout : le décodeur la remplit d'un **bruit** pseudo-aléatoire à la bonne énergie. Dans les aigus bruités (cymbales, souffle), c'est inaudible et presque gratuit. Enfin, chaque bande est codée soit en **gauche/droite**, soit en **milieu/côté** (somme et différence des canaux), selon ce qui coûte le moins de bits pour la même qualité perçue.

## Quantifier en treillis

La forme de chaque bande est quantifiée par **TCQ** (*Trellis-Coded Quantization*, quantification en treillis), la méthode de JPEG 2000 partie 2. Au lieu d'arrondir chaque coefficient indépendamment, l'encodeur parcourt une machine à 64 états. Chaque état n'autorise qu'une moitié des niveaux de reconstruction : selon le chemin suivi dans le treillis, le décodeur sait laquelle. Le pas effectif est ainsi divisé par deux sans payer le bit supplémentaire. L'encodeur cherche le meilleur chemin par l'**algorithme de Viterbi**, en pesant l'erreur de chaque niveau contre son coût exact en bits. Pour le décodeur, c'est presque gratuit : une table de transitions et un test de parité par coefficient. Depuis la version 3, l'état du treillis ne repart plus de zéro à chaque bande : un seul Viterbi parcourt toutes les bandes codées de la trame, ce qui a rapporté +0,036 d'ODG à 128 kb/s par rapport aux 8 états de la version 2.

À l'écoute en ABX, la TCQ a fait la différence. À 160 kb/s, elle était transparente sur les 6 extraits critiques testés, contre 5 sur 6 pour la quantification scalaire. Elle est donc devenue l'unique quantificateur du format, en version 2, et a été agrandie en version 3.

## Le codage entropique : rANS et modèles adaptatifs

Tous les symboles (types de bloc, énergies, allocations, coefficients) sont compressés par **rANS**, un codeur arithmétique moderne rapide à décoder. Il travaille sur un état de 32 bits et lit le flux par mots de 16 bits. Chaque symbole est codé avec une **distribution de probabilité (CDF) adaptative**, mise à jour après chaque symbole comme dans AV1. Il y en a 134, réparties en 9 flux.

Le gain vient des **contextes**. La probabilité d'un coefficient dépend de la taille des deux coefficients précédents, du même coefficient dans la trame précédente (la musique change peu d'une trame à l'autre) et de la finesse de quantification de sa bande. Les CDF initiales ont été entraînées sur 200 morceaux tirés de la bibliothèque et ne servant pas aux évaluations.

## Le conteneur : Ogg

MULE est encapsulé dans **Ogg**, comme Vorbis et Opus. Le lecteur de l'Echo Mini savait déjà lire ce conteneur. Un fichier contient un en-tête `MULEHead`, des tags `MULETags` (même disposition que ceux d'Opus), puis des paquets de 4 trames. Toutes les 40 trames, soit environ 0,93 s, un **paquet clé** remet les modèles adaptatifs à leur état initial et indique son numéro de trame : le décodeur peut donc reprendre n'importe où. Une recherche dans un morceau est ainsi précise à l'échantillon près. Les positions inscrites dans les pages Ogg permettent aussi une **lecture sans blanc** entre les pistes d'un album.

## L'encodeur et la psychoacoustique

Tout l'art est dans le choix des allocations. L'encodeur calcule pour chaque trame un **seuil de masquage** : le niveau de bruit que la musique elle-même rend inaudible. Il tient compte :
- de l'étalement du masquage le long de l'échelle des Bark, l'échelle fréquentielle de l'oreille ;
- de la tonalité, car un son pur masque moins bien que du bruit ;
- du seuil absolu d'audition.

L'allocation de chaque bande vise un bruit situé à une distance fixe sous ce seuil. Ce paramètre de qualité donne un débit variable : environ 110 kb/s pour le réglage −6 dB, 135 kb/s pour −9 dB et 165 kb/s pour −12 dB. Une passe d'optimisation débit-distorsion ajuste ensuite chaque allocation d'un cran, en connaissant le coût exact de chaque choix.

Dernière amélioration : dans les graves, où une bande de 172 Hz couvre près de 2 Bark, le masque est maintenant calculé raie par raie. Une note grave isolée ne masque que son voisinage, pas toute la bande. Le gain atteint +0,2 d'ODG sur un orchestre et sur des triangles.

## Le décodeur sur le baladeur

Le décodeur de l'appareil est écrit **en virgule fixe** : coefficients sur 32 bits, aucune opération flottante, aucune allocation de mémoire.
- **Transformée inverse** : l'IMDCT passe par une FFT complexe de 512 points, confiée à l'**accélérateur matériel** du baladeur (HIFIACC).
- **Exactitude** : ce décodeur est la référence du format. Sa sortie est identique au bit près sur le PC, dans l'émulateur du firmware et sur le Cortex-M3 émulé sous QEMU.
- **Encombrement** : l'image du codec occupe 30 Kio de code et de tables, et 91 Kio de mémoire de travail, tampons compris.
- **Charge de calcul** : environ 0,9 million d'instructions par trame en version 2, 0,84 million en version 3 (QEMU ; la version 3 n'est pas encore portée sur l'appareil). Sur l'appareil, en lisant un album entier à 139 kb/s, le cœur B tourne en moyenne à **59 MHz**, comme pour Opus, sans aucun sous-remplissage.

## Résultats

Mesures sur 30 extraits jamais utilisés pour régler l'encodeur, à débit égal. L'ODG (PEAQ) vaut 0 pour une différence imperceptible et −1 pour une différence audible mais pas gênante. ViSQOL note de 1 à 5.

| | ODG 128 kb/s | ODG 160 kb/s | ODG avancé 128 / 160 | ViSQOL 128 kb/s |
|---|---|---|---|---|
| Vorbis | −0,45 | −0,16 | −0,63 / −0,34 | 4,47 |
| Opus | **−0,12** | **0,00** | −0,45 / −0,24 | 4,54 |
| **MULE** (v3) | −0,17 | −0,01 | **−0,36 / −0,14** | **4,61** |

MULE dépasse nettement Vorbis et rivalise avec Opus. Il est devant ce dernier en ODG avancé et en ViSQOL, et derrière en ODG de base. À l'écoute (version 2), il est transparent dès 128 kb/s, et indiscernable d'Opus au même débit, y compris sur les extraits où PEAQ voit le plus grand écart (écoute G3). C'est désormais le débit par défaut de l'encodeur. Le tout pour un décodeur deux fois plus petit en code que celui de Vorbis, et qui n'a besoin d'aucun calcul flottant.
