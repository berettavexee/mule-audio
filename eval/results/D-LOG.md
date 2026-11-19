# Diagnostic : où MULE v3 perd encore face à Opus (19/11/2026)

`eval/frame_diag.py` : les 30 extraits de `test`, Opus à 128 kb/s, MULE v3 (c64 + a8) au même
débit sur chaque extrait (q par dichotomie ; écart moyen −0,1 %), fenêtres de 2 s au pas de 1 s
(420 fenêtres) : ODG de PEAQ basique de chaque codec, NMR interne par région, part de blocs
courts dans les trames de MULE, intensité, crête, part d'énergie au-dessus de 10 kHz
(`frame_diag.csv`).

## Le déficit est diffus

- ODG MULE − Opus : moyenne −0,055, médiane −0,060. MULE est moins bon sur 75 % des fenêtres ; les
  10 % de fenêtres les pires ne portent que 34 % du déficit.
- **Le NMR de MULE est plus bas que celui d'Opus dans toutes les régions** (médianes −1,1 dB sous
  2 kHz, −1,7 dB entre 2 et 6 kHz, −0,9 dB entre 6 et 10 kHz, −1,3 dB entre 10 et 16 kHz,
  −0,9 dB au-dessus) : MULE a moins de bruit audible selon le modèle interne, partout.
- Le déficit suit l'intensité (corrélation de Spearman −0,45) et, à intensité égale, la présence
  de blocs courts :

| Fenêtres | avec blocs courts | trames longues seulement |
|---|---|---|
| calmes | −0,046 (33) | **+0,023** (107) |
| moyennes | −0,090 (79) | −0,036 (61) |
| fortes | −0,104 (80) | −0,105 (60) |

Les morceaux les plus perdants sont du rock dense et saturé presque sans blocs courts
(`b_red_fang`, `b_orange_goblin`, `b_judas_priest`, `b_garbage` : −0,12 à −0,16), plus
`b_lebanon_hanover` (−0,32, 17 % de trames courtes).

## Ce que PEAQ voit (`eval/mov_diag.py`)

MOV de PEAQ basique sur les morceaux entiers, Opus contre MULE :

| | Lebanon Hanover | Judas Priest | Red Fang | Orange Goblin | Max Richter | Mravinsky |
|---|---|---|---|---|---|---|
| ODG | −0,11 / −0,60 | −0,07 / −0,19 | −0,08 / −0,23 | −0,07 / −0,21 | −0,04 / −0,08 | −0,13 / −0,16 |
| AvgModDiff1B | 6,1 / 7,4 | 9,8 / 11,2 | 10,7 / 12,4 | 9,1 / 10,9 | 7,6 / 7,7 | 7,9 / 7,5 |
| AvgModDiff2B | 6,6 / 8,5 | 19,8 / 23,9 | 23,4 / 30,1 | 16,7 / 21,9 | 28,6 / 26,2 | 18,3 / 17,8 |
| ADBB | −0,18 / 0,91 | −0,51 / 0,57 | −0,37 / 0,80 | −0,53 / 0,52 | −0,68 / −0,04 | −0,09 / 0,39 |
| BandwidthTestB | 901 / 863 | 906 / 861 | 907 / 857 | 900 / 863 | 905 / 855 | 898 / 854 |

Sur le rock, les différences de modulation (l'enveloppe temporelle par bande) sont de 15 à 30 %
plus fortes chez MULE ; sur les morceaux où MULE gagne, elles sont égales ou plus faibles. La
bande passante (la coupure à 19,95 kHz) est plus basse partout, gagnants compris : elle ne
sépare pas les morceaux.

**Plus de résolution temporelle n'y fait rien.** Seuil du détecteur de transitoires abaissé
(build de travail seulement) : de 10 dB à 6 puis 3 dB, la part de trames courtes passe de
1 % à 3 % puis 45 à 70 % sur ces quatre morceaux ; les différences de modulation augmentent
(AvgModDiff1B de Red Fang 12,4 → 12,5 → 13,1) et l'ODG ne bouge pas ou baisse.

## Conclusion pour la v3

- Les outils de résolution temporelle (points 5, 6, 7) ne visent pas ce déficit : les trames
  courtes, même nombreuses, l'aggravent.
- Les bandes aiguës plus étroites (point 15) non plus : le bruit de MULE y est déjà sous celui
  d'Opus.
- Le pliage (point 19) ne toucherait que les bandes 20 et 21 (au-dessus de 16 kHz).
- L'écart restant est propre au modèle de PEAQ basique (modulation, ADB) sur le rock dense,
  alors que le NMR, l'ODG avancé et ViSQOL donnent l'avantage à MULE. **Aucun outil de qualité
  n'est donc ajouté à la v3**, qui est figée en l'état.

Suite : le point 26 (Haar dans les bandes des trames longues), seul outil visant l'enveloppe
temporelle des trames longues, a été essayé : +0,003 d'ODG sur `dev`, écarté (`H-LOG.md`). La v3
est figée sans outil de qualité supplémentaire.
