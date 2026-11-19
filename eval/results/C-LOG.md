# Étape C : le coût du décodeur (point 13 de docs/V3-IDEAS.md)

Plan : réponse du 18/11/2026, étape C. Mesure du débit sur `dev` (vrais modèles adaptatifs,
réinitialisations, tables entraînées), mesure des instructions sur QEMU (Cortex-M3, abba q −12,
10 s, `bench/qemu/run.sh`, au bit près contre le PC à chaque fois).

## Où vont les instructions du décodage entropique

Décodeur instrumenté (`-DMULE_STATS`, `tools/mule_dec.c`), 17 extraits de `dev`, par trame (deux
canaux) :

| Flux | symboles | pas de recherche | entrées de CDF mises à jour |
|---|---|---|---|
| coef | 1 335 | 2 219 | **20 030** |
| energy | 46 | 379 | 695 |
| alloc | 46 | 378 | 695 |
| stereo | 22 | 32 | 22 |
| autres | 11 | 27 | 105 |
| total | 1 461 | 3 035 | **21 546** |

Plus 855 lectures de bits bruts (signes, suffixes d'échappement). La recherche s'arrête tôt (les
petites valeurs dominent : 1,7 pas par symbole de coefficient) ; la mise à jour parcourt toujours
toute la CDF (15 entrées) : c'est elle qui domine.

## Mettre à jour les modèles un symbole sur N (`mule_model_every`)

Expérience réglable dans `core/model.c` (encodeur et décodeur doivent avoir la même valeur ;
QEMU : `MULE_MODEL_EVERY`). Débit : `eval/c_models.py`, tous les flux, sur les opérations de
l'encodeur à mise à jour complète.

| Mise à jour | débit `dev` | instructions par trame (QEMU) |
|---|---|---|
| chaque symbole (v2) | 117,21 kb/s | 916 141 |
| 1 sur 2 | +0,32 % (66/66 extraits plus chers) | 828 571 (**−9,6 %**) |
| 1 sur 2, adaptation accélérée (taux −1) | +0,66 % | ≈ −9,6 % |
| 1 sur 4 | +0,66 % | 780 317 (**−14,8 %**) |
| 1 sur 4, taux −1 / −2 | +0,90 % / +2,03 % | ≈ −14,8 % |

La mise à jour coûte donc environ 19 % des instructions du décodeur. Accélérer l'adaptation pour
compenser fait pire. « 1 sur 2 » est un compromis raisonnable si la charge du cœur B redevient
une priorité (elle ne l'est pas aujourd'hui). Note : la simple présence du réglage coûte environ
1,5 % d'instructions (un test par mise à jour) ; une version définitive le figerait.

## Alphabet de 8 symboles pour les coefficients (`coef_a8`, branche `v3-a8`)

Les coefficients sont codés sur 16 symboles (0 à 14, échappement 15) ; ils passent à 8 (0 à 6,
échappement 7, suivi de l'ordre Exp-Golomb de mag − 7 dans le flux cesc et de ses bits bruts).
Tables initiales entraînées sur les traces de `train` (`tools/gen_init_a8.py`,
`core/init_cdf_a8.h`). Format v3 : bit 1 des drapeaux (octet 21).

Estimation sur la trace (`ctx_lab.py alpha8`, tables entraînées pour chaque alphabet) :

| Alphabet | bits de coefficients, échappements compris | écart (débit total) | échappements |
|---|---|---|---|
| 16 (v2) | 69,69 kb/s | — | 0,37 % des symboles |
| **8** | **69,69 kb/s** | **0,00 %** | 1,40 % |
| 4 | 70,16 kb/s | +0,40 % | 6,13 % |

Dans le codec (encodeur et décodeur), QEMU :

| Flux | instructions par trame | pire trame | débit (abba q −12) |
|---|---|---|---|
| v2 | 917 705 | 1 045 200 | 152,6 kb/s |
| v2 + alphabet 8 | 849 403 (**−7,4 %**) | 962 560 | 152,4 kb/s |
| c64 | 918 189 | 1 045 120 | 153,2 kb/s |
| c64 + alphabet 8 | 849 823 (**−7,4 %**) | 962 480 | 152,8 kb/s |
| c64 + alphabet 8 + mise à jour 1 sur 2 | 797 245 (**−13,2 %**) | — | 153,3 kb/s |

Tous au bit près contre le PC. L'alphabet à 8 symboles est gratuit en débit (−0,15 à −0,3 % à
réglages égaux sur trois extraits) et réduit le décodage de 7 % ; il divise aussi par deux la
taille des tables et des modèles de coefficients (96 × 17 → 96 × 9 entrées de 16 bits : −1,5 Kio
de RAM, −1,5 Kio de tables).

Vérification à débit égal (les décisions de l'encodeur changent un peu avec les coûts), c64+a8
contre c64 sur `dev` (66 extraits, `a8_dev.csv` dans la branche `v3-a8`, + = mieux) :

| Mesure | @128 | @160 |
|---|---|---|
| ODG | +0,002 [−0,001 ; +0,004] | +0,003 [−0,003 ; +0,009] |
| ODG avancé | +0,002 [+0,001 ; +0,003] | +0,001 [+0,000 ; +0,002] |
| 2f | +0,05 | +0,6 |
| ViSQOL | +0,000 | +0,001 |
| NMR | +0,01 dB | +0,03 dB |

Débit à réglages égaux −0,16 %, aucune régression. L'alphabet à 8 symboles est donc neutre à
légèrement favorable en qualité, et retire 7 % du décodage : **retenu avec c64 pour la v3**.
