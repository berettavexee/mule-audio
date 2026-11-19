# Mesures M1 à M8 (docs/V3-IDEAS.md), novembre 2026

Plan : `docs/NOTES-2026-11-18.md` § 4 et la réponse du 18/11 (ordre : outil commun, M8, M2, M7,
M1, puis M3, M6, M4, M5). Seuil retenu pour un changement de format : au moins 2 % du débit total,
confirmés sur `test`. Journaux bruts : `eval/results/m-logs/`.

## Étape 0 : la trace de l'encodeur et le banc `eval/ctx_lab.py`

- `mule_encode_trace` (`core/enc.c`, `core/mule_enc.h`) : un enregistrement par symbole de
  coefficient (trame, canal, bande, raie, classe d'allocation, queues, drapeau inter, exposant de
  remise à l'échelle, `y_prev`, index, contexte) et par résidu d'énergie. Désactivée par défaut :
  les fichiers produits sont identiques au commit précédent (72 encodages, SHA-256).
- `mule_stream_cost_each` (`core/rans.c`) : le coût de chaque symbole.
- `eval/ctx_lab.py check` : la règle actuelle reproduit **exactement** les 96 contextes de
  l'encodeur sur les 66 extraits de `dev`. Une autre règle de contexte ne change que le débit, pas
  le son : elle se mesure sans PEAQ. Chaque règle reçoit ses tables initiales, entraînées de la
  même façon sur `train` (200 extraits), puis se mesure sur `dev` avec les vrais modèles
  adaptatifs, réinitialisés à chaque paquet clé.

`dev` : 66 extraits, 942 s, 117,2 kb/s au débit par défaut (q −7), dont 68,7 kb/s de symboles de
coefficients (58,6 %).

## Phase 1 : les mesures sans changement de l'encodeur

### M8, contexte inter-trame lissé (moyenne glissante) — **écartée**

| Contexte | coefficients | total | extraits meilleurs |
|---|---|---|---|
| `y_prev` (actuel) | — | — | — |
| α = 0 (`y_prev`, remise à l'échelle en flottant) | +0,20 % | +0,12 % | 8/66 |
| α = 0,5, κ = 1 | −0,15 % | −0,09 % | 33/66 |
| α = 0,7, κ = 1 | +0,09 % | +0,05 % | 25/66 |
| α = 0,85, κ = 1 | +0,66 % | +0,39 % | 12/66 |
| α = 0,5, κ = 0,5 | +0,17 % | +0,10 % | 16/66 |
| α = 0,7, κ = 0,5 | +0,40 % | +0,24 % | 11/66 |
| α = 0,85, κ = 0,5 | +0,92 % | +0,54 % | 4/66 |
| max(`y_prev`, α = 0,5) | **−0,27 %** | **−0,16 %** | 36/66 |

La ligne α = 0 mesure le biais de la simulation (remise à l'échelle en flottant au lieu des
entiers de l'encodeur) : +0,2 %. Même corrigé, le meilleur gain reste vers 0,35 % des bits de
coefficients, loin des 6,7 % du signal synthétique (`eval/ema_context_sim.py`). Plus la mémoire
est longue, plus on perd ; κ = 0,5 est pire que κ = 1. Le contexte actuel est déjà grossier
(plafonné à 31, 6 classes) et l'adaptation des modèles absorbe le reste. Le point 27 est écarté.

### M2, la place du contexte inter-trame — **point 20 improbable**

| Trames | coefficients | bits | bit/coef |
|---|---|---|---|
| longues, avec contexte inter-trame | 90,4 % | 91,7 % | 1,252 |
| longues, sans (après un paquet clé ou des blocs courts) | 6,7 % | 5,2 % | 0,964 |
| courtes | 2,9 % | 3,0 % | 1,282 |

Les trames sans contexte inter-trame coûtent *moins* par coefficient : un effet de sélection (elles
suivent surtout les paquets clés, où les tables entraînées viennent d'être rechargées), pas la
valeur du contexte. Le contrefactuel (M2b, la même trace sans contexte inter-trame) la donne :
**+3,41 % de bits de coefficients, +2,00 % du total, les 66 extraits plus chers.** Le contexte
`y_prev` est précieux, mais tous ses raffinements mesurés (M8, M7 b) restent sous 0,3 % du total.
Un modèle harmonique (point 20) n'aurait de prise que sur les 5 % de bits sans contexte et sur ce
que `y_prev` ne capte pas : jugé improbable au-delà de 1 %, l'oracle de hauteur n'a pas été lancé.

### M7, préalables aux points 22 et 23 — **écartés**

- (b) contexte des deux côtés (n−1 et n+1, oracle) : −0,43 % des coefficients, **−0,25 % du
  total** (48/66 extraits meilleurs), pour 4 Kio de RAM de plus au décodeur. Point 23 écarté.
- (a) énergies des trames 1 et 2 d'un paquet de 4 interpolées entre les trames 0 et 3 (la trame 3
  prédite depuis la trame 0) : entropie des résidus 3,227 → 3,335 bit/bande, **+3,3 %** (+0,12 % du
  total ; estimation statique, 9 195 paquets). La prédiction actuelle (trame précédente et bande
  voisine) est meilleure. Point 22 écarté.

### M1, intervalle des paquets clés — **on garde 40 trames**

| Intervalle | kb/s | écart |
|---|---|---|
| 20 trames (0,46 s) | 116,00 | +0,34 % |
| **40 trames (0,93 s)** | **115,61** | — |
| 80 trames (1,86 s) | 115,41 | −0,17 % |
| 160 trames (3,72 s) | 115,32 | −0,26 % |

Les réinitialisations coûtaient 2,4 % en P2 ; les tables initiales entraînées ont effacé ce coût.
Doubler l'intervalle gagnerait 0,17 % et doublerait le décodage à faire avant le point d'arrivée
d'une recherche. Le point 24 (rafraîchissement progressif) n'a plus d'objet.

### Bilan de la phase 1

Aucune piste « gratuite » n'atteint le seuil de 2 %. Le codage entropique de MULE est proche de ce
que ses informations permettent : les gains restants sont dans l'encodeur (phase 2), pas dans le
format.

## Phase 2 : l'encodeur

### M3, allocation optimisée sur toute la trame

`rd_viterbi` (`core/enc.c`, `rd_alloc_viterbi`) : au lieu du choix glouton a−1 / a / a+1 bande par
bande, un Viterbi sur les bandes d'un groupe (3 états par bande, chaque survivant portant ses
queues de contexte), avec le coût différentiel de l'allocation dans les deux modes ; le mode le
moins cher est retenu. Encodage environ 3,5 fois plus lent. Évaluation : production et variante
à q −6, −9, −12, −15 sur `dev`, comparaison à débit égal (`p4_compare.py`, `m3_dev.csv`).

| Mesure (mule-rv contre production, + = mieux) | @128 kb/s | @160 kb/s |
|---|---|---|
| ODG | +0,0005 [−0,0009 ; +0,0021] | −0,0003 [−0,0017 ; +0,0012] |
| ODG avancé | +0,0013 [+0,0000 ; +0,0023] | −0,0002 [−0,0008 ; +0,0004] |
| 2f-model | −0,02 [−0,18 ; +0,13] | −0,18 [−0,56 ; +0,12] |
| ViSQOL | −0,0001 | −0,0001 |
| NMR interne (dB) | +0,013 | −0,003 |

Débit à réglages égaux −0,03 %, aucune régression. **Résultat nul** : le Viterbi retrouve presque
toujours le choix glouton, les dépendances entre bandes (queues de contexte, coût différentiel de
l'allocation) pesant trop peu. Sous le seuil de +0,01 d'ODG : `rd_viterbi` reste à 0 (le code
reste, désactivé).

### M6, réglage conjoint des paramètres (CMA-ES) — **interrompu, peu prometteur**

`eval/m6_tune.py` : `tcap_db`, `mid_db`, `fft_noise_db`, `rd_lambda` et `tcq_rdl` (à la place de
`tcq_lam`, inutilisé quand `tcq_rd` = 1), dans des bornes autour de la production. Objectif : la
moyenne de l'ODG et de l'ODG avancé à 128 kb/s à débit égal, sur la moitié paire de `dev`
(33 extraits) ; l'autre moitié et `test` réservées à la validation ; ViSQOL hors de la boucle.

- **Premier essai, faussé** (`m6_search_extrapolated.csv`) : deux qualités fixes (q −7 et −10).
  Les candidats à `rd_lambda` bas dépensent plus de bits (134 à 137 kb/s dès q −7, contre 118,6
  pour la production) : les deux points tombaient au-dessus de 128 kb/s, la valeur « à 128 »
  était extrapolée, et la courbe étant concave, surestimée. CMA-ES a exploité ce biais : +0,031
  annoncé en deux générations. Arrêté.
- **Second essai** (`m6_search.csv`) : pour chaque candidat, les qualités donnant 120 et 136 kb/s
  sont d'abord cherchées par encodages seuls (sécante sur q), puis PEAQ en ces deux points ;
  128 kb/s est toujours encadré. Production −0,3036 (q −7,19 → 120,3 kb/s, q −8,71 → 134,5).
  Génération 1 : aucun candidat meilleur ; génération 2 : +0,0006 (`tcap_db` 21,9, `mid_db` 4,2,
  `fft_noise_db` 3,5, `rd_lambda` 1,96, `tcq_rdl` 0,53), au niveau du bruit. Une génération coûte
  14 minutes : arrêté à la demande, après 2 générations sur 15. Peut se relancer une nuit
  (`python eval/m6_tune.py search --gens 15 --pop 10`, environ 3 h 30).

Leçon de méthode : un objectif « à débit égal » doit encadrer le débit visé pour chaque candidat,
sinon l'optimiseur trouve le biais de l'interpolation avant les vrais gains.

### M5, coût futur des contextes dans le Viterbi TCQ — **écarté**

Trace étendue (format 2 : niveau TCQ, valeur avant quantification, poids débit-distorsion de la
bande, drapeau M/S des bandes). `ctx_lab.py m5` : changer un index de ±1 modifie le contexte du
coefficient de la trame suivante (même raie) dans 72,7 % des cas, de 0,12 bit en moyenne ; la
borne brute (chaque coefficient suivant obtenant gratuitement le voisin le moins cher) est 7 % de
leurs bits, sans signification puisqu'elle ignore le coût du changement. `ctx_lab.py m5b` : un
changement de niveau voisin (|k| ± 2, même union) coûte sa distorsion et ses bits ; ne sont
comptés que ceux qui ne deviennent rentables que par le terme de la trame suivante (le symbole
suivant supposé connu, le chemin du treillis ignoré : borne optimiste). **0,12 % des
coefficients, 0,01 % du débit total.**

### M4, décisions de trame — **écarté**

`ctx_lab.py m4` :
- (a) α (poids de prédiction des énergies) n'a pas d'effet d'une trame à l'autre (les énergies
  mémorisées n'en dépendent pas) : un Viterbi n'y ajoute rien. Le choisir sur les vrais coûts
  (statiques) au lieu de l'approximation Σ log2(1 + |r|) : **−1,08 % des bits d'énergie, −0,06 %
  du total**.
- (b) M/S par bande : 21,3 % des bandes changent de représentation (L/R ↔ M/S) d'une trame longue
  à la suivante. Une bande qui bascule coûte plus : résidu d'énergie 3,99 contre 3,11 bits,
  coefficients 1,349 contre 1,270 bit/coef. L'excédent vaut **0,96 % du débit total**, borne
  haute de ce que garder la représentation pourrait rendre, avant de perdre le gain stéréo de la
  bascule. Sous le seuil ; une hystérésis sur la décision M/S (encodeur seul) en récupérerait au
  mieux une partie.
- Le type de bloc relève du détecteur de transitoires (perception), pas du débit : non mesuré.

## Bilan

| Mesure | Gain (débit total) | Décision |
|---|---|---|
| M8 moyenne glissante | −0,16 % | point 27 écarté |
| M2 / M2b contexte inter-trame | vaut 2,0 % ; raffinements < 0,3 % | point 20 improbable |
| M7 contexte des deux côtés | −0,25 % (+4 Kio) | point 23 écarté |
| M7 énergies interpolées | +0,12 % (perte) | point 22 écarté |
| M1 paquets clés à 80 trames | −0,17 % | 40 trames ; point 24 sans objet |
| M3 allocation conjointe | +0,0005 ODG | `rd_viterbi` reste à 0 |
| M6 réglage conjoint | +0,0006 ODG (2 générations) | interrompu |
| M5 coût futur des contextes | −0,01 % | écarté |
| M4 α / M/S | −0,06 % / ≤ 0,96 % | écarté (hystérésis M/S possible, < 1 %) |

Aucune piste n'atteint les seuils (2 % du débit pour le format, +0,01 d'ODG pour l'encodeur).
Le format v2 et son encodeur sont proches de ce que leur architecture permet : les gains restants
demanderaient des outils nouveaux (repliement, ordre hiérarchique abandonné ici, TCQ plus riche :
points 16 et 17), pas des réglages.
