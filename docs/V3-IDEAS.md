# Idées pour un format v3

Le format v2 est figé : le décodeur du firmware le lit, et tous les gains récents (axes 1 à 3) ont été obtenus côté encodeur. Cette liste rassemble ce qui demanderait de changer le format. Une v3 regrouperait plusieurs de ces changements d'un coup, avec de nouvelles CDF initiales (nouvel identifiant de table) et une nouvelle écoute ABX.

**Compatibilité** (décision du 17/11/2026) : la v3 peut rompre avec la v2. MULE est encore un prototype, aucune bibliothèque réelle n'est encodée, et le décodeur du firmware ne gardera qu'un seul format. Quand le code sera mûr, MULE aura son propre dépôt GitHub.

Critères pour le cœur B de l'Echo Mini, par ordre d'importance : **mémoire** du décodeur (la priorité), qualité, puis calcul (pas prioritaire pour l'instant).

## Gains probables, coût faible

1. **Bande passante jusqu'à 22 kHz.** La dernière bande s'arrête au coefficient 928 (19,95 kHz), alors qu'Opus monte à environ 20,4 kHz. C'est inaudible, mais PEAQ retire environ **0,025 d'ODG à 128 kb/s** pour cela (`E2-LOG.md`). Il suffirait d'une 23e bande de 928 à 1024, presque toujours remplie de bruit : quelques bits par trame, aucune mémoire en plus.
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
