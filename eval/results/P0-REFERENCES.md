# P0 : références Vorbis et Opus

Corpus de 36 extraits de 8 à 15 s en 44,1 kHz/16 bits stéréo, construit par `eval/corpus.py` :
- 16 extraits de l'EBU SQAM (castagnettes, glockenspiel, clavecin, triangles, voix, piano, orchestre, etc.) ;
- 4 extraits de Daft Punk, *Discovery* ;
- 16 extraits de la bibliothèque FLAC : metal, classique, baroque, électronique, hip-hop, voix seules, etc.

Commande : `.venv/bin/python eval/run_eval.py --tag p0_refs`. Les résultats détaillés sont dans `p0_refs.csv`.

Codecs utilisés : libvorbis via `oggenc` de vorbis-tools 1.4.3 (**ce n'est pas aoTuV**), et libopus 1.6.1 via `opusenc --music --vbr`, décodé par `opusdec --rate 44100`. Le débit compte uniquement les paquets audio, sans en-têtes ni surcoût Ogg.

## Moyennes sur le corpus

| Config | kb/s | NMR (dB) | NMR max (dB) | ADF | SNR (dB) |
|---|---|---|---|---|---|
| vorbis_q3 | 99,9 | −0,55 | 6,22 | 0,80 | 22,0 |
| vorbis_q4 | 113,1 | −2,24 | 4,65 | 0,76 | 23,6 |
| vorbis_q5 | 141,5 | −4,65 | 1,64 | 0,62 | 25,6 |
| vorbis_q6 | 171,3 | −6,70 | −0,66 | 0,48 | 28,1 |
| opus_96 | 101,8 | −1,69 | 4,66 | 0,79 | 21,1 |
| opus_128 | 133,9 | −4,42 | 1,82 | 0,66 | 23,4 |
| opus_160 | 165,8 | −6,57 | −0,35 | 0,51 | 25,1 |
| opus_192 | 196,9 | −8,78 | −2,59 | 0,32 | 26,4 |

ViSQOL v3, mode audio, MOS-LQO moyen : vorbis q3/q4/q5/q6 = 4,41 / 4,49 / 4,60 / 4,67 ; opus 96/128/160/192 = 4,38 / 4,54 / 4,65 / 4,66.

## À débit égal (interpolation sur la courbe de chaque codec)

| Codec | ViSQOL @128 | ViSQOL @160 | NMR @128 | NMR @160 | ADF @128 | ADF @160 |
|---|---|---|---|---|---|---|
| Vorbis (libvorbis 1.3) | 4,548 | 4,641 | −3,51 | −5,92 | 0,683 | 0,529 |
| Opus 1.6 | 4,512 | 4,630 | −3,92 | −6,18 | 0,687 | 0,538 |

Les deux codecs sont **à égalité dans la marge de mesure** : ViSQOL donne un léger avantage à Vorbis, le NMR un léger avantage à Opus.

**Cible G1 pour MULE** (estimation P2) : à 128 kb/s, un ViSQOL ≥ 4,55 et un NMR ≤ −3,9 dB ; à 160 kb/s, un ViSQOL ≥ 4,64 et un NMR ≤ −6,2 dB. Il faudra relever ces valeurs une fois aoTuV disponible.

Ce que valent les scores ViSQOL :
- l'échelle sature près de la transparence : tout le corpus tient entre 4,4 et 4,67. Les écarts utiles sont de l'ordre de quelques centièmes ;
- un score par extrait est bruité : dp_veridisquo obtient 4,32 en q4 et 4,17 en q5, et pires_concerto 3,16 avec opus_128. Seules les moyennes sur le corpus servent à décider ;
- extraits les plus bas pour Vorbis q4 : pinkfloyd (3,24), emerson_fugue, brandenburg, quartet. Pour Opus 128 : pires_concerto (3,16).

## Comment lire ces chiffres

- Le NMR interne est un modèle de Johnston volontairement simple (`eval/metrics.py`). **Ce qui compte, c'est l'écart entre deux variantes, pas la valeur absolue.** Il est clairement plus sévère que PEAQ : une ADF de 0,6 à 0,7 à 128 kb/s n'est pas plausible en valeurs absolues.
- Un passe-haut à phase nulle à 20 Hz est appliqué avant toute mesure. Opus supprime la composante continue, et le décalage DC de certains enregistrements SQAM faussait la mesure (triangles) et l'alignement.
- L'extrait le plus dégradé pour les deux codecs est **heilung** (percussions, voix de gorge, ambiance). Viennent ensuite wutang, bjork_medulla et dp_veridisquo.
- **orchestra / Opus** : le NMR reste à −3,8 dB quel que soit le débit et le délai mesuré est de −9 échantillons. L'extrait est très calme, et Opus remplit d'énergie des aigus presque vides au-dessus de 15 kHz. C'est un vrai comportement du codec, mais le modèle interne ne peut pas dire s'il est audible. À revérifier avec ViSQOL ou PEAQ.
- **Voix (SQAM, mono dans un fichier stéréo)** : Opus y est nettement meilleur (−7,7 contre +1,1 dB à environ 130 kb/s). Le M/S du futur MULE devra récupérer ce gain.

## Ce qui manque encore à P0

- ViSQOL : **c'est fait** (`third_party/visqol`, compilé avec gcc 15 et `-Wno-template-body -include cstdint`), et il est détecté automatiquement. Une évaluation complète prend environ 7 min ; `VISQOL= .venv/bin/python eval/run_eval.py` le désactive pour itérer vite sur le NMR seul (environ 40 s).
- PEAQ (GstPEAQ) : en option, avec la variable d'environnement `PEAQ`.
- Un encodeur **aoTuV** comme référence Vorbis réelle : `OGGENC=/chemin/vers/oggenc-aotuv`.
