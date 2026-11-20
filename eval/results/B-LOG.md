# Étape B : le treillis (points 4, 16 et 17 de docs/V3-IDEAS.md), branche `v3-tcq`

Plan : réponse du 18/11/2026 (« Plan pour la suite », étape B). Seuils : 1 % des bits de
coefficients pour le point 4 (sans coût au décodeur), +0,01 d'ODG à 128 kb/s confirmé sur `test`
pour les points 16 et 17.

## B1, point 4 : des contextes qui connaissent l'état du treillis

L'état change le sens du symbole : dans un état pair, l'union contient zéro et l'index vaut |k|/2 ;
dans un état impair, pas de zéro, et l'index vaut (|k| − 1)/2. L'état avant chaque coefficient est
connu du décodeur (0 au début de chaque bande en v2). Mesure sur la trace (`ctx_lab.py p4`, format
de trace 2, tables entraînées sur `train` pour chaque règle, `dev`) :

| Contexte | coefficients | total | extraits meilleurs |
|---|---|---|---|
| actuel (96) | — | — | — |
| × parité de l'état (192) | **−0,72 %** | **−0,42 %** | 60/66 |
| × état complet (768) | −0,53 % | −0,31 % | 50/66 |

Sous le seuil de 1 %, et pas gratuit : doubler les contextes des coefficients ajoute environ
3 Kio de modèles en RAM (et autant de tables initiales). Gardé en réserve, à combiner avec le
point 16 (en chaîne, la parité au début des bandes n'est plus toujours paire).

## Modèle simple avant le codec (`eval/tcq_sim.py`)

Famille de treillis : depuis l'état s, la branche br mène à (2 s + br) mod N et utilise le
sous-ensemble (s & 1) + 2 (br ⊕ parité(s & masque)). N = 8, masque 0b110 redonne exactement les
tables de MULE (vérifié). Masques trouvés par recherche exhaustive (MSE à pas fixe) : 16 états
0b1101, 32 états 0b10111.

Gain d'erreur quadratique sur un quantificateur scalaire uniforme, à entropie égale (dB),
échantillons laplaciens découpés en bandes de trame longue de MULE (200 trames ; Viterbi à pas
fixe, sans optimisation débit-distorsion : seuls les écarts entre lignes comptent) :

| Quantificateur | 1,0 bit | 1,25 bit | 1,5 bit | 2,0 bits |
|---|---|---|---|---|
| 8 états, redémarré à chaque bande (v2) | −0,49 | −0,06 | +0,28 | +0,67 |
| 8 états, chaîne, Viterbi conjoint (point 16) | −0,48 | +0,03 | +0,42 | +0,82 |
| 8 états, chaîne gloutonne (chaque bande depuis l'état final de la précédente) | −0,72 | −0,14 | +0,25 | +0,67 |
| 16 états, redémarré | −0,49 | −0,02 | +0,31 | +0,70 |
| 16 états, chaîne | −0,45 | +0,12 | +0,49 | +0,89 |
| 32 états, redémarré | −0,49 | −0,00 | +0,36 | +0,73 |
| 32 états, chaîne | −0,41 | +0,17 | +0,57 | +0,95 |

- La perte de la v2 ne vient pas de l'union paire imposée au départ (chaque coefficient a
  toujours une union de deux sous-ensembles, au même pas), mais du départ en un seul état : le
  treillis met trois coefficients à ouvrir ses chemins, ce qui pèse sur les bandes de 8.
- Enchaîner les bandes ne suffit pas : la chaîne gloutonne est même moins bonne. Tout le gain
  vient du **Viterbi conjoint** sur la trame, qui choisit la fin d'une bande avec le début de la
  suivante.
- Chaîne seule : +0,09 à +0,15 dB sur la v2 ; 32 états en chaîne : +0,23 à +0,29 dB. Vers
  1,25 bit par coefficient (le régime de MULE), 0,25 dB valent environ 0,04 bit par coefficient,
  3 % des bits de coefficients, près de 2 % du débit : le premier résultat à atteindre le seuil.

## B2, points 16 et 17 dans le codec (format v3)

- Format v3 (branche seulement) : en-tête de 22 octets, octet 20 = log2(états) (3, 4, 5),
  octet 21 = drapeaux (bit 0 : l'état du treillis se poursuit d'une bande à l'autre, remis à 0 au
  début de chaque groupe). Le décodeur lit v2 et v3 ; l'encodeur n'écrit v3 que si ces options
  sont utilisées (`tcq_states`, `tcq_chain`) : la production reste en v2, identique au bit près
  (72 encodages), QEMU inchangé, 25 tests.
- Encodeur : `tcq_viterbi_chain`, un Viterbi sur les bandes codées d'un groupe, chaque bande
  pondérée (distorsion × u²/masque, débit × tcq_rdl·rd_lambda : par bande, le critère actuel à un
  facteur près), queues de contexte et termes inter-trame portés par chaque survivant. Le choix
  d'allocation garde son estimation par bande (Viterbi depuis l'état 0).
- Aller-retour : les flux v3 se décodent sans désynchronisation (un écart d'état décalerait la
  lecture des signes et ferait échouer le contrôle d'intégrité des paquets). À réglages égaux, la
  chaîne dépense environ 0,8 % de bits en plus pour 0,2 dB de rapport signal-sur-bruit : seule
  la mesure à débit égal tranche.

### Résultats à débit égal (`p4_compare.py`, + = mieux, intervalles bootstrap à 95 %)

`dev` (66 extraits, `b2_dev.csv`, `b3_dev.csv`), contre la production :

| Variante | ODG @128 | ODG @160 | ODG avancé @128 | 2f @128 | NMR @128 | ViSQOL @128 | régressions |
|---|---|---|---|---|---|---|---|
| c8 (chaîne, 8 états) | +0,015 [+0,010 ; +0,020] | −0,001 | +0,005 | +2,4 | +0,07 dB | 0,000 | 1 (triangles −0,055) |
| c16 | +0,026 [+0,017 ; +0,035] | +0,008 | +0,013 | +3,2 | +0,12 dB | +0,001 | 0 |
| c32 | +0,037 [+0,028 ; +0,046] | +0,009 | +0,018 | +4,3 | +0,18 dB | +0,002 | 0 |
| **c64** | **+0,040 [+0,029 ; +0,051]** | **+0,016** | **+0,022** | **+4,6** | **+0,20 dB** | +0,002 | 0 |
| s32 (32 états sans chaîne) | +0,012 | +0,006 | +0,010 | +0,8 | +0,04 dB | +0,001 | 0 |

c64 contre c32 : +0,003 [−0,000 ; +0,007] @128, +0,007 @160 : les rendements diminuent, on
s'arrête à 64 états. Débit à réglages égaux : +0,44 % (la chaîne), compensé par l'interpolation
à débit égal.

**Confirmation sur `test`** (30 extraits jamais utilisés pour régler, `b3_test.csv`) :

| Variante | ODG @128 | ODG @160 | ODG avancé @128 / @160 | 2f @128 | ViSQOL @128 | NMR @128 | Zimtohrli ×1000 @128 |
|---|---|---|---|---|---|---|---|
| c32 | +0,032 [+0,015 ; +0,048] | +0,014 | +0,036 / +0,015 | +4,6 | +0,004 | +0,17 dB | +0,009 [−0,001 ; +0,020] |
| **c64** | **+0,038 [+0,020 ; +0,058]** | **+0,021** | **+0,041 / +0,017** | **+5,6** | **+0,005** | **+0,18 dB** | +0,010 [−0,003 ; +0,023] |

- Toutes les mesures vont dans le même sens, à 128 et 160 kb/s ; seul Zimtohrli reste neutre à
  légèrement favorable (il juge ces débits presque transparents : distance 0,0005 à 119 kb/s,
  1/1000 de son échelle).
- Une « régression » : `b_lebanon_hanover` (−0,10 d'ODG basique), où l'ODG avancé progresse au
  contraire nettement (−0,40 → −0,15 à q −6) : désaccord des deux modèles de PEAQ sur ce morceau
  dense, pas un défaut net.
- **c64 est retenu comme candidat v3** : +0,04 d'ODG à 128 kb/s, le plus grand gain de
  l'encodeur depuis la TCQ elle-même (+0,06), au-dessus du seuil de +0,01 sur `dev` et `test`.

### Le décodeur

- QEMU (Cortex-M3, abba q −12, 10 s) : les flux v2, c32 et c64 se décodent au bit près (même
  empreinte que sur le PC).
- Le pas du treillis passe par une table de transitions par décodeur (64 × 4 octets, remplie à
  l'initialisation) : 902 112 instructions par trame en v2 contre 914 197 sur `main` (−1,3 %),
  902 574 en c64. Aucun coût de calcul ; 256 octets d'état en plus.

## M6 autour de c64 (réglage conjoint, nuit du 18 au 19/11/2026)

CMA-ES (`eval/m6_tune.py --base tcq_chain=1,tcq_states=64 --tag v3`), 10 générations de 8,
débit encadré par candidat (120 et 136 kb/s), moitié paire de `dev` (33 extraits). Meilleur
point (génération 8) : tcap_db 23,3, mid_db 4,21, fft_noise_db 4,89, rd_lambda 2,66,
tcq_rdl 0,443, **+0,0041** sur l'ensemble de recherche (objectif ODG + ODG avancé).

Validation (`m6v3_validation.log`), contre c64 à débit égal :

| Ensemble | ODG @128 | ODG @160 | ODG avancé @128 | 2f @128 | ViSQOL @128 | NMR @128 |
|---|---|---|---|---|---|---|
| `dev`, moitié non vue (33) | −0,002 [−0,014 ; +0,007] | −0,003 | +0,009 | −0,3 | −0,002 | +0,07 dB |
| `test` (30) | −0,005 [−0,011 ; +0,001] | −0,005 | +0,001 | −1,0 | −0,005 | +0,06 dB |

**Rejeté** : le gain de la recherche ne se retrouve pas sur les extraits non vus (surajustement
à 33 extraits ; une régression, `violin` −0,12). Les réglages déplacent des bits (−4 % à
réglages égaux, rd_lambda plus fort) au profit du NMR sans que PEAQ ni ViSQOL ne suivent. Comme
sur v2 (+0,0006), les réglages de production sont déjà près de l'optimum, treillis compris.

## Bilan au 19/11/2026

**Candidat v3** (branches `v3-tcq` et `v3-a8`, rien dans `main` ni dans le firmware) :

1. Treillis à 64 états en chaîne, Viterbi conjoint par groupe (points 16 et 17) : **+0,038
   d'ODG à 128 kb/s sur `test`** (+0,021 à 160), toutes les mesures d'accord. Décodeur : une
   table de 256 octets, aucun coût de calcul.
2. Alphabet de 8 symboles pour les coefficients (point 13, `C-LOG.md`) : neutre à légèrement
   favorable en qualité (+0,002 d'ODG, −0,16 % de débit), **−7,4 % d'instructions** au décodage,
   −1,5 Kio de RAM et de tables.

Les deux se décodent au bit près sur QEMU (Cortex-M3). En réserve : mise à jour des modèles un
symbole sur deux (−9,6 % d'instructions pour +0,32 % de débit), contextes selon la parité de
l'état (−0,4 % de débit pour 3 Kio). Écartés : M1 à M8, M6 (deux fois).

Restant à décider : fusionner `v3-a8` dans `v3-tcq`, figer le format v3 (en-tête, drapeaux),
le confirmer sur `test` en combinaison (seul c64 l'a été ; a8 l'a été sur `dev`), puis le porter
dans le firmware (branche Mule).

## Combinaison c64 + alphabet 8 sur `test`, avec Opus et Vorbis (19/11/2026)

`a8_test.csv` (MULE, depuis la branche `v3-a8`) et `ref_test.csv` (opusenc VBR --music 112 à
176 kb/s, oggenc q3 à q6), 30 extraits. Valeurs interpolées à débit égal :

| Codec | ODG @128 | ODG avancé @128 | ViSQOL @128 | NMR @128 | ODG @160 | ODG avancé @160 | ViSQOL @160 |
|---|---|---|---|---|---|---|---|
| MULE v2 (production) | −0,211 | −0,394 | 4,602 | −3,39 dB | −0,033 | −0,158 | 4,632 |
| MULE c64 | −0,173 | −0,354 | 4,606 | −3,57 dB | −0,012 | −0,140 | 4,634 |
| **MULE c64 + a8** | **−0,175** | **−0,353** | **4,606** | **−3,58 dB** | **−0,018** | **−0,141** | **4,634** |
| Opus | −0,116 | −0,441 | 4,540 | −2,41 dB | +0,001 | −0,238 | 4,656 |
| Vorbis | −0,449 | −0,631 | 4,474 | −0,60 dB | −0,164 | −0,339 | 4,619 |

Écarts par extrait (`p4_compare.py`, + = mieux pour la première) :

- c64+a8 contre c64 : ODG −0,002 [−0,007 ; +0,002] @128, −0,006 [−0,012 ; −0,001] @160, ODG
  avancé +0,001 / −0,000 : l'alphabet coûte au plus quelques millièmes d'ODG à 160.
- c64+a8 contre la production : **+0,036 [+0,013 ; +0,056] @128**, +0,015 @160, ODG avancé
  +0,041 / +0,017, ViSQOL +0,005, NMR +0,19 dB (une régression : `b_lebanon_hanover`, comme c64).
- c64+a8 contre Opus : ODG −0,058 [−0,106 ; −0,013] @128, −0,019 [−0,060 ; +0,023] @160 ; ODG
  avancé +0,088 / +0,097 ; ViSQOL +0,066 @128, −0,021 @160 ; 2f −12 ; NMR +1,2 / +2,4 dB.
- c64+a8 contre Vorbis : ODG +0,27 @128, +0,15 @160 ; toutes les mesures en faveur de MULE.

Le treillis réduit l'écart avec Opus en ODG basique d'environ 40 % (−0,095 → −0,058 @128) ; à
160 kb/s l'écart n'est plus significatif. Les modèles se contredisent toujours (ODG avancé, NMR
et ViSQOL @128 pour MULE ; ODG basique et 2f pour Opus) : à ces débits, MULE et Opus restent
dans le même mouchoir, Vorbis nettement derrière.

## Gel de la v3 et vitesse de l'encodeur (19/11/2026)

- **Format v3 imposé** (`2a11735`) : l'encodeur écrit toujours la v3 (64 états en chaîne,
  coefficients sur 8 symboles) ; le décodeur lit encore la v2 (vecteurs gelés dans
  `tests/vectors/v2`). `spec/FORMAT.md` décrit la v3. Retirés : la mise à jour des modèles un
  symbole sur N (non retenue) et `rd_viterbi` (M3). QEMU : au bit près, 840 050 instructions par
  trame (−8,1 % contre la v2 de `main`), 49 368 octets d'état.
- **Diagnostic de l'écart avec Opus** (`D-LOG.md`) : aucun outil de qualité n'entre dans la v3.
- **Treillis de 48 états** (simulateur, `(2s + br) mod 48`, 8 masques valides) : moins bon que
  32 états (+0,12 dB à 1,25 bit contre +0,17 ; 64 états +0,23). Écarté.
- **Vitesse de l'encodeur** (64 états : 1,9× le temps réel contre 6,3× pour la v2) :
  - Viterbi réécrit, les candidats de chaque sous-ensemble calculés une fois par coefficient :
    sortie identique au bit près, environ +30 % (`95ee8d8`).
  - `tcq_rd_states` : le choix a−1 / a / a+1 estimé sur un treillis plus petit, le codage gardant
    64 états. À débit égal sur `dev` (`rd_dev.csv`), contre c64 avec estimation sur 64 états :

| Variante | vitesse | ODG @128 | ODG @160 | ODG avancé @128 | ViSQOL @128 | NMR @128 |
|---|---|---|---|---|---|---|
| c64, estimation 64 états | 1,0 | — | — | — | — | — |
| **c64, estimation 8 états** | **2,0** | **+0,000** [−0,002 ; +0,003] | −0,005 | −0,003 | +0,001 | −0,03 dB |
| c64, estimation 16 états | 1,7 | −0,000 | −0,002 | −0,002 | +0,002 | −0,02 dB |
| c32 | 1,6 | −0,004 | −0,007 | −0,003 | −0,001 | −0,02 dB |
| c32, estimation 8 états | 2,4 | −0,005 | −0,004 | −0,007 | +0,001 | −0,07 dB |

  L'estimation sur 8 états devient le réglage par défaut : **3,9× le temps réel**, sans perte
  mesurable (tous les écarts sous le seuil de 0,01). 32 états perdent un peu plus pour un gain
  de vitesse moindre.

## Quatre règles au lieu de deux (simulateur, 20/11/2026)

`eval/tcq_rules_sim.py` : le modèle de `tcq_sim.py` généralisé à K règles (grille au pas D/K,
2K sous-ensembles, la règle imposée par l'état modulo K, chaque règle au pas D). Avec K = 2, il
redonne les chiffres ci-dessus (−0,05 dB à 1,25 bit en v2, +0,23 dB à 64 états en chaîne). Masque
de chaque configuration par recherche exhaustive. Gain d'erreur sur le scalaire à entropie
égale (dB) :

| | 1,0 bit | 1,25 bit | 1,5 bit | 2,0 bits |
|---|---|---|---|---|
| 2 règles, 8 états, redémarré | −0,49 | −0,05 | +0,29 | +0,68 |
| 4 règles, 8 états, redémarré | −0,43 | −0,02 | +0,29 | +0,65 |
| 2 règles, 8 états, chaîne | −0,48 | +0,04 | +0,41 | +0,82 |
| 4 règles, 8 états, chaîne | −0,41 | +0,06 | +0,41 | +0,81 |
| 2 règles, 32 états, chaîne | −0,41 | +0,17 | +0,57 | +0,95 |
| 4 règles, 32 états, chaîne | −0,37 | +0,20 | +0,58 | +0,96 |
| 2 règles, 64 états, chaîne | −0,37 | +0,23 | +0,61 | +1,01 |
| 4 règles, 64 états, chaîne | −0,32 | +0,23 | +0,62 | +0,99 |

À 1,25 bit (le régime de MULE), quatre règles gagnent de +0,01 à +0,03 dB sur deux, soit
environ 0,005 bit par coefficient, très loin du seuil de 2 % du débit ; à 2 bits, rien ou moins.
C'est le résultat connu d'Ungerboeck (doubler l'alphabet donne l'essentiel du gain). Trois règles
sur quatre n'ont pas de zéro et paient le signe des petites valeurs. Écarté, sans essai dans le
codec. Réserve : le treillis à quatre règles garde la structure à deux branches par état de
MULE ; un treillis conçu autrement pourrait faire un peu mieux, sans changer l'ordre de grandeur.
