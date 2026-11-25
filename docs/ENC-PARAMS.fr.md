# Les réglages de l'encodeur

*English version: [ENC-PARAMS.md](ENC-PARAMS.md).*

État au 24/11/2026. Ce document recense les champs de `mule_enc_params` (`core/mule_enc.h`), ce que fait
chacun, sa valeur de production (`mule_enc_defaults`, `core/enc.c`) et d'où vient cette valeur.
`py/mule/params.py` (`Params`) reprend les mêmes champs pour Python ; `py/mule/native.py` les recopie
dans la structure C.

**Rien de tout cela n'est dans le format.** Le décodeur ignore ces réglages, sauf trois qui fixent
des drapeaux d'en-tête (`tcq_states`, `tcq_chain`, `coef_a8`, voir *Quantification*). On peut donc
changer tous les autres sans toucher au décodeur ni au firmware.

**Comment lire la colonne « origine ».** Les dates renvoient aux journaux de `eval/results/`
(`N-LOG.md` surtout ; `E-LOG.md`, `E2-LOG.md`, `B-LOG.md`, `M-LOG.md`, `P4-LOG.md`). « Prototype »
veut dire que la valeur vient du premier encodeur Python et n'a jamais été remesurée isolément.
« Sonde » désigne un réglage ajouté pour une expérience, éteint par défaut parce que l'expérience
n'a rien donné ou n'est pas finie.

## Les deux modes de la ligne de commande

`tools/mule-enc` part toujours de `mule_enc_defaults`, puis :

- **`-q dB`** (VBR de qualité pure) : fixe seulement `q_db`. Le débit suit la musique.
- **`--bitrate N`** (défaut 128, comme `opusenc`) : `params.for_bitrate(N)` remplace six valeurs :

  | champ | valeur | défaut de `mule_enc_defaults` |
  |---|---|---|
  | `q_db` | −9,21 × log2(N / 76,4) | −7 |
  | `rc_k` | 2 | 0 (niveleur éteint) |
  | `rc_max` | 15 dB | 9 dB |
  | `opa_mode` | 3 (mélange avec la table d'Opus) | 0 |
  | `opa_alpha` | 0,75 | 0,5 |
  | `band_db` | `params.realloc_db(N)` : réallocation entre bandes (ci-dessous) | 0 partout |

  Adopté le 23/11 (niveleur), le 24/11 (mélange C75) puis le 25/11/2026 (réallocation `brR128`),
  sur la campagne de 300 pistes.

  **La réallocation** (`band_db`, décalages des masques en dB, négatif = plus de bits) vient des
  pentes de notre modèle face à Zimtohrli (`eval/slopes.py`, `eval/results/B9-REPORT.md` §4-10) :

  | bandes MULE (fréquences) | 96 kb/s | 128 kb/s | 160 kb/s |
  |---|---|---|---|
  | 0-1 (graves, < 250 Hz environ) | −3,35 | −3,82 | −3,66 |
  | 2-5 | +1,72 | +3,40 | +0,08 |
  | 6-11 | −0,82 | −0,65 | −1,88 |
  | 12-15 | −0,69 | −0,56 | −1,36 |
  | 16-18 | −1,27 | −0,52 | −1,45 |
  | 19 | −1,81 | −1,24 | −1,77 |
  | 20-21 (13-20 kHz) | +6 | 0 | 0 |

  Entre ces débits, interpolation en log2 du débit (valeurs tenues en dehors) ; l'aigu (bandes
  20-21) vaut +6 dB jusqu'à 96 kb/s et descend linéairement à 0 à 128 kb/s. Sur 299 pistes (c224
  exclue, `eval/campaign.py` EXCLUDE), à débit égal, face à `brC75` : Zimtohrli −9,4 % / −4,7 % /
  −5,6 % à 96 / 128 / 160 kb/s, NMR meilleur partout, PEAQ basique −0,008 / +0,005 / −0,020, PEAQ avancé inchangé dès 128 kb/s ;
  ABX à 96 kb/s (aigu réduit) 46/96, aucune différence entendue. `band_db=()` dans
  `for_bitrate` rend l'ancien `--bitrate` (variante `brC75` de `eval/refcodecs.py`).

Les valeurs « production » ci-dessous sont celles de `mule_enc_defaults`. Pour `--bitrate`,
appliquer le tableau ci-dessus par-dessus.

## Qualité et débit

| champ | rôle | défaut | origine |
|---|---|---|---|
| `q_db` | Cible de bruit relative au seuil de masquage : le réglage de qualité. Plus bas = plus de bits. | −7 | Environ 128 kb/s sur une bibliothèque musicale (`tools/mule_enc.py`). Avec `--bitrate`, calculé depuis la courbe R(q). |
| `rc_k` | Niveleur de débit : chaque trame déplace `q_db` de `rc_k × rc_slope × log2(R / R(q))`, où R est le débit lissé. Ramène chaque piste vers le débit demandé ; l'écart en log est divisé par 1 + `rc_k`. | 0 (éteint) ; 2 avec `--bitrate` | Campagne 300 pistes, 23/11/2026. |
| `rc_tau` | Lissage du débit du niveleur (trames). | 200 (4,6 s) | Choisi à la conception, pas balayé. |
| `rc_max` | Déplacement maximal de `q_db` par le niveleur (dB). | 9 ; 15 avec `--bitrate` | 15 retenu parmi les variantes `rc*m15` de `refcodecs` (23/11/2026). |
| `rc_r0` | Courbe R(q) = `rc_r0` × 2^(−q / `rc_slope`) : débit moyen d'un réglage. | 76,4 kb/s | Ajustement sur la campagne 300 pistes (23/11/2026). |
| `rc_slope` | Pente de cette courbe (dB de `q_db` par doublement du débit). | 9,21 | Même ajustement. |
| `opa_mode` | Table d'allocation par bande d'Opus (CELT `band_allocation`, BSD), au débit `opa_kbps`. 1 : remplace les masques ; 2 : n'en prend que l'inclinaison ; 3 : mélange géométrique avec les masques. | 0 ; 3 avec `--bitrate` | Mode 3 adopté le 24/11/2026 (meilleur sur tous les juges à 96/128/160 kb/s, 300 pistes). |
| `opa_kbps` | Débit pour lequel lire la table. | 0 = R(`q_db`) | — |
| `opa_eta` | Part de la moitié du débit attribuée aux coefficients d'un canal (calibrage de la table). | 0,8 | Choisi à la conception, pas balayé. |
| `opa_k` | Mode 2 : échelle de l'inclinaison. | 1 | Mode 2 non retenu. |
| `opa_alpha` | Mode 3 : part (en log) de nos masques ; le reste vient de la table d'Opus. | 0,5 ; 0,75 avec `--bitrate` | Grille sur *dev*, confirmée sur *test* puis sur les 300 pistes (C75, 24/11/2026). La recherche CMA-ES du 24/11 propose ~0,67 à 96 kb/s (à valider). |

## Trames, blocs courts et groupes

| champ | rôle | défaut | origine |
|---|---|---|---|
| `keyframe` | Trames entre deux paquets clés (multiple de 4). Coût en débit contre temps de recherche dans le fichier. | 40 (0,93 s) | `M-LOG.md` : 80 et 160 trames ne gagnent que 0,17 et 0,26 % de débit. On garde 40. |
| `tr_db` | Détecteur de transitoires : montée d'énergie au-dessus de sa mémoire (dB). | 8,5 | 10 avant le 20/11/2026 (`N-LOG.md`). |
| `tr_decay_db` | Décroissance de la mémoire du détecteur par bloc de 128. | 1 dB | 3 avant le 22/11/2026 : les impulsions glottales d'une voix passaient pour des attaques (`N-LOG.md`). |
| `tr_hf` | Seconde passe du détecteur sur le signal filtré passe-haut. | 1 | 22/11/2026 (`N-LOG.md`). |
| `tr_hf_fc` | Fréquence de coupure de ce passe-haut. | 8000 Hz | Même série. |
| `tr_hf_db` | Seuil de cette passe. | 6 dB | 8,5 avant la v5 (détecteur corrigé, `N-LOG.md`). |
| `tr_hf_ton` | Veto tonal : une trame rendue courte par la seule passe aiguë reste longue si les bandes 12-21 sont plus plates que −`tr_hf_ton` dB. | 10 dB | v5 (cas Belenos, `N-LOG.md`). |
| `groups` | Trames courtes : 0 groupement adaptatif, 8 une énergie par bloc, 1 un seul groupe. | 0 | Prototype ; adaptatif confirmé dans `N-LOG.md`. |
| `group_mode` | Groupement adaptatif : 0 énergie de la fenêtre seule, 1 aussi par région de fréquence. | 1 | 20/11/2026 (`N-LOG.md`). |
| `group_db` | Saut d'énergie qui ouvre un nouveau groupe. | 12 dB | 6 avant `group_mode` 1 (20/11/2026, `N-LOG.md`). |
| `short_db` | Décalage de la cible de bruit dans les trames courtes (< 0 : plus de bits). | 0 | Sonde (Lebanon Hanover, `N-LOG.md`), sans gain. |

## Modèle psychoacoustique (les masques par bande)

| champ | rôle | défaut | origine |
|---|---|---|---|
| `ath_db` | Décalage du seuil d'audition absolu. | 0 | Levier G (`refcodecs` `athm6` … `athp6`), pas de gain. |
| `ath_rel_db` | Seuil d'audition relatif (façon Vorbis/LAME) : abaissé quand le passage est calme, de `ath_rel_db` au plus. | 0 (éteint) | Sonde du 23/11/2026. |
| `ath_ref_db` | Niveau de référence de ce seuil relatif. | −14 dBFS | Un passage fort de musique. |
| `ath_rel_rel` | Descente du suiveur de niveau. | 0,5 dB/trame (22 dB/s) | Choisi à la conception. |
| `tonal_all` | Tous les masqueurs traités comme tonaux. | 0 | Prototype (comparaison seulement). |
| `fft_tonal` | Tonalité estimée par la platitude d'un spectre FFT de Hann (sinon sur la MDCT). | 1 | Axes P4 (`P4-LOG.md`). |
| `fft_noise_db` | Platitude de référence d'un bruit dans ce spectre. | 3,4 | Réglage Zimtohrli, 22/11/2026 (4 avant ; CMA-ES, `N-LOG.md`). |
| `ton_scale` | Platitude (dB sous celle d'un bruit) d'une bande entièrement tonale. | 20 | Prototype. |
| `tcap_db` | Plafond du décalage de masquage tonal 14,5 + z. ≤ 0 : pas de plafond. | 15,3 | Réglage Zimtohrli, 22/11/2026 (25 avant). |
| `low_db` | Décalage de masquage supplémentaire dans les bandes 0-7 (< 1,4 kHz). | 15 | Réglage Zimtohrli, 22/11/2026 (10 avant). |
| `mid_db` | Même chose dans les bandes 8 à `mid_hi` − 1 (1,4 à 8 kHz). | 6,1 | Réglage Zimtohrli, 22/11/2026 (4 avant, `P4-LOG.md`). |
| `mid_hi` | Fin de la zone `mid_db`. | 17 | `P4-LOG.md`. |
| `spread_mode` | Étalement des masques : 0 Schroeder, 1 Terhardt (dépend du niveau), 2 le minimum, 3 Schroeder puis Terhardt au-delà de `sp_dz`. | 3 | 20/11/2026 (`N-LOG.md`) ; 0 avant. |
| `sp_dz` | Mode 3 : Schroeder jusqu'à cette distance au-dessus du masqueur (Bark). | 2 | Même série. |
| `fine_p` | Masques fins des trames longues : sous-bandes de `fine_w` raies, cible de bande = moyenne de puissance d'exposant −`fine_p`. 0 : éteint. | 8 | Axe 1 (`E-LOG.md`, combinaison lf8n12r05, confirmée sur *test*). |
| `fine_w` | Raies par sous-bande. | 1 | Même axe. |
| `fine_nb` | Masques fins sous cette bande seulement. | 12 | Même axe. |
| `pre_db` | Contrôle du pré-écho (rpelev d'AAC) : le masque d'une trame longue ne dépasse pas celui de la précédente de plus de `pre_db`. | 9,7 | Axe 2 (`E2-LOG.md`, 10), puis réglage Zimtohrli du 22/11/2026. |
| `dyn_a` | Façon dynalloc d'Opus : masques abaissés selon l'excès de la bande sur l'enveloppe basse. | 0 (éteint) | Sonde, pas de gain. |
| `bf_rel_db` | Plancher de bande : une bande proche de la plus forte (à `bf_rel_db` près) a un masque au plus `bf_snr_db` sous sa puissance. | 0 (éteint) | Sonde du 23/11/2026 (variantes `bf*` de `refcodecs`), sans gain. |
| `bf_snr_db` | Voir ci-dessus. | 0 | — |
| `hf_db` | Inclinaison des aigus : masques relevés en rampe jusqu'à `hf_db` dans la dernière bande. | 0 (éteint) | Sonde du 24/11/2026, pas de gain. |
| `hf_band` | Première bande de la rampe. | 16 | — |

## Stéréo

| champ | rôle | défaut | origine |
|---|---|---|---|
| `stereo` | 0 automatique (L/R ou M/S par bande, à l'entropie perceptive), 1 L/R, 2 M/S. | 0 | Prototype ; `refcodecs` `lr`, `ms` pour comparer. |

## Allocation (bits par bande)

| champ | rôle | défaut | origine |
|---|---|---|---|
| `alloc_auto` | Référence de codage des allocations : la moins chère entre la bande précédente et la trame précédente (sinon par bande). | 1 | Prototype. |
| `alloc_hyst` | Garde l'allocation de la trame précédente si la nouvelle en diffère d'au plus `alloc_hyst` (moins de bits d'allocation, moins de scintillement). | 1 | Prototype ; voir `N-LOG.md`. |
| `rd_lambda` | Choix débit-distorsion par bande entre a−1, a et a+1 : (bruit/masque) + λ × bits, les bits comptés sur une copie des modèles adaptatifs. 0 : éteint. | 2,42 | Axe 3 (`E-LOG.md`, 2), puis réglage Zimtohrli du 22/11/2026. |
| `zh_db` | Hystérésis marche/arrêt : une bande remplie de bruit à la trame précédente n'est codée que si son énergie dépasse sa cible de `zh_db`. | 0 (éteint) | Sonde du 24/11/2026 (Purcell) : effets de ±1 %, pas retenue. |
| `zh_keep_db` | Une bande codée ne repasse en bruit que si son énergie tombe `zh_keep_db` sous sa cible. | 0 (éteint) | Même sonde. |

## Quantification (TCQ) et codage

Les trois premiers fixent l'en-tête : les changer produit un flux que le décodeur lit, mais ce ne sont
plus les réglages du format v5 de production. Ils servent aux comparaisons.

| champ | rôle | défaut | origine |
|---|---|---|---|
| `tcq_states` | Treillis à 8, 16, 32 ou 64 états (octet 20 de l'en-tête). | 64 | Format v3 (`B-LOG.md`, `C-LOG.md`). |
| `tcq_chain` | L'état du treillis continue d'une bande à l'autre d'un groupe : un seul Viterbi (drapeau `MULE_TCQ_CHAIN`). | 1 | Format v3. |
| `coef_a8` | Alphabet de coefficients à 8 symboles, échappement à 7 (drapeau `MULE_COEF_A8`). | 1 | Format v3. |
| `tcq_rd` | Le Viterbi compte le débit avec les modèles suivis (contextes, échappements, signe). Demande `rd_lambda` > 0. | 1 | Axes 1 et 3 (`E-LOG.md`). |
| `tcq_rdl` | Poids du débit dans ce Viterbi, relatif à celui de l'allocation. | 0,48 | `E-LOG.md` (0,5), puis réglage Zimtohrli du 22/11/2026. |
| `tcq_lam` | Poids du débit dans le Viterbi quand `tcq_rd` = 0 (inutilisé en production). | 0,3 | `M-LOG.md`, `VARIANTS-BC.md`. |
| `tcq_rd_states` | Vitesse : treillis réduit pour les estimations du choix débit-distorsion. 0 : `tcq_states`. | 8 | `B-LOG.md` : encodeur deux fois plus rapide, même qualité. |

### `rd_lambda` et `tcq_rdl` : deux arbitrages débit-distorsion

L'encodeur décide en deux étapes, et chacune pèse les bits contre le bruit :

1. **L'allocation**, bande par bande : la finesse `a` de chaque bande. Le choix entre a−1, a et a+1
   minimise `bruit / masque + rd_lambda × bits`.
2. **La quantification en treillis (TCQ)**, coefficient par coefficient : le Viterbi cherche la
   suite de niveaux qui minimise `distorsion + λ × bits`, les bits comptés avec les modèles
   adaptatifs du codeur entropique (`tcq_rd` = 1).

`tcq_rdl` fixe le λ du Viterbi relativement à celui de l'allocation (`core/enc_tcq.c`) :

    λ = tcq_rdl × rd_lambda × (cible de bruit de la bande) / (pas de quantification)²

Les bits y sont donc pesés dans les mêmes unités, le bruit rapporté au masque, que dans l'allocation.

- **`tcq_rdl` faible** (vers 0) : le Viterbi privilégie la précision et prend les niveaux les plus
  proches du signal, même coûteux.
- **`tcq_rdl` élevé** : il accepte un peu plus d'erreur pour économiser des bits. Il préfère les
  petits niveaux et les zéros, moins chers, et les zéros sont ensuite remplis de bruit
  (`nf_off_db`).

À débit égal, les bits économisés dans le Viterbi reviennent à l'allocation, qui peut coder plus de
bandes ou plus finement. La recherche CMA-ES du 24/11 (mode `--bitrate`) monte `tcq_rdl` de 0,48 à
0,60-0,66 à 96 et 128 kb/s, avec un bruit de remplissage plus fort : plus de bandes couvertes, avec
des coefficients un peu plus grossiers. À valider.

## Bandes vides et bruit de remplissage

| champ | rôle | défaut | origine |
|---|---|---|---|
| `nf_off_db` | Niveau du bruit qui remplace les coefficients nuls d'une bande codée : niveau mesuré plus ce décalage. | −6 dB | v4 (`N-LOG.md`). La recherche CMA-ES du 24/11 propose ~−4,3 à 96 kb/s (à valider). |
| `nf_bias` | Énergie des bandes remplies de bruit envoyée `nf_bias` pas de 1,5 dB plus bas. | 1 | 21/11/2026 : Zimtohrli meilleur, ViSQOL moins bon, adopté par l'auteur (`N-LOG.md` ; premier essai `E2-LOG.md`). |
| `nf_top` | À partir de cette bande, une bande à allocation 0 est envoyée silencieuse au lieu d'être remplie. | `MULE_NB` (22 : jamais) | Sonde (`code*`, `N-LOG.md`). |
| `tg` | Bandes tonales à zéro bit : 1 garde (la bande reçoit `tg_a` si sa raie la plus forte est à moins de `tg_db` de la cible), 2 silence, 0 éteint. | 1 | Format v4 (`N-LOG.md`). |
| `tg_db` | Garde : marge de la raie la plus forte sous la cible. | 6 dB | `N-LOG.md` (balayage `tg1d0` … `tg1d18`). |
| `tg_a` | Garde : allocation donnée. | 1 | `N-LOG.md`. |
| `tg_band` | Garde : à partir de cette bande seulement. | 0 | `N-LOG.md` (`tg1b19`, `tg1b20` sans gain). |
| `tg_ton` | Une raie isolée : la plus forte de la bande dépasse de tant de dB celle d'un bruit de même nombre de raies (2 ln n × moyenne). | 5 dB | `N-LOG.md`. |
| `eg` | Garde d'enveloppe (Garbage) : dans une trame longue, une bande à allocation 0 à partir de `eg_band` est codée à `eg_a` si son énergie sur les 8 blocs courts monte de `eg_db` au-dessus de sa moyenne. Le bruit de remplissage est stationnaire sur la fenêtre. | 1 | 21/11/2026 (`N-LOG.md`). |
| `eg_band` | Voir ci-dessus. | 16 | Même série (`eg6b12`, `eg6b19`). |
| `eg_db` | Voir ci-dessus. | 5 dB | 6 d'abord ; 5 adopté avec `nf_bias` 1 (`N-LOG.md`, Zimtohrli). |
| `eg_a` | Voir ci-dessus. | 1 | Même série (`eg6a2` sans gain). |

## Les réglages réellement réglés

La plupart des valeurs ci-dessus ont été fixées une fois, sur une mesure, et n'ont plus bougé. Huit
d'entre elles ont été réglées ensemble par CMA-ES contre Zimtohrli le 22/11/2026 (`low_db`, `mid_db`,
`tcap_db`, `fft_noise_db`, `rd_lambda`, `tcq_rdl`, `pre_db`, puis `eg_db` avec `nf_bias`). Une
nouvelle recherche, en mode `--bitrate` à 96, 128 et 160 kb/s, est en cours le 24/11/2026
(`eval/m6_tune.py --space b9`). Elle porte sur les sept réglages psychoacoustiques plus
`opa_alpha` et `nf_off_db`.

Valeurs choisies sans mesure dédiée, candidates si l'on cherche encore : `ton_scale`, `opa_eta`,
`rc_tau`, `alloc_auto`, `ath_rel_rel`.

## Ajouter un réglage

1. Le champ et sa documentation dans `core/mule_enc.h`, au bout de la structure. La liaison cffi
   relit la structure dans ce fichier : il n'y a pas de seconde définition à tenir à jour.
2. La valeur de production dans `mule_enc_defaults` (`core/enc.c`), et sa validation dans
   `params_ok` si elle a un domaine.
3. Le champ dans `Params` (`py/mule/params.py`) et sa recopie dans `py/mule/native.py`.
4. Les variantes de mesure dans `VARIANTS` (`eval/refcodecs.py`).
5. Une ligne dans ce document et dans sa version anglaise.
