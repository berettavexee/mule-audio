# Où chaque codec place son bruit (20/11/2026)

`eval/noise_placement.py` sur les 30 extraits de `test`, codecs vers 128 kb/s (débits réels :
MULE q −7 129,7 kb/s, Opus 130,6, Vorbis q4 123,1, FDK-AAC 126,2). Juge commun : le modèle de
masque interne de l'évaluation (`eval/metrics.py`, demi-bandes de Bark), bande par bande : rapport
bruit/masque (NMR) moyen, part des trames où le bruit dépasse le masque, rapport bruit/signal.

**Réserve majeure** : ce juge reprend les constantes du modèle psychoacoustique de l'encodeur de
MULE (étalement de Schroeder, décalage 14,5 + z dB pour le tonal, 5,5 dB pour le bruit). MULE a été
réglé pour lui ressembler : il est avantagé par construction. Les écarts entre les autres codecs,
et la forme de leurs choix, sont plus instructifs que le classement de MULE.

| Région | MULE | Opus | Vorbis | FDK-AAC |
|---|---|---|---|---|
| 0-500 Hz | −17,2 dB / 0 % | −16,3 / 0 % | −18,5 / 0 % | **−25,1** / 0 % |
| 500-2000 Hz | −10,9 / 1,7 % | −9,3 / 1,4 % | −8,6 / 6,6 % | −13,2 / 0,6 % |
| 2-6 kHz | −2,5 / 19 % | −1,1 / 32 % | +0,5 / 43 % | −2,0 / 27 % |
| 6-12 kHz | −1,1 / 52 % | +0,2 / 58 % | +3,1 / 70 % | +2,3 / 64 % |
| 12-16 kHz | −25,5 / 4 % | −25,0 / 9 % | −25,6 / 11 % | −24,2 / 12 % |

(NMR moyen / part des trames au-dessus du masque ; au-dessus de 16 kHz, le juge tient tout pour
inaudible : seuil absolu très haut.)

## Lecture

- **FDK-AAC investit massivement dans les graves** : 7 à 9 dB de bruit en moins que les autres
  sous 500 Hz, encore 2 à 4 dB de moins entre 500 Hz et 2 kHz, payés par plus de bruit entre 6 et
  12 kHz et par sa coupure à 16 kHz. C'est un choix de modèle, prudent dans les graves.
- **Opus et MULE ont presque le même profil dans les graves** ; Opus laisse un peu plus de bruit
  partout au-dessus de 2 kHz (1 à 1,5 dB).
- **Vorbis** laisse nettement plus de bruit entre 1 et 12 kHz.
- **MULE** dépasse le moins souvent le masque du juge dans les médiums et les aigus, comme
  attendu d'un encodeur réglé sur un modèle voisin.

## Ce que ça dit pour MULE

- La stratégie de FDK (plus de marge dans les graves) a déjà été mesurée dans MULE : `low_db` 12
  au lieu de 10 (levier F, `E2-LOG.md`) n'a rien rapporté en PEAQ, et `low_db` 8 non plus. Rien de
  neuf à essayer de ce côté, sauf à l'oreille.
- Aucune région où MULE laisserait nettement plus de bruit que les autres : pas de piste
  d'allocation évidente.
- Pour un juge vraiment indépendant, il faudrait les variables de PEAQ par bande, ou un autre
  modèle d'audition (Zimtohrli), ce que l'outil ne fait pas encore.

## Avec l'encodeur AAC d'Apple (qaac TVBR 63, 123,8 kb/s)

| Région | MULE | Opus | Vorbis | FDK-AAC | Apple AAC |
|---|---|---|---|---|---|
| 0-500 Hz | −17,2 / 0 % | −16,3 / 0 % | −18,5 / 0 % | −25,1 / 0 % | −20,1 / 0 % |
| 500-2000 Hz | −10,9 / 1,7 % | −9,3 / 1,4 % | −8,6 / 6,6 % | −13,2 / 0,6 % | −10,4 / 1,4 % |
| 2-6 kHz | −2,5 / 19 % | −1,1 / 32 % | +0,5 / 43 % | −2,0 / 27 % | −0,3 / 39 % |
| 6-12 kHz | −1,1 / 52 % | +0,2 / 58 % | +3,1 / 70 % | +2,3 / 64 % | +1,7 / 68 % |
| 12-16 kHz | −25,5 / 4 % | −25,0 / 9 % | −25,6 / 11 % | −24,2 / 12 % | −25,2 / 11 % |

Apple se place entre FDK et Opus dans les graves (−20 dB sous 500 Hz, 5 dB de moins de soin que
FDK), et laisse **plus** de bruit que FDK entre 2 et 6 kHz (39 % des trames au-dessus du masque
contre 27 %), autant entre 6 et 12 kHz. Pour ce juge, Apple n'est donc pas meilleur que FDK ; pour
PEAQ, il l'est nettement (+0,23 d'ODG à 128 kb/s). Son avance ne tient pas à la répartition
moyenne du bruit entre les fréquences : elle est ailleurs (dans le temps : blocs courts,
pré-écho, TNS ; dans la bande passante, qui monte avec le débit et que PEAQ mesure ; dans la
stéréo), là où une moyenne par bande ne regarde pas. Piste suivante : les variables de PEAQ
(MOV) d'Apple et de FDK, extrait par extrait, pour voir laquelle porte l'écart.

## Les variables internes de PEAQ (MOV), Apple contre FDK

`eval/mov_compare.py aac_128,aapl_q63,mule_-7,opus_128 --set test`. Pour chaque extrait, on fait
la différence de chaque variable avec FDK. Pour chaque variable, on donne la moyenne de ces
différences, un score t (moyenne / écart-type × √30) et la corrélation r de la différence avec
celle de l'ODG. Débits réels : FDK 126,2 kb/s, Apple 123,8 kb/s.

| MOV | FDK | Apple | MULE | Opus | Apple − FDK : t / r |
|---|---|---|---|---|---|
| ODG | −0,565 | −0,364 | −0,156 | −0,105 | +4,1 |
| BandwidthTestB | 708 | 757 | 855 | 894 | +15,6 / +0,04 |
| Total NMRB (dB) | −11,9 | −13,0 | −14,5 | −13,9 | −4,4 / **−0,90** |
| ADBB | 0,85 | 0,37 | 0,13 | −0,29 | −8,8 / −0,79 |
| RelDistFramesB | **0,101** | 0,001 | 0,027 | 0,015 | −4,5 / −0,42 |
| AvgModDiff1B | 9,19 | 9,97 | 9,13 | 8,93 | +3,2 / −0,83 |
| EHSB | 0,30 | 0,28 | 0,20 | 0,20 | −0,6 / −0,84 |
| débit (kb/s) | 126,2 | 123,8 | 129,7 | 130,6 | −0,9 / **+0,91** |

### Lecture

1. **Le débit suit la difficulté (r = +0,91).** Apple a le même débit moyen que FDK, mais en VBR
   (TVBR). Les extraits où il dépense plus que FDK sont exactement ceux où il le bat le plus.
   FDK, en CBR à 128 kb/s, donne autant de bits à un extrait facile qu'à un extrait difficile.
   Une bonne part de l'avance vient de la **répartition des bits entre les extraits**, pas de
   l'encodeur trame par trame.
2. **Apple n'a presque aucune trame fortement dégradée.** RelDistFramesB compte la part des
   trames où le bruit dépasse le masque de 1,5 dB dans au moins une bande. Elle passe de 10 %
   chez FDK à 0,1 % chez Apple (MULE 2,7 %, Opus 1,5 %). ADBB, qui mesure la distorsion des blocs
   audibles, va dans le même sens. Apple supprime les pics de distorsion, là où FDK laisse
   passer des trames ratées. C'est la signature d'un contrôle du pire cas : réservoir de bits
   bien utilisé, ou boucle de distorsion qui borne le NMR maximal plutôt que sa moyenne.
3. **Pour le modèle d'oreille de PEAQ, Apple place mieux son bruit (−1,1 dB de NMR, r = −0,90).**
   C'est l'inverse du verdict de notre juge interne (section précédente). Les deux juges ne
   s'accordent donc pas sur ce qui est masqué. Apple semble réglé sur un modèle de masquage plus
   proche de celui de PEAQ que de celui que MULE partage avec notre juge. Cela confirme la
   réserve de départ : le juge interne n'est pas indépendant.
4. **La bande passante est plus large de 49 unités chez Apple (t = 15,6).** L'écart est
   systématique mais ne suit pas l'ODG extrait par extrait (r = 0,04). La corrélation ne permet
   pas de dire si ce décalage constant pèse dans la moyenne.
5. **Apple est un peu moins bon sur l'enveloppe temporelle** (AvgModDiff, WinModDiff +0,7 à +0,8).
   La piste « blocs courts, TNS, pré-écho » ne l'explique donc pas, du moins pour PEAQ.

### Pistes pour MULE

- MULE est déjà en VBR à qualité constante : le point 1 est acquis.
- Le point 2 est à vérifier : MULE a 2,7 % de trames fortement dégradées, Opus 1,5 %, Apple 0,1 %.
  Repérer ces trames dans la trace (les bandes où le NMR dépasse +1,5 dB) dirait si un plafond de
  NMR par bande dans l'allocation vaut quelque chose.
- Pour séparer le VBR du reste de la recette, il faut un FDK en VBR (`aacv_*`) au même débit
  qu'Apple, puis la même comparaison.

## Même comparaison, FDK en VBR

FDK n'a que cinq modes VBR. Paire la plus proche : `aacv_4` (137,1 kb/s) contre `aapl_q73`
(140,9 kb/s). La pente d'Apple entre q63 et q73 (+0,20 d'ODG pour 17 kb/s) vaut environ 0,045
d'ODG pour les 3,8 kb/s d'écart.

| MOV | FDK VBR | Apple | Apple − FDK : t / r |
|---|---|---|---|
| ODG | −0,466 | −0,161 | +6,2 (écart +0,31, environ +0,26 à débit égal) |
| BandwidthTestB | 734 | 765 | +7,6 / −0,14 |
| Total NMRB (dB) | −12,7 | −14,4 | −7,9 / −0,84 |
| ADBB | 0,64 | −0,07 | −9,2 / −0,78 |
| RelDistFramesB | 0,032 | 0,000 | −3,8 / −0,74 |
| AvgModDiff2B | 20,9 | 18,2 | −3,4 / −0,80 |
| EHSB | 0,335 | 0,245 | −2,8 / −0,74 |
| débit (kb/s) | 137,1 | 140,9 | +1,6 / **+0,84** |

### Lecture

- **Le VBR ne suffit pas à expliquer l'avance d'Apple.** L'écart reste d'environ +0,26 d'ODG à
  débit égal, plus que contre FDK CBR à 128 kb/s (+0,20).
- **Ce qui compte, c'est la façon de répartir les bits, pas le simple fait d'être en VBR.** Les
  deux encodeurs sont en VBR, et l'écart de débit extrait par extrait suit encore l'écart d'ODG
  (r = +0,84). Sur les extraits où Apple dépense plus que FDK, il gagne. Son estimation de ce
  dont chaque extrait a besoin (entropie perceptive) semble meilleure.
- **Les trames ratées tiennent pour une bonne part au CBR.** FDK VBR passe de 10 % à 3,2 % de
  trames au-dessus du masque de 1,5 dB. Apple reste à 0.
- **Le NMR de PEAQ est l'écart le plus net** : −1,7 dB, t = −7,9. Avec un modèle de masquage
  proche de celui de PEAQ, Apple met son bruit là où il est masqué.
- **Apple bat aussi FDK sur l'enveloppe temporelle** (AvgModDiff2B −2,7, EHS −0,09). À
  128 kb/s, il était légèrement moins bon que FDK CBR sur ce point. L'enveloppe ne fait donc pas
  partie de son avance stable.

### Bilan provisoire de la « recette d'Apple » vue par PEAQ

Les trois points se renforcent :

1. un modèle de masquage qui place le bruit sous le seuil de PEAQ (−1,1 à −1,7 dB de NMR) ;
2. une répartition des bits entre passages difficiles et faciles qui suit mieux la difficulté
   réelle ;
3. aucune trame laissée nettement au-dessus du masque.

Pour MULE, le point 3 est le plus concret : 2,7 % de trames dégradées. Ensuite le point 1 :
comparer le seuil du modèle psychoacoustique de MULE à celui de PEAQ bande par bande.

## Piste 1 : les trames dégradées de MULE

Le script `eval/bad_frames.py` compte les trames où le pire bruit de bande dépasse de plus de 1,5 dB
le masque de PEAQ. Il s'appuie sur un patch local de GstPEAQ (`PEAQ_FRAMES=1`, dans `src/movs.c`)
qui écrit, pour chaque trame, la pire bande et sa fréquence. Codecs vers 128 kb/s, sur `test` :

| | MULE | Opus | Apple | FDK CBR |
|---|---|---|---|---|
| trames dégradées | 2,75 % | 1,52 % | 0,13 % | 10,1 % |
| dépassement médian / 90e centile | +2,9 / +6,1 dB | +3,8 / +8,0 | +2,1 / +3,9 | +2,7 / +6,4 |
| part de ces trames au-dessus de 12 kHz | 90 % | 99 % | 32 % | 75 % |

- **Deux extraits portent 62 % des trames dégradées de MULE** : Zombie Zombie (26,7 % de ses
  trames) et Takemitsu (24,5 %). Opus et Apple sont à moins de 1 % sur ces deux extraits. Sans
  eux, MULE tombe à 1,1 %.
- **Takemitsu, une raie isolée à 15,08 kHz dans une pièce calme.** La bande 20 de MULE
  (13,4–17,2 kHz, 176 raies) reçoit 0 bit dans 100 % des trames : pour l'encodeur, sa puissance
  est 18 dB sous le masque, qui est ici le seuil absolu. Au décodage, la raie ressort 13 dB trop
  bas (−38,6 au lieu de −25 dB) et un bruit plat la remplace sur toute la bande. Il dépasse
  l'original de 6,6 dB entre 13,5 et 14,1 kHz, là où il n'y avait presque rien. C'est ce bruit
  que PEAQ voit (pire bande à 13,8 kHz). Opus garde la raie (−25,0 dB).
- **Zombie Zombie, même mécanisme, moins marqué.** Une raie à 14,98 kHz sur le canal droit
  perd 5 dB. La bande 20 est à 0 bit dans 56 % des trames.
- **Ce n'est pas un problème de niveau du seuil absolu.** Le levier G (`E2-LOG.md`) a déjà
  décalé ce seuil globalement, sans gain. Le défaut est ailleurs : remplacer par du bruit plat
  le contenu *tonal* d'une bande large à 0 bit en détruit la forme. L'énergie est conservée,
  mais une raie devient un souffle de 3,8 kHz de large.

### Proposition (rien n'est encore codé)

Une **garde tonale des bandes à 0 bit**, du côté de l'encodeur seulement : le format v3 et le
décodeur ne changent pas.

- **Déclencheur.** L'allocation donne 0 bit à une bande, la bande est tonale (la planéité
  spectrale `flat[]` est déjà calculée pour le masque), et sa raie la plus forte est proche du
  seuil, à moins de X dB.
- **Action.** On donne à la bande l'allocation minimale non nulle, pour que la raie soit codée
  et que la bande ne soit plus remplie de bruit. Le seuil se compare à la raie, pas à la
  moyenne de la bande, qui dilue une raie seule par 176.
- **Mesure.** Sur `test`, à débit égal, contre la production : ODG, ODG avancé, ViSQOL, part
  des trames dégradées, et les régressions extrait par extrait. Variantes : X = 6, 12, 18 dB.
- **Risque.** Des bits dépensés dans les aigus de passages calmes, au détriment du reste. Il
  faudra aussi écouter Takemitsu : à 15 kHz, une raie n'est pas audible pour tout le monde,
  même si PEAQ la compte.

### Ce que font les autres codecs

- **Opus (CELT).** Aucune bande n'est jugée inaudible : l'énergie est toujours transmise et, à
  128 kb/s, toutes les bandes reçoivent des impulsions PVQ. Pour une raie seule, une impulsion
  suffit (environ log₂(2 × 176) ≈ 8,5 bits pour 176 raies), et le niveau est exact, puisque
  l'énergie est codée à part. Une bande sans impulsion est remplie par recopie d'une bande plus
  basse (*folding*), pas par un bruit plat.
- **AAC.** Les bandes de facteur d'échelle sont bien plus étroites en haut du spectre. En AAC-LC,
  une bande sans bits est muette. La substitution de bruit (PNS) et le remplissage de bruit de
  l'USAC ne visent que les bandes reconnues comme du bruit : FDK vérifie la tonalité avant
  d'activer la PNS.
- **HE-AAC (SBR).** Le drapeau `add_harmonic` insère une sinusoïde là où une raie forte manque à
  la reconstruction des aigus. C'est le cas le plus proche de celui de MULE.
- **MP3.** La dernière bande (sfb21) n'a pas de facteur d'échelle. LAME s'en sort surtout avec un
  passe-bas.

### Deux variantes codées (encodeur seul, format v3 inchangé)

1. **Garde tonale, à la manière d'Opus** (`tg_db`) : une bande à 0 bit, tonale, dont la raie la
   plus forte arrive à moins de `tg_db` dB du masque, reçoit l'allocation minimale non nulle.
2. **Bande tonale muette, à la manière de la PNS** (`tg_mute`) : une bande tonale à 0 bit n'est
   pas remplie de bruit, elle est envoyée muette. Elle sert de témoin : elle dira si le gain de
   la variante 1 vient de la raie retrouvée ou du bruit supprimé.

### Mise au point (20/11/2026)

- **La planéité ne détecte pas ces raies.** Dans la bande 20 de Takemitsu, la planéité FFT des
  masques reste à −3,7 dB en médiane, un niveau de bruit : la raie n'est là que par moments, et
  la planéité est mesurée sur toute la bande. Le critère retenu est donc **le facteur de crête**,
  pris sur les coefficients codés. La raie la plus forte doit dépasser de `tg_ton` dB (5 par
  défaut) le maximum attendu d'un bruit sur les mêmes n raies, soit 2 ln n fois la puissance
  moyenne. Seules les bandes d'au moins 16 raies sont concernées. Dans la bande 20, à 0 bit, la
  crête dépasse 15 dB dans 22 % des trames de Takemitsu (PEAQ en compte 24,5 % de dégradées) et
  dans 90 % de celles de Zombie Zombie, contre 1 à 4 % sur Eminem et Judas Priest.
- **La production reste identique au bit près** (`tg` = 0) : même empreinte md5 que la version
  commitée, sur 3 extraits et 2 qualités. La trace des bandes ajoute deux champs, `flat_cdb` et
  `peak_mdb`.
- **Premier essai, sur les deux extraits fautifs, à q −7 :**

| | trames dégradées | ODG | débit |
|---|---|---|---|
| production | 25,6 % | −0,279 | 106,96 kb/s |
| garde tonale (`tg` 1) | **7,2 %** | **−0,253** | 107,29 (+0,3 %) |
| bande tonale muette (`tg` 2) | 23,6 % | −0,282 | 107,56 (+0,6 %) |

  Le gain vient de la raie retrouvée, pas du bruit supprimé : la variante muette ne fait rien et
  coûte plus, car ses énergies à −100 font des sauts de prédiction. `tg_db` n'a pas d'effet
  (6 et 18 dB donnent le même résultat), puisque le critère de crête suffit à décider.

### Comment Apple et FDK rendent ces raies

Spectre moyen (FFT de 8192 points) autour de la raie, sur le canal fautif, à 128 kb/s environ.
L'erreur est la médiane, sur les trames où la raie est présente, de l'écart de niveau avec
l'original.

| Takemitsu, 15,09 kHz | raie | bruit 13,5–14,1 kHz | 16–20 kHz | erreur sur la raie | kb/s |
|---|---|---|---|---|---|
| original | −20,2 | −45,4 | −33,6 | – | |
| MULE | −30,3 | −38,8 | −33,8 | 9,5 dB | 104,5 |
| MULE `tg` 1 | −23,3 | −42,8 | −33,9 | 2,7 dB | 104,7 |
| Opus | −20,1 | −45,7 | −33,1 | 0,3 dB | 125,0 |
| Apple | −20,3 | −45,9 | **−43,3** | 0,5 dB | 121,8 |
| FDK | −20,6 | −45,3 | −66,2 | 0,6 dB | 126,2 |

Sur Zombie Zombie (raie à 14,98 kHz, −7,1 dB) :

| | erreur sur la raie | kb/s |
|---|---|---|
| MULE | 3,1 dB | 109,4 |
| MULE `tg` 1 | 1,7 dB | 109,8 |
| Opus | 0,9 dB | 146,4 |
| Apple | 0,8 dB | 94,5 |
| FDK | 0,4 dB | 126,2 |

- **Les deux AAC gardent la raie sans garde-fou**, grâce à leurs bandes étroites : la raie domine
  sa bande, le pas se cale sur elle, et les bandes voisines, vides, ne reçoivent rien.
- **Apple sacrifie le haut du spectre plutôt que la raie** : −10 dB sur 16–20 kHz pour Takemitsu,
  la raie intacte. FDK coupe tout au-dessus de 16 kHz.
- **La garde tonale à l'allocation 1 corrige à moitié** : la raie reste 3 dB trop basse et le
  bruit voisin 2,6 dB trop haut. Variantes suivantes : `tg_a`, l'allocation donnée par la garde
  (2, 3, 4). Idée de format, des bandes plus étroites au-dessus de 13 kHz : dans
  `docs/V4-IDEAS.md`.

### Mesure sur `test` à débit égal (`tg_test.csv`)

Production, garde tonale (`tg` 1) et bande muette (`tg` 2), chacune à q −6, −9 et −12,
interpolées à 128 et 160 kb/s :

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | débit à q égal |
|---|---|---|---|---|---|---|
| production | −0,1725 | −0,0144 | −0,3546 | −0,1402 | 4,6082 | |
| `tg` 1 | **−0,1688** | **−0,0129** | **−0,3520** | **−0,1389** | **4,6129** | +0,04 % |
| `tg` 2 | −0,1745 | −0,0134 | −0,3545 | −0,1401 | 4,5933 | +0,15 % |

À q −6, `tg` 1 ne fait régresser aucun extrait de plus de 0,02 d'ODG. Les gains se concentrent sur
Lebanon Hanover (+0,064), Takemitsu (+0,039) et Zombie Zombie (+0,029). Le gain moyen
(+0,004) reste sous le seuil d'adoption du projet (+0,01). Le défaut est localisé : la garde le
corrige à moitié là où il se trouve, sans rien coûter ailleurs. `tg` 2 est rejetée.

**`tg_a`** (l'allocation donnée par la garde), sur les deux extraits fautifs à q −7 : ODG de
−0,253 (a = 1) à −0,248 (a = 4), trames dégradées de 7,2 % à 6,5 %. Presque sans effet. Les 7 %
de trames qui restent sont surtout des trames où la garde ne se déclenche pas, pas des raies mal
codées.

## Les écarts extrait par extrait, à 128 kb/s

L'ODG de chaque extrait est interpolée entre les deux configurations qui encadrent 128 kb/s de
débit moyen (`ref_test.csv`, `aapl_test.csv`, `tg_test.csv`). Moyennes : MULE −0,173,
Opus −0,116, Apple −0,314.

- **L'écart avec Opus (−0,056) est très concentré.** Lebanon Hanover en porte environ un quart à
  lui seul (−0,458 contre Opus). C'est aussi l'extrait où le rapport bruit/masque de MULE est le
  pire, à toutes les qualités. Viennent ensuite Zombie Zombie (−0,216), Max Richter (−0,168),
  Spector (−0,129), Salut c'est cool (−0,125), Mravinsky (−0,122) et Takemitsu (−0,118).
- **MULE est derrière Opus de plus de 0,02 sur 19 extraits, devant sur 5**, dont Belenos (+0,37)
  et Holst (+0,085).
- **Un motif : MULE dépense beaucoup moins qu'Opus sur les morceaux calmes ou clairsemés.**
  Zombie Zombie 108 kb/s contre 144, Takemitsu 103 contre 123, Max Richter 116 contre 140,
  Mravinsky 119 contre 140. Le débit variable de MULE, qui vise le même rapport bruit/masque
  partout, juge ces extraits faciles. PEAQ n'est pas d'accord. Le masque de MULE y est
  probablement trop indulgent : seuil absolu, ou masquage surestimé quand le signal est faible.

## Passage par passage (`eval/segment_odg.py`, fenêtres de 3 s, q −7 / Opus 128 / Apple q63)

ODG de MULE moins celle d'Opus, fenêtre par fenêtre (les extraits durent 15 s) :

| extrait | 0-3 s | 3-6 | 6-9 | 9-12 | 12-15 |
|---|---|---|---|---|---|
| Lebanon Hanover | **−0,67** | −0,46 | −0,36 | −0,55 | −0,14 |
| Zombie Zombie | **−0,48** | −0,06 | −0,13 | −0,07 | **−0,39** |
| Max Richter | −0,10 | −0,19 | −0,19 | −0,12 | −0,14 |
| Spector | −0,23 | −0,12 | −0,13 | −0,07 | −0,17 |
| Salut c'est cool | −0,13 | −0,15 | −0,18 | −0,10 | −0,10 |
| Mravinsky | −0,14 | −0,14 | −0,13 | −0,11 | −0,02 |
| Takemitsu | −0,18 | −0,13 | −0,07 | −0,04 | +0,01 |

- **Deux types de défaut.** Sur Zombie Zombie, le défaut est localisé : deux passages, le début et la
  fin. Partout ailleurs, il est **diffus** : un retard régulier de 0,1 à 0,2 sur tout l'extrait.
  Lebanon Hanover est un cas à part, mauvais partout (−0,36 à −0,67).
- **Lebanon Hanover.** Même à q −9 (156 kb/s), MULE reste à −0,42, contre −0,11 pour Opus à
  130 kb/s. La variable qui s'écarte est la sonie du bruit, `RmsNoiseLoudB` : 0,92 contre 0,15.
  Viennent ensuite le NMR (−9,3 contre −12,7 dB) et ADBB (0,87 contre −0,18).
  - Le spectre moyen du bruit ne l'explique pas : MULE n'en laisse plus qu'entre 7 et 11 kHz
    (+3 à +4 dB par rapport à Opus), et il est équivalent ou meilleur ailleurs, stéréo comprise.
  - L'extrait compte 17 % de trames en blocs courts, mais seulement 4 attaques franches (+10 dB),
    et le pré-écho y est à peine plus fort que chez Opus (−17,8 contre −19,2 dB). La cause n'est
    donc ni le spectre moyen ni les attaques. Restent la modulation temporelle du bruit à
    l'intérieur des trames longues, ou la fenêtre 0-3 s à écouter.
- **Zombie Zombie.** Le pré-écho est 4 dB plus fort que chez Opus avant les attaques
  (−18,7 contre −22,7 dB, 14 attaques), en plus de la raie à 15 kHz. Ses deux mauvais passages
  sont à vérifier sur ces deux causes.

## Lebanon Hanover : les blocs courts sont sous-dotés

Extraits d'écoute de la fenêtre 0-3 s (original, MULE q −7, Opus 128) : fichiers locaux, non
publiés (musique sous droits).

**Les trames proches d'un bloc court portent le défaut.** On croise l'NMR que PEAQ donne trame par
trame avec le type de bloc que MULE a choisi. Une trame de PEAQ (21,3 ms) est dite « près d'un
bloc court » si la trame MULE correspondante, ou l'une de ses voisines, est courte.

| Lebanon Hanover | part des trames | NMR moyen en puissance, MULE | Opus |
|---|---|---|---|
| près d'un bloc court | 37 % | −8,1 dB | −14,6 dB |
| blocs longs seulement | 63 % | −9,0 dB | −11,6 dB |

MULE est en blocs courts dans 17 % des trames. En médiane, son NMR par trame est meilleur que
celui d'Opus (−14,5 contre −12,5 dB). Mais dans 10 % des trames, il est plus de 5 dB au-dessus.
PEAQ fait sa moyenne en puissance : ces trames l'emportent.

**Le bruit à l'intérieur des trames, 5-12 kHz, par blocs de 2,9 ms.** Le bruit de MULE est plus
faible en moyenne (−13,0 contre −10,3 dB), mais plus fort dans les instants calmes : dans les
blocs à plus de 10 dB sous le maximum de leur fenêtre de 23 ms, −9,1 contre −14,7 dB. Il s'étale
sur la fenêtre de 46 ms au lieu de suivre l'enveloppe du signal.

**Diagnostic, à q −7.** `tr_db` est le seuil du détecteur d'attaques : moins de blocs courts.
`short_db` est la cible de bruit des blocs courts : plus de bits pour eux. Les deux paramètres
ont été remis dans l'encodeur, à leurs valeurs de production par défaut.

| | Lebanon ODG | kb/s | RmsNoiseLoudB | Zombie | Eminem | Airbourne |
|---|---|---|---|---|---|---|
| production | −0,545 | 136,0 | 0,924 | −0,317 | −0,108 | −0,065 |
| `tr_db` 13 à 99 | −0,544 à −0,547 | +2 % | 0,92 | inchangé | −0,005 à −0,011 | inchangé |
| `short_db` −3 | −0,393 | 140,6 | 0,667 | −0,312 | −0,095 | −0,063 |
| `short_db` −6 | **−0,279** | 145,7 | 0,485 | −0,305 | −0,091 | −0,065 |
| Opus 128 | −0,107 | 130,3 | 0,148 | −0,107 | −0,043 | −0,099 |

- **Le nombre de blocs courts n'y est pour rien.** Monter le seuil change à peine le débit et pas
  du tout la note. Le second critère du détecteur, une hausse de 20 dB sur 7 à 10 blocs, reste
  actif.
- **La dotation des blocs courts est en cause.** `short_db` −6 fait gagner +0,27 d'ODG à Lebanon
  Hanover pour 7 % de débit. Passer de q −7 à q −9 (+15 % de débit) ne faisait gagner que +0,12.
  La sonie du bruit est divisée par deux.
- Le levier H (`E2-LOG.md`) avait essayé `short_db` −3 sur `dev`, en moyenne : +0,004, dont
  « l'essentiel tient à un seul extrait (Lebanon Hanover +0,08) ». Le signal était là. La moyenne
  l'a noyé.
- Mesure à débit égal en cours sur `test` : `short_db` −3, −6 et −9 (`sh_test.csv`).

### `short_db` sur `test`, à débit égal (`sh_test.csv`)

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | Lebanon @128 | régressions |
|---|---|---|---|---|---|---|---|
| production | −0,1725 | −0,0144 | −0,3546 | −0,1402 | 4,6082 | | |
| −3 dB | −0,1672 | −0,0067 | −0,3538 | −0,1421 | 4,6077 | +0,156 | 0 |
| −6 dB | −0,1662 | −0,0036 | −0,3562 | −0,1441 | 4,6073 | +0,262 | 0 |
| −9 dB | −0,1673 | −0,0046 | −0,3609 | −0,1473 | 4,6067 | +0,338 | 1 (Belenos −0,021) |

L'ODG gagne +0,005 à +0,011, presque uniquement grâce à Lebanon Hanover ; l'ODG avancé et ViSQOL
reculent un peu. Ce réglage ne fait que compenser : il donne des bits à tous les blocs courts
pour réparer ceux d'un seul extrait.

### La vraie cause : le regroupement des fenêtres courtes

Un groupe par fenêtre (`g8`) ramène Lebanon Hanover de −0,545 à −0,232 et la sonie du bruit de
0,92 à 0,20 (Opus : 0,15), pour +12 % de débit. Avec `short_db` −6, elle n'était tombée qu'à
0,49. La règle de production sépare deux fenêtres quand leur énergie **totale** varie de plus de
`group_db` (6 dB). Sur Lebanon Hanover, cette énergie est dominée par les graves (46 dB sous
100 Hz). Une attaque dans les aigus (charleston, caisse claire) ne la fait presque pas bouger :
les fenêtres calmes sont groupées avec celle de l'attaque, et partagent son énergie et son
allocation. Le bruit des aigus s'étale alors sur toute la trame.

**`group_mode` 1.** Une séparation de plus quand l'une des quatre régions de la fenêtre
(0-1,4 kHz, 1,4-4,1 kHz, 4,1-8,3 kHz, au-delà) varie de plus de `group_db`, à condition que la
région soit à moins de 40 dB de la fenêtre. Seul l'encodeur change : le masque des groupes est
déjà transmis. La production reste identique au bit près.

| à q −7 | Lebanon ODG | kb/s | RmsNoiseLoudB | Salut c'est cool | Eminem | Zombie |
|---|---|---|---|---|---|---|
| production (6 dB, énergie totale) | −0,545 | 136,0 | 0,924 | −0,163 | −0,108 | −0,317 |
| `g8` (un groupe par fenêtre) | −0,232 | 152,9 | 0,200 | −0,161 | −0,107 | −0,315 |
| `group_db` 3 (énergie totale) | −0,253 | 143,7 | 0,240 | −0,158 | −0,108 | −0,311 |
| régions, 6 dB | −0,233 | 143,2 | 0,200 | −0,156 | −0,104 | −0,319 |
| régions, 8 dB | −0,233 | 139,5 | 0,199 | −0,161 | −0,100 | −0,315 |
| **régions, 10 dB** | **−0,232** | **137,0** | **0,200** | −0,160 | −0,106 | −0,311 |

Le défaut de Lebanon Hanover disparaît presque entièrement (+0,31 d'ODG pour +0,7 % de débit).
Les autres extraits ne bougent pas. Mesure à débit égal en cours sur `test` : régions à 8, 10 et
12 dB (`gr_test.csv`).

### Regroupement par régions sur `test`, à débit égal (`gr_test.csv`)

| seuil | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | 2f @128 | débit à q égal | régressions ODG |
|---|---|---|---|---|---|---|---|---|
| production | −0,1725 | −0,0144 | −0,3546 | −0,1402 | 4,6082 | 106,15 | | |
| 8 dB | −0,1629 | −0,0044 | −0,3640 | −0,1459 | 4,6082 | 106,11 | +0,4 % | 0 |
| 10 dB | −0,1614 | −0,0041 | −0,3622 | −0,1446 | 4,6085 | 106,34 | +0,2 % | 0 |
| **12 dB** | **−0,1607** | **−0,0037** | −0,3623 | −0,1444 | 4,6085 | **106,40** | **0,0 %** | 0 |

À 12 dB : ODG +0,012 à 128 kb/s, +0,011 à 160, intervalle de confiance à 95 % de ±0,022. Le gain
vient de Lebanon Hanover (+0,33). Sans lui, l'effet est nul (+0,001). Aucun extrait ne régresse
de plus de 0,02 en ODG. Le débit est inchangé.

**PEAQ avancé dit le contraire sur Lebanon Hanover**, et sur lui seul. Ailleurs, il donne raison
au regroupement par régions : Korpiklaani +0,078, Salut c'est cool +0,066, And One +0,047 à q −6.

| Lebanon Hanover | kb/s | ODG | ODG avancé | ViSQOL | 2f | NMR interne |
|---|---|---|---|---|---|---|
| production q −6 | 126,3 | −0,633 | **−0,126** | 4,703 | 86,9 | +3,0 dB |
| régions 10 dB, q −6 | 127,3 | **−0,263** | −0,578 | **4,708** | **92,5** | **+1,4 dB** |
| Opus 128 | 130,3 | −0,107 | −0,457 | 4,687 | 118,3 | +3,2 dB |
| Opus 160 | 163,3 | −0,005 | −0,241 | 4,724 | 132,6 | +1,3 dB |

Quatre juges sur cinq préfèrent le regroupement par régions : PEAQ de base, ViSQOL, 2f et le NMR
interne. PEAQ avancé le pénalise, et pénalise Opus de la même façon. Sur cet extrait, PEAQ avancé
range le nouvel encodage du côté d'Opus. Les deux modèles de PEAQ ne voient pas la même chose : le
modèle de base, à FFT, sanctionne le bruit étalé dans le temps ; le modèle avancé, à banc de
filtres, sanctionne autre chose, que le découpage plus fin introduit et qu'Opus partage. Seule
l'oreille peut trancher. Écoute de l'extrait entier à q −6 (production 126,3 kb/s, régions
12 dB 125,8 kb/s, original), sur des fichiers locaux non publiés (musique sous droits).

### Décision (20/11/2026) : le regroupement par régions à 12 dB devient la production

Validé à l'écoute sur Lebanon Hanover : « cela sonne mieux que la version de production
actuelle ». Les valeurs par défaut sont désormais `group_mode` 1 et `group_db` 12, dans
`core/enc.c` et dans `py/mule/params.py`.

- Seul l'encodeur change : le format v3 reste le même, et le décodeur aussi (les 42 tests passent,
  vecteurs figés compris).
- La nouvelle production donne exactement les mêmes fichiers que la variante mesurée
  (`gr1d12`). La variante `gr0` (`group_mode` 0, 6 dB) redonne exactement l'ancienne production.
- Les variantes `gd3` et `gd4` fixent maintenant `group_mode` 0, pour garder le sens qu'elles
  avaient lors de la mesure.
- Les chiffres publiés de MULE (README, billet 1 : ODG −0,17 à 128 kb/s) datent de l'ancienne
  production : environ −0,16 avec la nouvelle. À mettre à jour au moment de la publication
  groupée.
- Prochaine étape : la garde tonale (`tg` 1), mesurée par-dessus la nouvelle production.
