# Point 26 : Haar dans les bandes des trames longues (branche `v3-haar`)

Plan : réponse du 19/11/2026. Étape A, sonde à niveau fixe : toutes les trames longues, bandes
`haar_b0` à 21, Walsh-Hadamard orthonormé sur des groupes de 2^L raies voisines, coefficients
rangés segment par segment ; inverse au décodeur (Q30), avant M/S. Niveau et bande de départ dans
les bits 2 à 7 des drapeaux (provisoire : le test d'en-tête refuse encore ces bits et échoue sur
cette branche). Aucune décision, aucune signalisation, contexte inter-trame gardé (même domaine
d'une trame à l'autre).

Aller-retour exact ; à réglages égaux, +0,9 % de débit au niveau 1, +2,2 % au niveau 2 (perte de
concentration).

## Étape A : 14 extraits de `test` (8 de rock perdants, 6 autres), à débit égal contre la v3

`haarA.csv`, `p4_compare.py`, + = mieux, @128 kb/s :

| Variante | ODG | ODG rock / autres | ODG avancé | 2f rock / autres | ViSQOL | NMR | ODG @160 |
|---|---|---|---|---|---|---|---|
| h1 (bandes 12+, 2 raies) | +0,003 | +0,011 / +0,001 | −0,008 | +2,5 / +0,2 | +0,006 | −0,15 dB | +0,011 |
| h2 (bandes 12+, 4 raies) | +0,001 | **+0,026** / −0,009 | −0,024 | +4,0 / −0,1 | +0,012 | −0,35 dB | +0,010 |
| h1b15 (bandes 15+) | −0,001 | +0,003 / +0,001 | −0,001 | +2,4 / +0,0 | +0,006 | −0,11 dB | +0,013 |
| h2b15 | +0,004 | **+0,026** / −0,008 | −0,014 | +4,0 / −0,4 | +0,012 | −0,23 dB | +0,010 |
| h3b17 (bandes 17+, 8 raies) | −0,009 | +0,009 / −0,010 | −0,022 | +3,9 / −0,6 | +0,015 | −0,32 dB | +0,009 |

- Sur le rock, le Haar fait ce qu'on attendait : 2f (qui pèse les différences de modulation et
  l'ADB) +4, ViSQOL +0,015, ODG +0,026 aux niveaux 2. Critère de l'étape A (+0,02 sur le rock)
  atteint.
- Imposé partout, il coûte ailleurs (ODG −0,01 hors rock) et l'ODG avancé et le NMR reculent
  partout (bits perdus en concentration) : un niveau choisi par trame est indispensable.
- Suite : étape B (décision par trame et par classe de bandes, signalisation, mesure sur `dev`).

## Étape B : niveau choisi par trame, signalé

Un niveau par trame longue et par classe (bandes 12 à 15, 16 à 21), 0 à `haar_max`, partagé par
les deux canaux, 2 bits bruts chacun après les drapeaux stéréo ; l'encodeur prend le niveau qui
minimise la norme L1 normalisée des bandes (somme sur bandes et canaux), × (1 + `haar_bias` ×
niveau). Le contexte inter-trame d'une bande est coupé quand son niveau change.

Tri sur les 14 extraits (`haarAB.csv`, moyennes des écarts par extrait, @128) : biais 0 :
ODG +0,011 (rock +0,019, autres +0,001), ODG avancé −0,001, 2f +1,1, ViSQOL +0,003 ; biais 0,05 et
0,15 : le Haar n'est presque plus choisi (écarts nuls).

**`dev`** (66 extraits, `haarB_dev.csv`, `p4_compare.py`, contre la v3) :

| Variante | ODG @128 | ODG @160 | ODG avancé @128 | 2f @128 | ViSQOL @128 | NMR @128 | débit à réglages égaux |
|---|---|---|---|---|---|---|---|
| ha0 (biais 0, niveaux 0-2) | +0,003 [−0,001 ; +0,007] | +0,001 | −0,002 | +0,7 | +0,002 | −0,08 dB | +0,52 % |
| ham03 (biais −0,03) | −0,001 | −0,003 | −0,016 | +0,8 | +0,003 | −0,25 dB | +1,68 % |
| ha3 (niveaux 0-3) | +0,002 | +0,001 | −0,003 | +0,7 | +0,003 | −0,09 dB | +0,64 % |

**Sous le seuil (+0,01) : point 26 écarté.** Le Haar améliore l'enveloppe temporelle là où PEAQ
la pénalise (2f, ViSQOL en hausse, gain sur le rock), mais il coûte des bits en concentration
partout ailleurs (ODG avancé et NMR en baisse), et sur l'ensemble de `dev` les deux s'annulent.
Le critère de concentration ne sait pas réserver l'outil aux trames où il aide ; un meilleur
critère devrait viser la mesure de PEAQ elle-même, ce que la règle du projet déconseille.
Les étapes C et D ne sont pas faites ; la branche `v3-haar` reste comme trace, non fusionnée.
