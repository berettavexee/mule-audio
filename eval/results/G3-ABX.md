# Écoute ABX G3 (kit : `data/listen/g3`, `eval/abx_kit_g3.py`)

Encodeur : MULE format v2, encodeur des axes 1 et 2 (`main`, commit d'après `a5780e0`). MULE au
même débit qu'Opus sur chaque extrait (à 2 % près, `rates.txt`). 16 essais par test ; 12 bonnes
réponses ou plus : différence entendue (p < 0,05).

## 1. Extraits « écart » (PEAQ : Opus devant)

| Extrait | mule128 / orig | opus128 / orig | mule128 / opus128 | mule160 / orig | opus160 / orig | Défaut entendu |
|---|---|---|---|---|---|---|
| female_en | 9/16 | | 7/16 | | | aucun identifié |
| b_joy_division | 8/16 | | 8/16 | | | aucun identifié |
| b_wolfmother | 10/16 (p 0,23) | | 11/16 (p 0,11) | | | aucun identifié |
| b_modest_mussorgsky | 5/16 | | 6/16 | | | aucun identifié |
| b_body_count | 9/16 | | 9/16 | | | aucun identifié |
| heilung | 8/16 | | 6/16 | | | aucun identifié |

Écoute du 17/11/2026 au soir (squishyball, `data/listen/g3/results/`). **Aucun résultat significatif** : ni MULE à 128 kb/s contre l'original, ni MULE contre Opus au même débit. Le plus proche du seuil est Wolfmother (10/16 et 11/16, p = 0,23 et 0,11). « J'ai beaucoup de mal à identifier des différences sur les deux tests. »

Conclusion : sur les extraits où PEAQ voit le plus grand écart avec Opus, l'écart ne s'entend pas, et MULE à 128 kb/s est transparent pour cet auditeur. L'écart de PEAQ (environ 0,05 d'ODG à 128 kb/s) n'est pas audible ici.

## 2. Bruit de remplacement (q −7)

| Extrait | mule128nf / mule128 | mule128 / orig | mule128nf / orig | Préférence |
|---|---|---|---|---|
| triangles | | | | |
| glockenspiel | | | | |
| orchestra | | | | |
