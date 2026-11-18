# P1 : transformée et commutation de blocs

Code : `py/mule/mdct.py` (MDCT 2048/256, fenêtres Vorbis, transitions façon Vorbis) et `py/mule/transient.py` (détecteur).
Tests : `tests/` (16 tests). Expérience : `.venv/bin/python eval/p1_blocks.py --snr 12`, résultats détaillés dans `p1_blocks_snr12.csv`.

## Transformée

- La reconstruction est **exacte (erreur < 1e-9)** pour des séquences de blocs longs et courts tirées au hasard, en mono comme en stéréo. Le critère P1 était < 1e-6.
- La MDCT correspond à sa définition directe, et l'IMDCT est bien sa transposée.
- L'échelle est orthonormée : du bruit blanc a la même énergie par coefficient en bloc long et en bloc court (écart < 0,2 dB).
- Géométrie : trames de 1024 ; fenêtre longue de 2048 centrée sur 1024·t ; 8 blocs courts de 256 placés à 448 + 128k (disposition AAC) ; pentes de 1024 entre deux blocs longs, de 128 dès qu'un des deux voisins est court.

## Détecteur

On travaille sur un signal filtré au-dessus de 3 kHz, découpé en sous-blocs de 128 échantillons. Un sous-bloc est une attaque si l'une de ces deux conditions est remplie :
- il dépasse de plus de 10 dB une mémoire du passé qui décroît de 3 dB par sous-bloc (attaques franches) ;
- il dépasse de plus de 20 dB le sous-bloc le plus fort situé 20 à 29 ms plus tôt (attaques lentes, comme le gong qui monte de 3 dB/ms).

La décision vaut pour tous les canaux.

**Zone d'affectation** : une attaque passe la trame t en blocs courts si elle tombe dans `[1024t − 448, 1024t + 576)`. Une zone centrée, `[1024t − 512, 1024t + 512)`, laissait des attaques dans la pente de la fenêtre longue précédente, et leur bruit se répandait sur toute cette fenêtre.

## Pré-écho avec une quantification fictive

On ajoute dans chaque bande (et chaque groupe) un bruit uniforme 12 dB sous l'énergie de la bande. Les attaques de référence sont détectées sur le signal original, indépendamment du détecteur testé. Le PER (rapport pré-écho/signal) compare le bruit au signal entre 20 ms et 2 ms avant l'attaque, avec un signal planché à −80 dBFS. Une attaque est comptée comme « audible » si PER > 0 dB.

Trois modes sont comparés :
- **long** : uniquement des blocs longs ;
- **sw8** : commutation, avec une énergie par fenêtre courte (8 groupes) ;
- **sw1** : commutation, avec une seule énergie pour les 8 fenêtres (1 groupe).

| Moyenne sur 36 extraits | long | sw8 | sw1 |
|---|---|---|---|
| Trames courtes | 0 % | 4,3 % | 4,3 % |
| PER moyen | −8,9 dB | **−11,1 dB** | −9,0 dB |
| Attaques audibles | 9,2 % | **1,3 %** | 8,9 % |
| NMR interne | +0,77 dB | **−0,19 dB** | +0,47 dB |

Détail des extraits critiques (part de trames courtes, puis attaques audibles en long → sw8) :
- castagnettes : 16 % de trames courtes, 33 % → **0 %** ;
- triangles : 1,4 %, 67 % → **0 %** ;
- gong 5 kHz : 3,5 %, 100 % → **0 %** ;
- voix féminine : 13 %, 12 % → 3,7 % ;
- violon et guitare : → 0 %.

Les extraits stationnaires (orgue, piano, quatuor, orchestre) restent à 0 ou 0,5 % de trames courtes.

**Conclusion : le regroupement des blocs courts est indispensable.** Avec une seule énergie pour les 8 fenêtres, on ne gagne presque rien. `PROPOSAL-A.md` §3 est corrigé en conséquence.

Ce qu'il reste :
- **glockenspiel**, 1 attaque sur 4 : elle suit un silence numérique, et un bloc court étale quand même environ 4 ms de bruit avant elle. C'est la limite de résolution des blocs de 256, couverte en pratique par le masquage antérieur.
- **trompette**, 1 attaque sur 12 : une attaque douce, de −65 à −46 dBFS, avec un PER de +1,6 dB. Elle n'est pas détectée, et ce n'est probablement pas audible.

## À faire plus tard

- Les énergies supplémentaires en trames courtes ont un coût en débit : à mesurer en P2, et à réduire par un regroupement adaptatif (par exemple deux groupes, avant et après l'attaque).
- `tf_change` par bande pour retrouver de la résolution fréquentielle dans les graves des trames courtes.
- Un bloc intermédiaire de 512 ou 1024 (tailles prises en charge par l'accélérateur matériel), si P2 montre que la résolution des blocs courts coûte trop cher sur les attaques douces.
