# Optimisation de l'encodeur, axes 1 et 3 (17/11/2026)

Encodeur seul : le format v2, le décodeur et le firmware ne changent pas. Réglages sur `dev` (66 extraits), validation sur `test` (30 extraits jamais utilisés pour régler). Comparaison à débit égal (`eval/p4_compare.py`, intervalles de confiance à 95 % par rééchantillonnage des extraits, 4 qualités par variante). Référence : la production v2 (`e_base_dev.csv`, `v2_test.csv`).

Nouveaux paramètres de l'encodeur C (`core/mule_enc.h`), tous désactivés par défaut, donc sans effet sur la production tant qu'ils ne sont pas adoptés :

| Paramètre | Rôle |
|---|---|
| `tcq_rd`, `tcq_rdl` | axe 3 : Viterbi avec le débit des modèles suivis (contexte de chaque survivant d'après ses deux dernières magnitudes, contexte inter-trame, échappements, signe), niveaux le plus proche et ±4 ; poids du débit relatif à `rd_lambda` |
| `rd_span` | axe 3 : allocation RD cherchée sur a ± span (production : 1) |
| `fine_p`, `fine_w`, `fine_nb`, `fine_ton` | axe 1 : masques par sous-bandes de `fine_w` raies (étalement en Bark comme densité, tonalité de la bande), la cible d'une bande étant leur moyenne de puissance d'exposant −`fine_p` ; seulement sous la bande `fine_nb` |
| `lf_min_a` | essai : allocation minimale dans les bandes 0-7 (pas de bruit de remplacement) |

Outil ajouté : `eval/item_sweep.py` (un extrait, plusieurs jeux de paramètres, ODG interpolé à un débit commun).

## Axe 3 : optimisation débit-distorsion conjointe (`dev`)

| Variante | ODG @128 | @160 | ODG avancé @128 | @160 | Débit à réglage égal | Régressions |
|---|---|---|---|---|---|---|
| r025 (`tcq_rdl` 0,25) | +0,006 | −0,011 | −0,009 | −0,004 | +2,5 % | 0 |
| **r05** (0,5) | +0,001 | −0,003 | **+0,012** | **+0,005** | −0,4 % | 0 |
| r1 (1,0) | −0,060 | −0,030 | +0,013 | −0,007 | −5,7 % | 31 |
| sp2 (`rd_span` 2) | +0,002 | −0,008 | +0,019 | −0,001 | −5,2 % | 2 (piano, Liszt) |
| r05sp2 | +0,010 | −0,007 | +0,031 | +0,004 | −4,3 % | 1 (Liszt) |

Gain faible, significatif seulement en ODG avancé pour r05. Un poids du débit égal à celui de l'allocation (r1) retire trop de coefficients. La recherche élargie (sp2) régresse sur le piano.

## Axe 1 : sons tonals clairsemés

**Masque fin dans les aigus (sous-bandes de 8 raies) : rejeté.** −0,02 d'ODG @128, −0,03 à −0,05 en ODG avancé ; aide le glockenspiel (+0,13), dégrade les triangles (−0,11 à −0,16) et l'orchestre (−0,14). Une première version, avec la tonalité mesurée sur 8 raies, divisait le débit par deux (les partiels n'y paraissent plus tonals) : la tonalité est prise sur la bande entière.

**Diagnostic des triangles** (`eval/p4_diag.py`, MULE q −12 à 97 kb/s contre Vorbis q4 à 104 kb/s) : dans les aigus, le NMR de MULE est meilleur que celui de Vorbis (−15 contre −5 dB). La perte est **dans les graves** : de 65 à 430 Hz, MULE est à −2/−4 dB (jusqu'à 9 % des trames au-dessus du masque), Vorbis à −15/−22 dB. Balayage sur l'extrait seul, ODG à 100 kb/s : référence −1,22 ; `low_db` 0 : −2,12 ; `low_db` 20 : −1,07 ; `tcap_db` 15 : −1,14 ; `lf_min_a` 8 : −1,14 (le remplacement par du bruit n'est pas la cause) ; regroupement, stéréo, λ : effet faible.

**Cause** : les bandes graves ont 8 raies (172 Hz, près de 2 Bark à ces fréquences). Le masque, calculé sur l'énergie de la bande entière, suppose le bruit masqué partout, alors qu'une composante grave localisée ne masque que son voisinage.

**Masque raie par raie dans les bandes basses** (`fine_w` 1) :

| Variante | ODG @128 | @160 | ODG avancé @128 | @160 | Débit | Régressions |
|---|---|---|---|---|---|---|
| lf4 (p 4, 8 bandes) | +0,014 | +0,007 | +0,007 | +0,005 | +0,3 % | 0 |
| lf8 (p 8, 8 bandes) | +0,013 | +0,007 | +0,008 | +0,005 | +0,5 % | 0 |
| lf8n12 (12 bandes) | +0,019 | +0,007 | +0,011 | +0,007 | +0,9 % | 0 |
| lf8n16 (16 bandes) | +0,020 | +0,008 | +0,009 | +0,005 | +1,7 % | 0 |
| lf8r05 | +0,015 | +0,005 | +0,020 | +0,010 | +0,1 % | 0 |
| **lf8n12r05** | **+0,021** | **+0,007** | **+0,023** | **+0,012** | +0,5 % | 0 |
| lf8n16r05 | +0,022 | +0,009 | +0,021 | +0,010 | +1,3 % | 0 |
| lf16n12r05 | +0,020 | +0,004 | +0,023 | +0,011 | +0,8 % | 0 |

Meilleurs extraits (lf8n12r05) : orchestre +0,21, triangles +0,20, violon +0,11. Retenue pour la validation : **lf8n12r05**, le meilleur compromis, sans hausse de débit notable.

Coût : l'encodage d'un extrait de 10 s passe de 2,0 à 3,2 s (machine chargée), encore environ trois fois le temps réel.

## Validation sur `test` (lf8n12r05 contre la production v2, 30 extraits)

| Mesure | @128 kb/s | @160 kb/s |
|---|---|---|
| ODG | **+0,007** [+0,002, +0,013] | +0,006 [−0,002, +0,016] |
| ODG avancé | **+0,020** [+0,016, +0,024] | **+0,007** [+0,006, +0,008] |
| ViSQOL | −0,005 [−0,009, −0,001] | −0,002 [−0,005, +0,001] |
| NMR (dB, + = mieux) | +0,20 | +0,18 |

Débit à réglage égal : +0,3 %. Aucune régression (< −0,05 d'ODG). Meilleurs extraits : Belenos +0,08, Takemitsu +0,06, Holst +0,04.

Le gain est plus faible que sur `dev` : `test` est tiré au hasard dans la bibliothèque et contient peu de sons du type des triangles ou de l'orchestre, où le gain se concentre. La baisse de ViSQOL est négligeable (0,005 sur une échelle où MULE est à 4,6).

## Conclusion

- **Axe 1** : la cause du point faible des triangles est trouvée. Ce n'était pas les partiels aigus, mais la résolution du masque dans les graves. Le masque raie par raie dans les 12 bandes basses la corrige en partie (+0,20 d'ODG sur les triangles, +0,21 sur l'orchestre, à débit égal).
- **Axe 3** : le treillis à coûts exacts apporte un petit gain, surtout en ODG avancé.
- **Combinaison lf8n12r05** : gain confirmé sur `test`, sans régression, sans changement de format. Proposition : en faire le réglage par défaut de l'encodeur C (`fine_p` 8, `fine_w` 1, `fine_nb` 12, `tcq_rd` 1, `tcq_rdl` 0,5), puis une écoute ABX des triangles et de l'orchestre.

## Décision (17/11/2026) : lf8n12r05 devient le réglage par défaut de l'encodeur C

Valeurs de production : `fine_p` 8, `fine_w` 1, `fine_nb` 12, `tcq_rd` 1, `tcq_rdl` 0,5 (`mule_enc_defaults`, et `None` dans `Params` → la valeur de production, comme `rd_lambda`). L'encodeur Python (prototype) ne les implémente pas ; le test d'égalité C/Python les désactive. Le format, le décodeur et le firmware ne changent pas.

Jeu `test` (30 extraits), à débit égal :

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | NMR @128 | @160 |
|---|---|---|---|---|---|---|---|---|
| Vorbis | −0,449 | −0,164 | −0,631 | −0,339 | 4,474 | 4,619 | −0,6 | −3,0 |
| Opus | **−0,118** | **0,000** | −0,446 | −0,241 | 4,539 | **4,654** | −2,4 | −4,3 |
| MULE v2 (avant) | −0,234 | −0,053 | −0,425 | −0,168 | **4,607** | 4,634 | −3,2 | −6,3 |
| **MULE v2 (encodeur actuel)** | −0,227 | −0,047 | **−0,405** | **−0,161** | 4,602 | 4,632 | **−3,4** | **−6,5** |
