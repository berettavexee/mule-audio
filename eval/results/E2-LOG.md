# Axe 2 : l'écart avec Opus en ODG de base (17/11/2026)

Encodeur seul : le format v2, le décodeur et le firmware ne changent pas. Même méthode que l'axe 1 (`E-LOG.md`). Référence : la production après l'axe 1 (lf8n12r05), `e2_base_dev.csv`.

## Étape 0 : diagnostic par les MOV de PEAQ

Outils :
- `third_party/gstpeaq/src/peaq.c` (local, non publié) : la variable `PEAQ_MOVS` fait afficher les 11 MOV du mode de base ;
- `eval/peaq_movs.py` : les MOV par configuration (`run`), puis l'écart MULE/Opus à débit égal attribué à chaque MOV (`gap`). Le réseau de PEAQ est réévalué avec une MOV de MULE remplacée par celle d'Opus. Sa réimplémentation donne l'ODG de GstPEAQ à 10⁻⁴ près.
- `eval/metrics.py` : un `peaq` resté bloqué plus d'une heure, sans consommer de processeur (deux fois, dont un orphelin de 15 h), a arrêté une évaluation. Chaque appel à PEAQ et à ViSQOL a désormais un délai maximal, avec deux nouvelles tentatives.

Résultat sur `dev` (66 extraits, interpolation par extrait) :

| MOV | MULE @128 | Opus @128 | Gain d'ODG si MULE avait la valeur d'Opus @128 | @160 |
|---|---|---|---|---|
| **ADBB** (distorsion moyenne des trames dégradées) | 0,434 | −0,154 | **+0,066** | **+0,068** |
| **BandwidthTestB** | 833 | 871 | **+0,025** | 0,000 |
| Total NMRB | −14,9 | −14,0 | −0,033 (MULE meilleur) | −0,029 |
| EHSB | 0,259 | 0,244 | +0,007 | 0,000 |
| autres (modulation, sonie du bruit, MFPD, trames dégradées) | | | < 0,005 chacune | < 0,01 |

ODG mesuré : MULE −0,268, Opus −0,207 à 128 kb/s ; −0,131 et −0,090 à 160 kb/s.

Lecture :
- **ADB** : MULE a moins de bruit au total (son NMR total est meilleur), mais il le concentre davantage dans certaines trames. C'est le levier principal.
- **Bande passante** : MULE s'arrête à 19,95 kHz (la dernière bande du format finit au coefficient 928), Opus monte à environ 20,4 kHz. C'est inaudible, mais PEAQ le compte (+0,025 à 128 kb/s). Le corriger demande un changement de format ; c'est noté pour une v3.

Extraits où Opus mène le plus à 128 kb/s : Joy Division +0,36, pitchpipe +0,28, Wolfmother, Moussorgski, voix féminine +0,21. Diagnostic par bande (`p4_diag.py`, MULE q −12 contre Opus 160) :
- **voix féminine** : MULE dépasse le masque dans 2 à 8 % des trames, **dans toutes les bandes à la fois** (Opus : 0 à 2 %). Ce sont des trames entières, aux attaques : du pré-écho dans des trames longues que le détecteur ne fait pas passer en blocs courts ;
- **pitchpipe** : MULE juge que 11 kb/s suffisent, contre 133 kb/s pour Opus, et dépasse le masque entre 2,7 et 6 kHz : un contenu tonal clairsemé, comme les triangles. L'écart à débit égal y est en partie extrapolé, car MULE n'atteint pas 128 kb/s sur cet extrait ;
- **Joy Division** : les deux codecs dépassent le masque entre 6 et 10 kHz, sans différence de nature.

## Levier A : contrôle du pré-écho (`pre_db`)

Principe d'AAC (`rpelev`) : dans une trame longue, le masque d'une bande ne peut pas dépasser celui de la trame longue précédente de plus de `pre_db` dB. La première trame longue après des blocs courts n'est pas limitée.

Voix féminine seule (ODG à 128 kb/s) : référence −0,138 ; 3 dB : −0,064 ; 6 dB : −0,077 ; 10 dB : −0,107 ; 15 dB : −0,104.

Sur `dev`, à débit égal, contre la production (`e2_base_dev.csv`) :

| `pre_db` | ODG @128 | @160 | ODG avancé @128 | @160 | Débit | Régressions |
|---|---|---|---|---|---|---|
| 3 | −0,013 | +0,004 | −0,004 | −0,010 | +4,2 % | 0 |
| 6 | +0,005 | +0,014 | +0,010 | 0,000 | +1,5 % | 0 |
| 8 | +0,008 | +0,015 | +0,013 | +0,002 | +0,8 % | 0 |
| **10** | **+0,008** | **+0,015** | **+0,012** | **+0,003** | +0,4 % | 0 |
| 13 | +0,008 | +0,012 | +0,010 | +0,003 | +0,2 % | 0 |
| 16 | +0,006 | +0,008 | +0,006 | +0,002 | +0,1 % | 0 |
| 20 | +0,003 | +0,003 | +0,002 | +0,001 | 0,0 % | 0 |

Retenu : **10 dB**. Tous les intervalles de confiance sont positifs. Meilleurs extraits : Baroness +0,09, voix féminine +0,06, piano +0,06, Wolfmother +0,06, Slayer +0,05.

Incident : la référence a d'abord échoué, parce que les 12 processus ont recompilé `build/libmule.so` en même temps (« file too short »). `py/mule/native.py` prend désormais un verrou de fichier pendant la recompilation.

## Le cas du pitchpipe

PEAQ basique donne −3,9 à MULE à tous les réglages (9 à 12 kb/s), mais aussi −3,3 à −3,9 à Opus de 96 à 192 kb/s, alors que PEAQ avancé donne +0,16 à MULE. L'erreur de MULE est faible trame par trame (sons identiques à 0,1 dB près au spectre), avec un plancher de bruit très bas autour des sons du sifflet. C'est un extrait limite pour PEAQ basique, et son poids dans l'écart vient surtout de l'extrapolation (MULE n'y atteint jamais 128 kb/s). Il n'est pas pris comme cible.

## Levier B : tonalité par prédictibilité (`unpred`) — rejeté

Modèle 2 de MPEG : l'amplitude et la phase de chaque raie FFT sont prédites à partir des deux trames précédentes, et l'imprévisibilité, pondérée par l'énergie, donne la tonalité de la bande (`tb = −0,299 − 0,43 ln cb`). Mode 1 : elle remplace la platitude ; 2 : on prend la plus grande des deux ; 3 : leur moyenne.

Extraits seuls (ODG @128, avec `pre_db` 10) : triangles −0,78 → −0,70 (modes 1 et 2) ; glockenspiel −0,31 → −0,37 (mode 1), −0,30 (mode 2) ; voix féminine −0,107 → −0,092 (mode 2).

Sur `dev`, contre `pre_db` 10 :

| Mode | ODG @128 | @160 | ODG avancé @128 | @160 | Débit | Régressions |
|---|---|---|---|---|---|---|
| 2 (maximum) | −0,005 | −0,007 | −0,005 | −0,003 | +1,2 % | 0 |
| 3 (moyenne) | −0,014 | −0,003 | +0,009 | +0,004 | −2,9 % | 6 (trompette −0,25, violon −0,24, Vivaldi −0,09…) |

Le vibrato des cordes et des cuivres les rend imprévisibles d'une trame à l'autre : ils passent pour du bruit et perdent des bits. La platitude reste la meilleure estimation, et le masque fin dans les aigus, qui en dépendait, n'est pas repris.

## Levier C : niveau du bruit de remplacement (`nf_bias`)

Pour les bandes non codées (allocation nulle), l'énergie transmise est abaissée de `nf_bias` crans de 1,5 dB. L'allocation est désormais calculée avant l'écriture des énergies. Cette réorganisation ne change rien au flux : la sortie est identique au bit près à celle de l'encodeur commité, vérifié sur 3 extraits et 2 qualités contre une bibliothèque compilée depuis `6f4fdc2`.

Sur `dev`, contre `pre_db` 10 :

| `nf_bias` | ODG @128 | @160 | ODG avancé @128 | @160 | Débit | Régressions |
|---|---|---|---|---|---|---|
| 1 (−1,5 dB) | +0,005 | +0,005 | +0,011 | +0,005 | 0,0 % | 0 |
| **2 (−3 dB)** | **+0,005** | **+0,006** | **+0,015** | **+0,006** | +0,1 % | 0 |
| 3 (−4,5 dB) | +0,002 | +0,004 | +0,014 | +0,005 | +0,2 % | 0 |
| 4 (−6 dB) | −0,004 | +0,002 | +0,011 | +0,004 | +0,3 % | 3 (orchestre −0,07, trompette, The Killers) |

Retenu : **2 crans (−3 dB)**. Meilleurs extraits : triangles +0,18, glockenspiel +0,06.

## Leviers D et E : étalement du masquage — rejetés

- **D, pentes de Terhardt** (`spread_lvl`) : pente basse de 27 dB/Bark, pente haute de 24 + 230/f − 0,2 L, le niveau L du masqueur pris en dB SPL (pleine échelle 96 dB), au lieu de la fonction de Schroeder.
- **E, addition en loi de puissance** (`mask_alpha`) : (Σ (w E)^α)^(1/α) au lieu de la somme.

Les deux décalent la calibration : environ +30 % de débit pour D ; −40 % (α = 0,5) à −80 % (α = 0,3) pour E. Les réglages de qualité ont donc été décalés pour couvrir la même plage de débits (D : +3 dB ; E, α 0,7 : −3 dB ; α 0,5 : −6 dB). Les moyennes à débit égal restent valables, mais pas le comptage des régressions par extrait, qui apparie les réglages par leur nom.

| Variante (avec `pre_db` 10, `nf_bias` 2) | ODG @128 | @160 | ODG avancé @128 | @160 |
|---|---|---|---|---|
| Terhardt | +0,004 (n.s.) | −0,009 (n.s.) | −0,006 | −0,009 |
| α = 0,7 | −0,026 | +0,004 | −0,033 | −0,016 |
| α = 0,5 | −0,185 | −0,122 | −0,220 | −0,080 |

## Levier F : recalibrage des décalages et du seuil des transitoires — rien à changer

`tr_db` (seuil du détecteur de transitoires, 10 dB jusqu'ici, rendu réglable). Contre `pre_db` 10 + `nf_bias` 2, sur `dev` :

| Variante | ODG @128 | @160 | ODG avancé @128 | @160 |
|---|---|---|---|---|
| `tcap_db` 20 | −0,006 | +0,003 | +0,006 | +0,004 |
| `tcap_db` 30 | −0,003 | −0,008 | −0,011 | −0,008 |
| `mid_db` 2 | −0,001 | +0,007 | +0,008 | −0,003 |
| `mid_db` 6 | −0,013 | −0,016 | −0,007 | −0,007 |
| `low_db` 8 | −0,002 | +0,007 | −0,004 | −0,002 |
| `low_db` 12 | −0,005 | −0,008 | +0,001 | −0,001 |
| `tr_db` 7 | −0,004 | −0,004 | −0,005 | −0,002 |
| `tr_db` 8,5 | −0,001 | −0,001 | −0,002 | −0,001 |

Aucun ne bat le réglage actuel de façon significative : le calibrage est déjà au bon endroit.

## Validation sur `test` (30 extraits, contre la production de l'axe 1)

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | Régressions |
|---|---|---|---|---|---|---|---|
| `pre_db` 10 | **+0,010** | **+0,014** | +0,011 | +0,004 | **0,000** | **0,000** | 0 |
| `pre_db` 10 + `nf_bias` 2 | +0,013 | +0,019 | +0,021 | +0,008 | **−0,029** | **−0,030** | 0 |

Le biais du bruit de remplacement gagne encore un peu en PEAQ, mais fait perdre 0,03 à ViSQOL (intervalle de confiance entièrement négatif). PEAQ et ViSQOL se contredisent : seule l'écoute peut trancher.

## Décision (17/11/2026)

- **`pre_db` 10 devient le réglage par défaut de l'encodeur C.** Il gagne sur `dev` et sur `test`, sans régression et sans perte en ViSQOL. `Params.pre_db` vaut `None` (la valeur de production) ; le test d'égalité C/Python le désactive.
- **`nf_bias` reste désactivé**, en attendant une écoute ABX : ancien encodeur contre `nf_bias` 2, sur les triangles, le glockenspiel et deux morceaux de `test`. Si l'écoute lui donne raison, la bonne solution serait un gain de bruit transmis à part, en v3 (`docs/V3-IDEAS.md`, point 2), plutôt qu'une énergie faussée.

## Levier G : seuil absolu d'audition — rejeté

`ath_db` (décalage du seuil absolu) et `ath_mode` 1 (seuil d'une bande pris comme moyenne en puissance sur la bande, au lieu de son point le plus sensible). Sur `dev`, contre la production (`pre_db` 10) :

| Variante | ODG @128 | @160 | ODG avancé @128 | @160 | Débit | Régressions |
|---|---|---|---|---|---|---|
| −6 dB | −0,009 | −0,003 | −0,012 | −0,006 | +5,3 % | 5 (orchestre −0,38, glockenspiel −0,19…) |
| −3 dB | −0,001 | +0,001 | −0,004 | −0,002 | +2,6 % | 5 |
| +3 dB | −0,003 | −0,006 | 0,000 | −0,004 | −2,5 % | 1 |
| +6 dB | −0,011 | −0,024 | −0,005 | −0,019 | −4,9 % | 4 |
| moyenne sur la bande | −0,589 | −0,628 | −0,520 | −0,452 | −12,5 % | 64 |

Le seuil actuel est le bon. Le prendre au point le plus sensible de la bande est indispensable.

## Levier H : répartition des bits entre trames (`short_db`) — non adopté

L'encodeur vise déjà le même rapport bruit/masque dans toutes les trames, ce qui est optimal pour le bruit moyen. Essai : une cible de bruit décalée pour les trames en blocs courts (les attaques). Sur `dev`, contre la production :

| `short_db` | ODG @128 | @160 | ODG avancé @128 | @160 | Débit | Régressions |
|---|---|---|---|---|---|---|
| +1,5 | −0,006 | −0,007 | −0,006 | −0,004 | −0,3 % | 2 |
| −1,5 | +0,004 | +0,002 | +0,004 | +0,002 | +0,4 % | 0 |
| **−3** | **+0,004** | **+0,003** | **+0,008** | **+0,003** | +0,7 % | 0 |
| −5 | +0,003 | +0,004 | +0,010 | +0,004 | +1,2 % | 0 |
| −8 | −0,003 | +0,002 | +0,010 | +0,003 | +1,9 % | 0 |

Sur `test`, −3 dB : ODG +0,0015 (n.s.) / +0,007, ODG avancé +0,003 (n.s.) / −0,002 (n.s.), ViSQOL −0,0005, sans régression. L'essentiel du gain tient à un seul extrait (Lebanon Hanover +0,08). C'est au niveau du bruit de mesure : **non adopté**.

## Diagnostic final : ce qui reste de l'écart avec Opus (`dev`, encodeur de production actuel)

Écart d'ODG de base mesuré sur `dev` : **0,051 à 128 kb/s** (0,061 avant l'axe 2) et **0,026 à 160 kb/s** (0,041).

| MOV | Part de l'écart @128 | @160 |
|---|---|---|
| ADB (distorsion des trames dégradées) | +0,059 | +0,055 |
| Bande passante (limite du format) | +0,024 | 0,000 |
| Total NMR (MULE meilleur) | −0,035 | −0,031 |
| autres | < 0,01 | < 0,01 |

Extraits où Opus mène encore le plus : rock dense et saturé (Joy Division +0,35, Wolfmother, Body Count, X, Deep Purple, Slayer), voix (voix féminine +0,18), et le pitchpipe (cas limite de PEAQ). Sur le rock dense, les deux codecs dépassent le masque entre 6 et 10 kHz ; MULE dans des bandes larges (64 à 144 coefficients, soit 1,4 à 3 kHz), avec une seule énergie par bande.

**Conclusion de l'axe 2.** Les leviers de l'encodeur sont épuisés ; ce qui reste demande le format :
- **les attaques**, résolution temps-fréquence et blocs intermédiaires (`V3-IDEAS.md`, points 5 à 7) ;
- **la bande passante** (point 1, +0,024 à 128 kb/s) ;
- **le niveau du bruit de remplacement**, transmis à part (point 2), pour obtenir le gain PEAQ de `nf_bias` sans fausser l'énergie ;
- **éventuellement des bandes aiguës plus étroites**, pour le rock dense.
