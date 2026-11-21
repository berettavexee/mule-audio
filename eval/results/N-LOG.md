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

## Garde tonale par-dessus la nouvelle production (regroupement par régions)

Sur les extraits difficiles, à q −7. Belenos sert de témoin : MULE y bat Opus. ODG par extrait :

| | production | `tg_ton` 3 | **`tg_ton` 5** | `tg_ton` 8 | Opus 128 |
|---|---|---|---|---|---|
| Takemitsu | −0,242 | −0,205 | −0,213 | −0,236 | −0,139 |
| Zombie Zombie | −0,314 | −0,302 | **−0,292** | −0,306 | −0,107 |
| Belenos | −0,243 | −0,226 | −0,225 | −0,225 | −0,635 |
| Mravinsky | −0,233 | **−0,251** | −0,234 | −0,232 | −0,131 |
| Salut c'est cool | −0,159 | −0,166 | **−0,169** | −0,162 | −0,036 |
| Lebanon Hanover | −0,235 | −0,234 | −0,235 | −0,235 | −0,107 |
| Max Richter | −0,197 | −0,196 | −0,197 | −0,197 | −0,042 |
| Spector | −0,186 | −0,188 | −0,186 | −0,186 | −0,047 |
| trames dégradées (8 extraits) | 7,7 % | 2,6 % | 2,8 % | 5,6 % | |

- **Le défaut visé disparaît en grande partie.** Avec `tg_ton` 5, les trames dégradées passent de
  24,5 % à 4,8 % sur Takemitsu, et de 26,7 % à 9,6 % sur Zombie Zombie. L'ODG gagne +0,029 et
  +0,022, Belenos +0,018, pour 0,1 à 0,4 % de débit.
- **`tg_ton` 3 en fait trop** : Mravinsky −0,018, alors que Takemitsu gagne un peu plus.
  **`tg_ton` 8 ne fait presque rien.** 5 reste le bon réglage. Salut c'est cool perd 0,010, au
  niveau du bruit de mesure.
- **Lebanon Hanover est réglé par le regroupement** : 1,4 % de trames dégradées, et la garde n'y
  change rien.
- **Ce qui reste de l'écart avec Opus a une autre origine.** Sur Max Richter, Mravinsky, Spector
  et Salut c'est cool, l'écart est de 0,10 à 0,16, sans trames dégradées. MULE y dépense 118 à
  120 kb/s, contre 137 à 143 pour Opus. C'est la piste des morceaux calmes sous-dotés, où le
  masque de MULE serait trop indulgent.

### Garde tonale (`tg_ton` 5) sur `test`, à débit égal, contre la nouvelle production (`tg2_test.csv`)

Référence : `gr_test.csv`, configurations `mule-gr1d12`, qui donnent exactement les mêmes fichiers
que la production. Intervalles bootstrap à 95 %, sur les extraits.

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 |
|---|---|---|---|---|---|---|
| production | −0,1607 | −0,0037 | −0,3623 | −0,1444 | 4,6085 | 4,6354 |
| `tg` 1 | −0,1578 | −0,0010 | −0,3594 | −0,1429 | 4,6134 | 4,6376 |
| écart | +0,0029 [−0,0002 ; +0,0068] | +0,0027 [+0,0009 ; +0,0045] | +0,0030 [+0,0001 ; +0,0065] | +0,0016 [+0,0002 ; +0,0034] | +0,0049 | +0,0022 |

- **Toutes les mesures vont dans le même sens**, ce qui est rare dans ce projet. Aucune régression
  de plus de 0,02, sur aucune mesure. Le débit augmente de 0,03 % à q égal.
- **Les gains viennent des extraits attendus** : Takemitsu (+0,034 d'ODG, +0,18 de ViSQOL), Zombie
  Zombie (+0,033), Belenos (+0,026).
- **Le gain moyen (+0,003) reste sous le seuil d'adoption du projet** (+0,01). Ce seuil a été fixé
  pour les réglages d'encodeur, dont le gain se perd dans le bruit de mesure. Ici, le mécanisme
  est identifié, le défaut localisé, et la correction ne coûte rien ailleurs. Décision laissée à
  l'auteur.

### Décision (20/11/2026) : la garde tonale est adoptée (`tg` 1, `tg_ton` 5)

L'auteur : « tous les outils sont d'accord. Le seuil d'adoption était présent pour éviter de se
perdre dans des optimisations trop précoces de l'algorithme. On attaque la phase de fine tuning.
On peut être moins rigide sur le seuil d'adoption, d'autant plus quand il n'affecte pas le format
et ne génère aucune régression. »

Nouvelle règle pour cette phase de réglage fin : un changement de l'encodeur seul, sans aucune
régression, sur lequel toutes les mesures s'accordent, peut être adopté sous le seuil de +0,01.

## Zimtohrli, enfin lisible (`zimt_test.csv`)

`run_eval.py` écrivait les CSV avec `%.4f`. Les distances Zimtohrli (0,0001 à 0,0009) n'y
gardaient qu'un chiffre significatif, et la mesure était inexploitable depuis le début. L'écriture
passe à `%.6g` ; les CSV antérieurs restent tronqués pour cette colonne. Nouvelle mesure, Zimtohrli
seul (PEAQ et ViSQOL désactivés), sur `test`, à débit égal. Distance × 1000, plus petite = mieux.

| | @128 | @160 |
|---|---|---|
| ancienne production (`gr0`) | 0,3965 | 0,2104 |
| production (regroupement par régions) | **0,3794** | **0,1988** |
| production + garde tonale (`tg` 1) | 0,3818 | 0,1998 |

- **Le regroupement par régions est confirmé** : −2,9 % à 128 kb/s et −3,5 % à 160, intervalle de
  confiance entièrement négatif. Lebanon Hanover −55 à −63 %, Korpiklaani −10 à −15 %, aucun
  extrait pire de plus de 2 %. Cinquième juge d'accord, PEAQ avancé reste seul contre.
- **La garde tonale divise Zimtohrli** : +0,6 % en moyenne (intervalle [−0,2 ; +1,7 %]).
  - Takemitsu s'améliore (−4 à −9 %).
  - Beethoven 59 se dégrade de 11 à 14 %, et ViSQOL va dans le même sens (−0,013 à −0,019) ;
    l'ODG baisse un peu (−0,003 à −0,005).
  - Zombie Zombie se dégrade de 3,5 à 5,7 % pour Zimtohrli et de 0,019 pour ViSQOL, alors que PEAQ
    le voit s'améliorer (+0,014 à +0,041).
- **La condition d'adoption, « tous les outils d'accord, aucune régression », n'est donc pas
  remplie.** La garde n'est pas activée par défaut. Hypothèse : sur un orchestre, le critère de
  crête se déclenche sur des bandes à partiels, où le remplissage de bruit convenait. Piste :
  limiter la garde aux bandes hautes (19 à 21), où le défaut a été trouvé.

## La répartition des notes par extrait, codec par codec

ODG de chaque extrait de `test`, interpolée au débit moyen donné. MULE est la production actuelle
(regroupement par régions, sans garde tonale).

| à 128 kb/s | moyenne | médiane | écart type | p10 | p90 | pire | asymétrie | normalité (Shapiro p) |
|---|---|---|---|---|---|---|---|---|
| MULE | −0,161 | −0,153 | 0,074 | −0,259 | −0,085 | −0,335 | −0,48 | 0,66 |
| Opus | −0,116 | **−0,092** | 0,113 | −0,141 | −0,052 | −0,685 | **−4,37** | 0,000 |
| Apple AAC | −0,314 | −0,277 | 0,120 | −0,456 | −0,206 | −0,683 | −1,33 | 0,002 |
| FDK AAC | −0,540 | −0,537 | 0,248 | −0,849 | −0,267 | −1,199 | −0,82 | 0,11 |
| Vorbis | −0,449 | −0,412 | 0,184 | −0,630 | −0,286 | −1,125 | −1,85 | 0,000 |

À 160 kb/s : MULE −0,004 de moyenne, +0,009 de médiane, écart type 0,082 ; Opus +0,001, +0,010
et 0,075.

- **MULE suit à peu près une gaussienne** (Shapiro p = 0,66, presque symétrique) : régulier,
  sans catastrophe, mais toute sa distribution est décalée. Sa médiane à 128 kb/s est 0,06 en
  dessous de celle d'Opus.
- **Opus n'est pas gaussien du tout** : une asymétrie de −4,4. La plupart des extraits sont
  excellents, et le cœur de la distribution est deux fois plus serré que celui de MULE (de p10
  à p90 : 0,089 contre 0,174). Mais un extrait s'effondre : Belenos à −0,685. C'est lui qui gonfle
  l'écart type d'Opus (0,113 contre 0,074). Le test de Levene ne distingue pas les deux variances
  (p = 0,70) : l'écart type, dominé par une valeur aberrante, est la mauvaise mesure ici.
- **Deux profils** : Opus est très bon presque partout, avec de rares accidents ; MULE est un peu
  moins bon partout, sans accident. Le retard moyen de MULE n'est plus porté par quelques
  extraits : il est diffus, sur tout le cœur de la distribution.
- **À 160 kb/s, les médianes de MULE et d'Opus sont identiques** (+0,009 et +0,010).

### La garde limitée aux bandes hautes (`tg_band` 19 et 20, `tgb_test.csv`)

Quatre juges, à débit égal, contre la production. Zimtohrli en écart relatif, plus petit = mieux.

| | ODG @128 | ODG avancé @128 | ViSQOL @128 | Zimtohrli @128 | Beethoven 59, Zimtohrli |
|---|---|---|---|---|---|
| `tg` 1, toutes bandes | +0,0029 | +0,0030 | +0,0049 | +0,61 % | +11,3 % |
| bandes 19 et plus | +0,0026 | +0,0030 | +0,0051 | +0,61 % | +11,3 % |
| bandes 20 et plus | +0,0024 | +0,0028 | +0,0049 | +0,61 % | +11,3 % |

- **L'hypothèse est réfutée.** La dégradation de Beethoven 59 ne vient pas de partiels dans les
  bandes moyennes. Elle est identique quand la garde est limitée aux bandes 20 et 21 : sur cet
  extrait, la garde agit à 277 reprises dans la bande 20.
- **La part d'énergie de la raie ne sépare pas non plus les cas.** Dans les trames gardées, la
  raie porte en médiane 28 % de l'énergie de la bande sur Takemitsu (où la garde aide), 29 % sur
  Beethoven 59 (où elle nuit), 35 % sur Zombie Zombie.
- **Explication probable.** Une bande codée à l'allocation 1 perd son remplissage de bruit : ses
  coefficients arrondis à zéro restent nuls. Le reste de la bande, qui était du bruit, devient
  un trou autour de la raie. PEAQ y voit surtout la raie retrouvée ; ViSQOL et Zimtohrli voient
  surtout le trou. Le format v3 ne permet pas les deux à la fois : il y a du bruit seulement à
  allocation 0. Le remède propre serait un remplissage de bruit des coefficients nuls dans les
  bandes codées, comme dans l'USAC. C'est un changement de format, à noter pour une v4.
- **La garde n'est pas activée.** Fichiers d'écoute locaux, non publiés : Beethoven 59, Zombie
  Zombie et Takemitsu, production contre `tg` 1 à q −6, avec l'original.

### Décision (20/11/2026) : la garde tonale reste une option

À l'écoute, l'auteur n'entend pas de différence sur Beethoven 59, Zombie Zombie et Takemitsu. La
garde reste disponible (`tg` 1, variantes `tg1*`) et désactivée par défaut.

## Ce que décide l'encodeur d'Apple, lu dans ses trames (`eval/aac_frames.py`)

Lecteur de flux AAC-LC écrit pour l'occasion. Il s'arrête avant les données spectrales : il lit le
type de bloc, le regroupement des fenêtres courtes, `max_sfb` (la bande passante), le masque
M/S, le codebook de chaque bande du premier canal (bande à zéro, PNS, intensité, codée) et la
taille des trames. Apple q63 (~124 kb/s) contre FDK 128 et MULE q −7. Les 0,2 % de blocs courts
communs à tous sont les premières trames du fichier.

| extrait | blocs courts Apple / FDK / MULE | groupes par trame courte | M/S Apple / FDK | taille max/moyenne Apple / FDK |
|---|---|---|---|---|
| Lebanon Hanover | 17,7 / 10,2 / 17,2 % | 3,1 / 4,0 / 1,9 | 87 / 98 % | 1,68 / 1,43 |
| Eminem | **20,2** / 6,8 / 11,4 % | 2,3 / 4,0 / 1,8 | 63 / 99 % | 2,16 / 1,51 |
| New Order | **12,2** / 2,2 / 3,1 % | 2,2 / 4,0 / 1,9 | 59 / 99 % | 1,82 / 1,57 |
| Salut c'est cool | 7,2 / 5,2 / 5,9 % | 2,6 / 4,0 / 1,8 | 75 / 99 % | 1,90 / 1,50 |
| Monster Magnet | 2,8 / 0,3 / 0,8 % | 2,4 / 4,0 / 2,0 | **27** / 100 % | 1,63 / 1,41 |
| Zombie Zombie | 0,8 / 2,2 / 2,3 % | 2,8 / 4,0 / 2,9 | 61 / 100 % | **2,44** / 1,48 |
| Takemitsu, Belenos, Max Richter, Mravinsky, Beethoven 59, Classical | ≤ 1 % partout | | 75 à 94 / 80 à 100 % | 1,25 à 1,57 / 1,41 à 1,54 |

Aucun des deux AAC n'utilise la PNS ni l'intensité stéréo à ce débit.

**Les bandes mises à zéro** (trames longues, premier canal) :

| | 0-4 kHz | 4-8 | 8-12 | 12-16 | 16-20 kHz |
|---|---|---|---|---|---|
| Apple, Takemitsu | 0,3 % | 0,2 | 0,3 | 1,9 | **82** |
| Apple, Zombie Zombie | 1,0 | 7,0 | 6,3 | 14,2 | **78** |
| Apple, Lebanon Hanover | 0,2 | 0,2 | 0,3 | 1,6 | **78** |
| Apple, Monster Magnet | 0,1 | 0,2 | 0,6 | 5,8 | **86** |
| Apple, Max Richter | 0,1 | 0,2 | 0,3 | 1,5 | **99** |
| FDK (coupe à 15,8 kHz) | 0 à 1,7 | 0 à 1,2 | 0 à 3,9 | 0,2 à 13,2 | – |

### Lecture

- **Le haut du spectre, à la demande.** Apple déclare une bande passante de 20 kHz, mais met à zéro
  80 à 99 % des bandes entre 16 et 20 kHz. Il ne les code que lorsqu'elles contiennent quelque
  chose qui vaut la peine : c'est ainsi qu'il garde la raie de Takemitsu, tout en atténuant
  16-20 kHz de 10 dB en moyenne. En dessous de 16 kHz, il ne met presque rien à zéro. FDK coupe
  net à 15,8 kHz. MULE, lui, remplit toujours de bruit à l'énergie de la bande au-dessus de
  13,4 kHz : il ne coupe jamais et ne garde jamais une raie seule dans ses bandes à 0 bit.
- **Plus de blocs courts sur la musique percussive.** Apple en met beaucoup plus sur Eminem
  (20 % contre 11 % pour MULE) et New Order (12 % contre 3 %). Sur la musique calme, tous sont à
  zéro. Ses trames courtes reçoivent 1,0 à 1,3 fois les octets d'une trame longue.
- **Le regroupement des fenêtres courtes.** FDK fait toujours 4 groupes. Apple en fait 2 à 3 et
  s'adapte. MULE en fait encore moins (1,8 à 2,0), même avec le nouveau regroupement par régions.
- **Le M/S, bande par bande.** FDK est en M/S presque partout (80 à 100 %). Apple choisit vraiment :
  27 % seulement sur Monster Magnet, 59 à 63 % sur New Order, Zombie Zombie et Eminem.
- **Les octets suivent le signal.** La plus grosse trame d'Apple fait 1,3 à 2,4 fois la moyenne,
  contre 1,4 à 1,5 pour FDK, limité par son débit constant et son réservoir.

### Pistes pour MULE (encodeur seul)

1. **Plus de groupes dans les trames courtes** : `group_db` 6 ou 8 avec les régions donnait le même
   ODG sur Lebanon Hanover pour plus de débit, mais n'a pas été mesuré par Zimtohrli ni sur les
   extraits percussifs (Eminem, New Order).
2. **Plus de blocs courts sur les attaques modestes** (Eminem, New Order) : `tr_db` plus bas. À
   remesurer maintenant que les trames courtes sont mieux regroupées : le levier F (`tr_db` 7 et
   8,5) datait d'avant.
3. **La bande 21 (17,2-19,9 kHz) muette plutôt que remplie de bruit**, sauf quand elle est codée, à
   la manière d'Apple au-dessus de 16 kHz.

### Les trois pistes inspirées d'Apple, sur 12 extraits (`pistes_apple.csv`)

Eminem, New Order, Lebanon Hanover, Salut c'est cool, Monster Magnet, Zombie Zombie, Takemitsu,
Max Richter, Belenos, Spector, Airbourne, Korpiklaani. q −6 et −9, interpolé à 135 kb/s, contre
la production. Pour Zimtohrli, écart relatif, plus petit = mieux.

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | pire extrait (ODG) |
|---|---|---|---|---|---|
| régions, 6 dB (`gr1`) | −0,008 | −0,011 | −0,001 | +2,9 % | New Order −0,018 |
| régions, 8 dB (`gr1d8`) | −0,003 | −0,006 | −0,001 | +1,3 % | New Order −0,012 |
| attaques à 7 dB (`tr7`) | −0,001 | −0,005 | +0,001 | −1,8 % | Salut c'est cool −0,013 |
| **attaques à 8,5 dB (`tr85`)** | **+0,001** | **+0,000** | **+0,000** | **−1,8 %** | New Order −0,003 |
| muettes au-dessus de 17,2 kHz (`nf21`) | −0,024 | −0,003 | −0,097 | +13,8 % | Max Richter −0,070 |
| muettes au-dessus de 13,4 kHz (`nf20`) | −0,030 | −0,007 | −0,107 | +15,9 % | Max Richter −0,165 |

- **Des groupes plus fins : rejeté.** Moins bien sur les quatre juges. Les 12 dB restent.
- **Le détecteur d'attaques à 8,5 dB : candidat.** Les quatre juges vont dans le même sens, sans
  régression. Validation lancée sur les 30 extraits.
- **Les bandes hautes muettes : rejeté, nettement.** ViSQOL −0,1, Zimtohrli +14 à 16 %
  (Takemitsu +60 %). Le remplissage de bruit des aigus est un atout de MULE. Couper comme Apple
  n'est pas à copier, et c'est peut-être une raison du ViSQOL plus faible d'Apple (4,49). Inutile
  d'essayer une coupure au milieu d'une bande en v3 ; l'idée v4 reste valable pour la forme du
  bruit, pas pour couper.

### Détecteur d'attaques à 8,5 dB sur `test` (`tr85_test.csv`), contre la production

Débit identique à q égal (119,96 contre 119,99 kb/s à q −6). Intervalles bootstrap à 95 %.
Zimtohrli en écart relatif, plus petit = mieux.

| | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| @128 | +0,0007 [−0,0003 ; +0,0016] | +0,0010 [−0,0007 ; +0,0025] | +0,0004 [+0,0002 ; +0,0007] | **−0,97 %** [−2,05 ; −0,05] | aucune |
| @160 | +0,0006 [−0,0012 ; +0,0018] | +0,0002 | +0,0003 | **−0,98 %** [−2,09 ; −0,16] | Kompromat, Zimtohrli +2,7 % |

Les quatre juges vont dans le même sens. L'effet est minuscule pour PEAQ et ViSQOL, mais net
pour Zimtohrli : Lebanon Hanover −9 à −14 %, Garbage −8 à −9 %. Le gain tient sur la longueur
des pré-échos que l'on évite, ce que Zimtohrli mesure mieux que PEAQ. Seul accroc : Kompromat,
+2,7 % pour Zimtohrli à 160 kb/s.

### Décision (20/11/2026) : le détecteur d'attaques à 8,5 dB devient la production

`tr_db` passe de 10 à 8,5 dB par défaut (C et Python). La nouvelle production donne exactement les
fichiers de `tr85`, et `tr10` redonne exactement la précédente. Les 42 tests passent. Les
variantes ne fixent que leurs propres champs : celles mesurées avant cette décision (`gr0`,
`tg1*`, `nf2*`…) l'ont été avec 10 dB, celles d'après hériteront de 8,5 dB. L'effet sur la
moyenne est trop petit pour changer les chiffres du README (+0,0007 d'ODG à 128 kb/s).

## Les morceaux calmes

### Ce que PEAQ reproche (MULE q −7 contre Opus 128)

| extrait | ODG Opus / MULE | kb/s | NMR total | ADBB | AvgModDiff1B | BandwidthTestB |
|---|---|---|---|---|---|---|
| Max Richter | −0,042 / −0,198 | 143 / 118 | −14,0 / −13,6 | −0,68 / +0,17 | 7,6 / **10,6** | 905 / 855 |
| Mravinsky | −0,131 / −0,233 | 143 / 120 | −12,7 / −13,1 | −0,09 / +0,40 | 7,9 / **9,7** | 898 / 855 |
| Spector | −0,047 / −0,182 | 134 / **137** | −14,5 / −14,9 | −0,32 / **+0,78** | 8,2 / 8,5 | 902 / 864 |
| Salut c'est cool | −0,036 / −0,171 | 137 / 120 | −15,5 / −14,9 | −0,40 / +0,42 | 7,0 / 7,8 | 895 / 857 |
| Beethoven 59 | −0,062 / −0,139 | 140 / 122 | −13,2 / −13,2 | −0,83 / −0,48 | 8,7 / 9,8 | 895 / 855 |
| Brahms | −0,109 / −0,095 | 131 / 118 | −13,7 / −14,1 | −0,14 / −0,41 | 8,2 / 9,2 | 901 / 855 |

- **Ce n'est pas d'abord une question de bits** : le NMR de PEAQ est équivalent, et Spector perd
  autant avec autant de bits qu'Opus. Ce qui s'écarte : la modulation de l'enveloppe
  (AvgModDiff1B) et la probabilité de détection (ADBB).
- **BandwidthTestB** : environ 45 raies FFT plus bas chez MULE, qui s'arrête à 19,98 kHz. C'est le
  piège des 20 kHz (une coupure inaudible que PEAQ pénalise), connu et laissé de côté.

### Où l'enveloppe est déformée

Enveloppe par bande (STFT, pas de 5,8 ms). Erreur rms de l'enveloppe en dB, MULE / Opus :

- **Classique calme** (Max Richter, Mravinsky) : MULE est pire entre 2 et 6 kHz (0,59 à 0,91
  contre 0,45 à 0,54 dB). Ce sont des bandes faibles, quelques Bark au-dessus de l'énergie
  principale.
- **Pop** (Spector, Salut c'est cool) : MULE est pire de 6 à 17 kHz (Spector 13,4-17,2 kHz : 2,40
  contre 1,00), avec une enveloppe aplatie (modulation à 73 à 94 % de l'original, Opus 91 à
  101 %). C'est l'étalement temporel des trames longues et du remplissage de bruit.

### Hypothèse pour le classique calme : l'étalement du masquage ne dépend pas du niveau

Le modèle de MULE étale le masquage avec la fonction de Schroeder : une pente vers l'aigu
d'environ −10 dB par Bark, quel que soit le niveau. Selon Terhardt (la formule du modèle d'oreille
de PEAQ), cette pente vaut −24 − 230/f + 0,2·L dB par Bark : environ −16 à 40 dB SPL, −8 à
80 dB SPL. Sur un passage calme, Schroeder surestime donc le masquage quelques Bark au-dessus de
l'énergie principale, là où MULE déforme l'enveloppe. Option `spread_mode` 1 : l'étalement de
Terhardt, dépendant du niveau (96 dB SPL = pleine échelle, pente vers le grave −27 dB par Bark),
pour les masques de bandes ; les masques fins des bandes graves gardent Schroeder. La production
reste identique au bit près. Le débit monte nettement à q égal (+4 % sur Takemitsu, +17 à +20 %
sur Zombie Zombie et Eminem) : la comparaison se fait donc à débit égal (`calme_sp.csv`,
12 extraits).

### Résultat : l'étalement de Terhardt (`calme_sp.csv`, 12 extraits, débit égal)

| à 135 kb/s | ODG | ODG avancé | ViSQOL | Zimtohrli |
|---|---|---|---|---|
| moyenne des 12 | −0,005 | −0,005 | +0,000 | **+5,8 %** |
| Max Richter | **+0,089** | +0,048 | 0,000 | **−15,2 %** |
| Mravinsky | **+0,061** | +0,050 | +0,013 | **−18,7 %** |
| Belenos | −0,067 | −0,015 | −0,005 | +12,8 % |
| Classical | −0,063 | −0,025 | −0,013 | +12,2 % |
| Takemitsu | −0,037 | −0,081 | −0,072 | +13,2 % |
| Lebanon Hanover | −0,001 | 0,000 | −0,002 | +19,1 % |
| Airbourne | −0,005 | −0,032 | +0,001 | +22,2 % |

À 125 kb/s, même tableau, en plus marqué (Zimtohrli +9,6 %).

- **L'hypothèse est confirmée là où elle était posée.** Sur Max Richter et Mravinsky, tous les
  juges s'améliorent nettement : le masque de Schroeder était trop indulgent au-dessus de leur
  énergie principale.
- **Appliqué partout, l'étalement de Terhardt dégrade le reste.** Il est bien plus raide que
  Schroeder près de la bande masquante, même à niveau moyen (−12 dB contre −4 dB à 1 Bark,
  à 60 dB SPL). Il abaisse donc les masques presque partout (+17 à +20 % de débit à q égal sur
  Zombie Zombie et Eminem) et rompt l'équilibre des décalages (14,5 + z, 5,5, `low_db`,
  `mid_db`), réglés avec Schroeder.
- **`spread_mode` 2** (le plus petit des deux étalements) coûte presque le même débit que le
  mode 1 : ce ne sont pas les sons forts, au-delà de 80 dB SPL, qui posent problème.
- **Aucun niveau ne sépare les cas.** Bande la plus forte : Max Richter 76 dB SPL, Mravinsky 72 (ils
  gagnent) ; Belenos 77, Brahms 57, Takemitsu 47 (ils perdent). Brahms et Takemitsu, les plus
  calmes, perdent. Le spectre très incliné de Max Richter et Mravinsky (environ 30 à 40 dB entre
  la bande la plus forte et 1,4-4,8 kHz) se retrouve chez Lebanon Hanover, qui perd aussi.
- Options laissées : non adoptées. Pistes : une pente intermédiaire (un réglage, donc une
  recalibration des décalages à la clé), ou un critère qui reste à trouver.

### Pistes 1 (étalement à la MPEG-1) et 3 (critère relatif d'Opus), sur 12 extraits (`calme_p13.csv`)

Contre la production (`calme_sp.csv`), interpolé à 130 kb/s. Zimtohrli en écart relatif, plus
petit = mieux.

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | gagnants | perdants |
|---|---|---|---|---|---|---|
| **`sp3`** (Schroeder jusqu'à 1 Bark, puis Terhardt si plus raide) | **+0,0074** | **+0,0060** | **+0,0010** | **−1,2 %** | Max Richter +0,076 / −19,8 %, Mravinsky +0,030 / −12,2 %, Beethoven 59 +0,015 / −3,0 % | Airbourne −0,012 / +8,3 %, Eminem −0,008 / +3,2 %, Lebanon Hanover +3,3 %, Takemitsu −0,008 / +2,8 % |
| `sp3d2` (à partir de 2 Bark) | +0,0016 | +0,0029 | +0,0013 | −0,5 % | Max Richter +0,028 / −8,5 % | Airbourne +2,3 % |
| `dy05` (Opus, 0,5) | +0,0079 | −0,0073 | +0,0030 | +1,4 % | **Belenos +0,217 / −25,6 %** | tous les autres, −0,007 à −0,022 |
| `dy1` (Opus, 1) | −0,0043 | −0,0259 | +0,0026 | +6,1 % | Belenos +0,254 / −32,7 % | tous les autres |

- **La piste 1 marche.** Les quatre juges s'améliorent en moyenne. `sp3` garde l'essentiel du gain
  de Terhardt sur Max Richter et Mravinsky, sans les grosses pertes (Belenos −0,067 → −0,002). Il
  reste des pertes modérées sur le rock fort (Airbourne, Eminem, Lebanon Hanover). La cause : au-delà
  d'un Bark, la pente de Schroeder n'est que de −7 à −8 dB par Bark ; celle de Terhardt est plus
  raide dès que la bande masquante est sous 80 dB SPL environ, donc sur presque toute la musique.
  `sp3d2` est plus prudent : gains et pertes plus petits.
- **La piste 3 ne sert qu'à Belenos**, mais de façon spectaculaire : +0,22 à +0,25 d'ODG, −26 à −33 %
  pour Zimtohrli. C'est justement l'extrait où Opus s'effondre. Partout ailleurs, elle dégrade.
  À comprendre : Belenos a des bandes qui ressortent nettement de leurs voisines, et le masque de
  MULE les y sous-dote.

### Le paradoxe de Belenos : un morceau affamé, pas un critère miracle

Le critère d'Opus (`dy05`) fait passer Belenos de 157 à 183 kb/s à q −7 (+16 %) : il y trouve
beaucoup de bandes qui dépassent l'enveloppe basse et leur donne des bits. **Au même débit sur
Belenos (175 kb/s), il fait un peu moins bien que la production** (ODG −0,093 contre −0,072). Son
« gain » à débit moyen égal sur les 12 extraits n'était qu'un transfert de bits vers Belenos, pris
aux autres extraits.

| Belenos | kb/s | ODG |
|---|---|---|
| MULE q −6 | 148 | −0,41 |
| MULE q −9 | 176 | −0,06 |
| Opus 128 | 153 | −0,64 |
| Opus 160 | 187 | −0,27 |
| Apple q63 | 134 | −0,68 |

Belenos a une courbe débit/qualité très raide : +0,35 d'ODG pour +19 % de débit chez MULE. Opus
et Apple s'y effondrent parce que leur débit variable ne lui donne pas assez de bits pour franchir
la pente, pas à cause de leur critère. MULE, qui vise le même rapport bruit/masque partout, lui en
donne déjà plus. C'est la même leçon que l'analyse Apple contre FDK : la répartition des bits
entre extraits pèse autant que le codage. La bande passante de référence de Belenos est basse
(BandwidthRefB 727, environ 17 kHz) : ce n'est pas un effet des 20 kHz.

### Piste 1 sur `test` (`sp3_test.csv`), contre la production actuelle (`tr85_test.csv`)

Intervalles bootstrap à 95 %. Zimtohrli en écart relatif, plus petit = mieux. Régression : ODG
ou ODG avancé < −0,02, ViSQOL < −0,01, Zimtohrli > +3 %.

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | Zimtohrli @128 | @160 | débit à q égal |
|---|---|---|---|---|---|---|---|---|
| `sp3` (1 Bark) | +0,0055 [−0,0008 ; +0,0128] | **+0,0107** [+0,0027 ; +0,0187] | +0,0064 | +0,0023 | +0,0025 | −1,4 % | 0,0 % | +2,7 % |
| `sp3d2` (2 Bark) | +0,0021 [−0,0006 ; +0,0050] | +0,0034 | +0,0028 [+0,0000 ; +0,0068] | +0,0007 | +0,0009 | −0,4 % | +0,1 % | +0,5 % |

- **`sp3`** gagne plus : Max Richter +0,08 à +0,09 et −19 à −22 %, Mravinsky, Zombie Zombie. Mais il
  fait régresser plusieurs extraits : Monster Magnet −0,058 d'ODG à 160 kb/s ; Takemitsu −0,022,
  ViSQOL −0,011 à −0,021 et Zimtohrli +8,5 % ; Zimtohrli +3 à +6 % sur le rock et la synthwave
  (Airbourne, Carpenter Brut, Foo Fighters, Steel Panther, Dance with the Dead).
- **`sp3d2`** gagne moins, mais proprement. À 128 kb/s, les quatre juges sont positifs, sans
  aucune régression. À 160 kb/s, c'est neutre, avec une seule régression limite (Classical
  −0,021 d'ODG). Gains : Max Richter +0,03 / −9 %, Zombie Zombie, Beethoven 59.

### Décision (20/11/2026) : l'étalement à la MPEG-1, au-delà de 2 Bark, devient la production

`spread_mode` 3 et `sp_dz` 2 par défaut, dans l'encodeur C et en Python. La production donne
exactement les fichiers de `sp3d2`, et `sp0` (Schroeder seul) redonne exactement la précédente.
Les 42 tests passent. Le seuil de 1 Bark gagnait plus (ODG +0,011 à 160 kb/s), mais faisait
régresser Monster Magnet, Takemitsu, et le rock pour Zimtohrli : à reprendre plus tard, en
comprenant ces pertes.

## Bilan de la phase de réglage fin (20/11/2026)

Adoptés, encodeur seul, format v3 inchangé :
1. le regroupement des fenêtres courtes par régions de fréquence, à 12 dB (Lebanon Hanover) ;
2. le détecteur d'attaques à 8,5 dB ;
3. l'étalement du masquage à la MPEG-1 au-delà de 2 Bark (Max Richter, Mravinsky).

En option : la garde tonale (`tg`), l'étalement de Terhardt (`spread_mode` 1, 2), le critère
d'Opus (`dyn_a`), les bandes hautes muettes (`nf_top`), le seuil de 1 Bark. Rejetés : des groupes
plus fins, les bandes hautes muettes.

## Mesure de référence de la production réglée (`prod2_test.csv`)

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | Zimtohrli ×1000 @128 | @160 |
|---|---|---|---|---|---|---|---|---|
| production du matin | −0,1725 | −0,0144 | −0,3546 | −0,1402 | 4,6082 | 4,6350 | 0,3965 | 0,2104 |
| après le regroupement par régions | −0,1607 | −0,0037 | −0,3623 | −0,1444 | 4,6085 | 4,6354 | 0,3794 | 0,1988 |
| **production réglée** | **−0,1580** | **+0,0003** | −0,3585 | −0,1435 | **4,6099** | **4,6360** | **0,3735** | **0,1962** |
| Opus | −0,1164 | +0,0013 | −0,4405 | −0,2376 | 4,5397 | 4,6556 | | |

Distribution de l'ODG par extrait :

| à 128 kb/s | moyenne | médiane | p10 | p90 | p10-p90 | écart interquartile | écart type | pire |
|---|---|---|---|---|---|---|---|---|
| matin | −0,173 | −0,157 | −0,268 | −0,085 | 0,183 | 0,072 | 0,105 | −0,576 (Lebanon Hanover) |
| régions | −0,161 | −0,153 | −0,259 | −0,085 | 0,175 | 0,080 | 0,074 | −0,335 (Zombie Zombie) |
| **réglée** | **−0,158** | **−0,151** | −0,256 | −0,084 | **0,172** | 0,073 | **0,070** | **−0,308** (Zombie Zombie) |
| Opus | −0,116 | −0,092 | −0,141 | −0,052 | 0,088 | 0,047 | 0,113 | −0,685 (Belenos) |

À 160 kb/s : moyenne −0,014 → **+0,000** (Opus +0,001), médiane +0,003 → +0,009 (Opus +0,010),
écart type 0,108 → 0,082, pire extrait −0,419 → −0,176 (Takemitsu).

- **Le gain de la journée tient surtout à la valeur aberrante supprimée.** Lebanon Hanover passe de
  −0,58 à −0,24 (+0,34). L'écart type tombe de 0,105 à 0,070, et le pire extrait remonte de
  −0,58 à −0,31. MULE n'a plus d'extrait catastrophique, Opus en garde un (Belenos).
- **Le cœur de la distribution a très peu bougé.** Médiane −0,157 → −0,151 ; largeur de p10 à p90
  0,183 → 0,172. Il reste deux fois plus large que celui d'Opus (0,088), et décalé d'environ
  0,06 en médiane. Les réglages suivants ont amélioré un peu tout le monde (Max Richter +0,03 à
  +0,04, Holst +0,04, Zombie Zombie +0,02), sans resserrer le nuage.
- **À 160 kb/s, MULE rejoint Opus** en moyenne (+0,000 contre +0,001) et en médiane (+0,009
  contre +0,010). Zimtohrli −6 à −7 % sur la journée. Seul PEAQ avancé recule un peu
  (−0,004 à 128 kb/s), à cause de Lebanon Hanover (voir plus haut : l'écoute a tranché).
- **README** : les chiffres arrondis ne changent pas (−0,16 ; 0,00 ; −0,36 / −0,14 ; 4,61).

# Branche v4 : du bruit dans les coefficients nuls des bandes codées (20/11/2026)

Prototype de format (drapeau d'en-tête `MULE_NF_CODED`). Par canal et par trame, 3 bits bruts
donnent un niveau : 0 = aucun, sinon un rms de 0,5 × 2^(−(n−1)/2) unités de niveau D/2 (−6 à
−24 dB). Le décodeur remplit de bruit (le même générateur congruentiel, en entiers) les
coefficients au niveau 0 des bandes codées, à partir de la bande 12 (2,8 kHz). L'encodeur
mesure le rms de ce que les zéros ont laissé (x / (D/2)), le décale de `nf_off_db` et écrit le
niveau à la place réservée en tête du canal. Sans le drapeau, la sortie v3 est identique au bit
près sur tout le corpus (576 encodages). Coût : 3 bits par canal et par trame, 0,26 kb/s.

### Premier essai, 12 extraits (`v4nf_12.csv`), à 135 kb/s, contre la production v3 (`prod2_test.csv`)

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli |
|---|---|---|---|---|
| niveau mesuré (`nfc`) | −0,019 | −0,055 | +0,005 | +4,0 % |
| −3 dB (`nfcm3`) | +0,006 | −0,024 | +0,006 | −0,2 % |
| −6 dB (`nfcm6`) | +0,010 | −0,009 | +0,004 | −1,1 % |
| niveau mesuré + garde tonale (`nfctg`) | −0,014 | −0,053 | +0,009 | +3,5 % |
| **−3 dB + garde tonale (`nfcm3tg`)** | **+0,013** | −0,018 | **+0,026** | **−1,8 %** |

- **Au niveau mesuré, le bruit est trop fort** : tous les juges reculent sauf ViSQOL. Plus il est
  bas, mieux PEAQ de base et Zimtohrli le reçoivent.
- **PEAQ avancé le pénalise partout**, sur chaque extrait, de moins en moins à mesure que le niveau
  baisse (−0,055 ; −0,024 ; −0,009).
- **Le bruit débloque la garde tonale** : Takemitsu passe à ViSQOL +0,154 et Zimtohrli −21,6 %,
  Zombie Zombie à ODG +0,055 et Zimtohrli −11,7 %. Beethoven 59, qui perdait 11 % pour Zimtohrli
  avec la garde seule, n'en perd plus que 3,2 %.
- Suite : des niveaux plus bas (−9 et −12 dB) et la garde à −6 et −9 dB (`v4nf_12b.csv`).

### Second essai : niveaux plus bas (`v4nf_12b.csv`), même base, 135 kb/s

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions (ODG < −0,02, ViSQOL < −0,01, Zimtohrli > +3 %) |
|---|---|---|---|---|---|
| −6 dB | +0,010 | −0,009 | +0,004 | −1,1 % | 1 (Takemitsu, ViSQOL −0,011) |
| −9 dB | +0,008 | −0,004 | +0,002 | −0,8 % | 0 |
| −12 dB | +0,006 | −0,001 | +0,000 | −0,3 % | 0 |
| −3 dB + garde | +0,013 | −0,018 | +0,026 | −1,8 % | 9 |
| **−6 dB + garde** | **+0,017** | −0,002 | **+0,021** | **−2,4 %** | 1 (Beethoven 59, Zimtohrli +4,2 %) |
| **−9 dB + garde** | +0,015 | **+0,004** | +0,016 | −1,5 % | 1 (Beethoven 59, Zimtohrli +6,7 %) |

- Seul, le bruit aide un peu (ODG +0,006 à +0,010), et PEAQ avancé ne l'accepte qu'autour de −12 dB.
- **Avec la garde tonale, c'est nettement mieux** : les quatre juges sont positifs ou neutres à
  −6 et −9 dB. ViSQOL gagne +0,016 à +0,021, et l'ODG +0,015 à +0,017, au-dessus du seuil d'un
  changement de format. La seule régression restante est Beethoven 59 pour Zimtohrli.
- Validation sur les 30 extraits : −6 et −9 dB avec la garde, q −6, −9 et −12 (`v4nf_test.csv`).

### Validation sur `test`, 30 extraits (`v4nf_test.csv`), contre la production v3 (`prod2_test.csv`)

Intervalles bootstrap à 95 %. Zimtohrli en écart relatif, plus petit = mieux.

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | Zimtohrli @128 | régressions |
|---|---|---|---|---|---|---|---|---|
| **−6 dB + garde** | **+0,018** [+0,012 ; +0,024] | **+0,013** [+0,006 ; +0,020] | −0,010 [−0,015 ; −0,004] | −0,005 | **+0,017** [+0,007 ; +0,030] | +0,008 | −1,3 % | ODG avancé : 5 extraits vers −0,02 à −0,03 ; Zimtohrli : Brahms +3,0 %, Beethoven 59 +4,5 % |
| **−9 dB + garde** | **+0,013** [+0,009 ; +0,018] | +0,009 [+0,005 ; +0,013] | −0,002 [−0,006 ; +0,003] | −0,001 | +0,011 [+0,003 ; +0,027] | +0,005 | −1,0 % | Beethoven 59 : ViSQOL −0,010, Zimtohrli +6,4 % |

Débit : +0,3 kb/s à q égal (les 3 bits par canal et par trame), compté dans la comparaison.

**La distribution se resserre**, à 128 kb/s :

| | médiane | p10 | p90 | écart type | pire |
|---|---|---|---|---|---|
| production v3 | −0,151 | −0,256 | −0,084 | 0,070 | −0,308 |
| −6 dB + garde | **−0,133** | **−0,225** | −0,072 | **0,063** | **−0,278** |
| −9 dB + garde | −0,141 | −0,228 | −0,081 | 0,062 | −0,272 |

- **Premier changement de format au-dessus du seuil depuis la v3** : ODG +0,013 à +0,018 à 128 kb/s,
  intervalle de confiance entièrement positif, avec ViSQOL dans le même sens. À 160 kb/s, MULE
  passe devant Opus en moyenne (+0,013 contre +0,001).
- **C'est le cœur de la distribution qui bouge**, pas seulement les extrêmes : médiane −0,151 →
  −0,133, p10 −0,256 → −0,225.
- **−6 dB** gagne plus mais PEAQ avancé recule (−0,010, intervalle négatif). **−9 dB** est neutre
  pour PEAQ avancé, avec un peu moins de gain.
- Reste Beethoven 59, que Zimtohrli trouve moins bon (+4,5 à +6,4 %), avec ViSQOL à −0,010 à
  −9 dB. À écouter.
- Coût au décodeur : aucune mémoire en plus ; un tirage du générateur par coefficient nul dans
  les bandes codées au-dessus de 2,8 kHz.

## Couper les aigus, à la raie près, fixe ou trame par trame (`lowpass_12.csv`)

Idée de l'auteur : une coupure calée sur les raies, pas sur les bandes, à la manière d'Apple, pour
concentrer les bits ou éviter du bruit inutile très haut. Encodeur seul, compatible v3 :

- `lp_hz` : coupure fixe, les coefficients au-dessus mis à 0 avant le codage. Les puissances FFT
  de la tonalité ne sont pas touchées ; la première version les coupait aussi, ce qui faisait
  paraître la bande coupée très tonale (+17 % de débit sur Eminem à 16 kHz).
- `lpd` : coupure trame par trame. Dans chaque fenêtre, au-dessus de 11 kHz, tout ce qui est au-delà
  de la dernière raie qui dépasse son masque cible de `lpd_db` dB est mis à 0 dans les deux canaux.

**Le débit libéré est presque nul** à q −7 : coupure fixe à 16 kHz −0,0 à −0,9 % ; coupure
dynamique +0,0 à +0,2 % (les bandes qui deviennent muettes font des sauts de prédiction
d'énergie). Au-dessus de la coupure, MULE ne codait que du bruit de remplissage, qui coûte
quelques bits par bande. Apple, lui, coupait des bandes codées.

12 extraits, 135 kb/s, contre la production :

| | ODG | ODG avancé | ViSQOL | Zimtohrli | pire extrait |
|---|---|---|---|---|---|
| fixe 16 kHz | −0,068 | −0,016 | −0,172 | +19,4 % | Airbourne −0,20 d'ODG, +46 % |
| fixe 18 kHz | +0,000 | +0,002 | −0,044 | +2,5 % | Takemitsu ViSQOL −0,21 |
| dynamique, 0 dB | −0,036 | −0,005 | −0,106 | +17,8 % | Takemitsu +64 % |
| dynamique, +6 dB | −0,045 | −0,011 | −0,121 | +21,9 % | Takemitsu +59 % |

**Rejeté, nettement.** Comme les bandes hautes muettes : les quatre juges sanctionnent la
disparition du bruit des aigus, et la coupure ne libère aucun bit à réemployer. La coupure à
18 kHz est presque neutre pour PEAQ, mais ViSQOL et Zimtohrli la sanctionnent encore. La v4 ne
portera pas de limite de remplissage pour couper ; si elle en porte une, ce sera pour façonner le
bruit. Les options restent dans l'encodeur, désactivées.

## v4, résolution temporelle des aigus : étape 0, le diagnostic (`eval/envelope_diag.py`)

Pour chaque trame longue et chaque bande de MULE à partir de 2,8 kHz, l'enveloppe sur 8
sous-blocs de 2,9 ms, original contre décodé : erreur de forme (rms de l'écart en dB, moyenne
retirée) et aplatissement (écart type de l'enveloppe décodée sur celui de l'original). Cellules
rangées selon la décision de l'encodeur de production (trace, premier canal codé). On ne garde que
les cellules où l'enveloppe originale varie (≥ 1,5 dB) et où la bande compte (moins de 50 dB sous
la plus forte). 10 extraits : pop calme, classique, rock dense, rap. MULE q −7, Opus 128, candidat
v4 (bruit dans les zéros à −6 dB, avec la garde tonale).

| classe de cellule | part | MULE | Opus | v4 candidat |
|---|---|---|---|---|
| bande remplie de bruit (a = 0) | 8,6 % | **2,62 dB, aplatie à 0,56** | 2,06 dB, 0,88 | 2,62 dB, 0,56 |
| bande codée, moins de 50 % de zéros | 87,2 % | 0,61 dB, 0,98 | 0,69 dB, 0,99 | 0,63 dB, 0,97 |
| bande codée, au moins 50 % de zéros | 4,2 % | 1,15 dB, 0,93 | 0,87 dB, 0,97 | 1,18 dB, 0,90 |

Même tableau sur chacun des 10 extraits, sans exception notable.

- **Le bruit de quantification n'est pas en cause.** Dans les bandes codées (87 % des cellules),
  MULE suit l'enveloppe aussi bien qu'Opus, voire mieux (0,61 contre 0,69 dB). C'est pour ça que
  la Haar et le TNS ont si peu rapporté : ils visaient un défaut qui n'existe presque pas. Les
  étapes 1 et 2 du plan sont donc abandonnées.
- **Le défaut est le bruit de remplissage.** Dans les bandes remplies de bruit, l'enveloppe de
  MULE est aplatie de moitié (0,56), celle d'Opus beaucoup moins (0,88). Le bruit de MULE est
  stationnaire sur toute la trame de 46 ms ; Opus remplit ses bandes par recopie d'une bande plus
  grave (*folding*), qui garde la structure temporelle de la trame, sur des trames de 20 ms.
- **Le bruit dans les zéros de la v4 aggrave un peu la troisième classe** (aplatissement 0,93 →
  0,90), comme on le craignait : lui aussi est stationnaire.
- Suite, étape 3 : donner une forme temporelle au bruit. Première variante, sans bit
  supplémentaire : le folding d'Opus pour les bandes à 0 bit (et, en option, pour les zéros
  des bandes codées).

## v4, étape 3 : le folding des bandes à 0 bit (drapeau `MULE_FOLD`)

Prototype paramétrique, pour la recherche de réglages. Avec le drapeau, l'en-tête passe à 24 octets :
- l'octet 22 donne `fold_start`, la première bande concernée ;
- l'octet 23 donne `fold_mix`, de 0 (copie pure) à 8 (bruit pur).

Une bande à 0 bit, à partir de `fold_start`, est remplie à partir des w raies décodées juste en
dessous de chacune de ses raies, dans la même fenêtre (le folding d'Opus). Cette forme et le bruit
du générateur sont normalisés chacun, puis mélangés avec les poids cos et sin de `fold_mix`/8 × 90°.
Le résultat est mis à l'énergie de la bande, comme le bruit actuel. Si les raies du dessous sont
muettes, le bruit pur prend le relais. Tout est en entiers, sans mémoire en plus. L'encodeur
n'écrit que l'en-tête. Sans le drapeau, la sortie v3 est identique (576 encodages). Le test des
drapeaux inconnus passe à 16.

Diagnostic d'enveloppe (Spector, Eminem ; bandes remplies, aplatissement médian) : bruit 0,54 ;
copie pure 0,79 ; `fold_mix` 2 0,73 ; `fold_mix` 4 0,62 ; Opus 0,93. Les bandes codées ne bougent
pas. Mesure à débit égal en cours (`fold_12.csv`).

### Le folding sur 12 extraits (`fold_12.csv`), à 135 kb/s, contre la production v3

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| copie pure (`fd0`) | −0,017 | −0,015 | −0,004 | +2,2 % | 12 |
| `fold_mix` 2 | −0,007 | −0,008 | −0,001 | +0,1 % | 9 |
| `fold_mix` 4 (moitié bruit) | −0,001 | −0,003 | +0,004 | −1,3 % | 2 |
| `fold_mix` 2, à partir de 6 kHz | −0,007 | −0,008 | −0,001 | −0,3 % | 8 |
| `fold_mix` 2 + garde | −0,001 | −0,001 | +0,009 | +1,4 % | 8 |
| `fold_mix` 2 + garde + bruit dans les zéros −6 dB | +0,013 | −0,008 | +0,022 | −3,0 % | 1 |
| rappel : garde + bruit dans les zéros −6 dB | **+0,017** | −0,002 | +0,021 | −2,4 % | 1 |

`fold_mix` 2, extrait par extrait (ODG ; Zimtohrli) : Spector +0,004 ; −11,9 %, Eminem +0,004 ;
−6,1 %, Airbourne +0,010 ; −2,1 % — mais Zombie Zombie −0,030 ; +13,4 %, Takemitsu −0,014 ;
+8,9 %, Mravinsky −0,029, Beethoven 59 +3,6 %.

- **L'enveloppe s'améliore, les juges ne suivent qu'à moitié.** Le folding aide la musique
  percussive (Spector, Eminem), là où l'enveloppe des aigus compte, et dégrade la musique tonale
  (Zombie Zombie, Takemitsu, Mravinsky), dont il recopie des raies dans des aigus qui n'en ont pas.
  Les deux effets s'annulent en moyenne. Plus on mélange de bruit, moins il nuit et moins il aide.
- **Combiné au candidat (garde + bruit dans les zéros), il n'ajoute rien** : ODG +0,013 contre
  +0,017, Zimtohrli un peu mieux (−3,0 contre −2,4 %).
- **Conclusion** : appliqué partout, le folding ne vaut pas. Il faudrait le décider trame par trame,
  ou par groupe de bandes, comme Opus décide de son étalement : copier quand l'enveloppe des aigus
  bouge et que le contenu est bruité, garder le bruit quand le contenu est tonal. Ça demande un bit
  de signalisation et un critère dans l'encodeur, que celui-ci peut calculer sur le signal original.

### Le folding décidé trame par trame (`folddyn_12.csv`), 12 extraits, 135 kb/s, contre la production v3

Un bit par canal et par trame (bit 4 de l'octet 23 de l'en-tête). Chaque bande à 0 bit vote, avec
son énergie, pour la copie si la bande de dessous (sa source) est plate au-delà de
−`fold_ton_db` dB, sinon pour le bruit ; la majorité décide. Diagnostic d'enveloppe : la décision
copie presque toujours sur Spector et Eminem, nettement moins sur Zombie Zombie.

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| folding partout, `fold_mix` 2 (rappel) | −0,007 | −0,008 | −0,001 | +0,1 % | 9 |
| décidé, copie pure | −0,008 | −0,008 | −0,002 | +0,4 % | 12 |
| décidé, `fold_mix` 2, seuil 8 dB | −0,004 | −0,005 | +0,002 | −0,6 % | 6 |
| **décidé, `fold_mix` 2, seuil 5 dB** | −0,003 | −0,003 | +0,004 | −1,1 % | 3 |
| décidé, seuil 12 dB | −0,006 | −0,007 | −0,000 | −0,0 % | 8 |
| décidé (8 dB) + garde + bruit dans les zéros −6 dB | +0,014 | −0,006 | +0,022 | **−3,5 %** | 1 |
| rappel : garde + bruit dans les zéros −6 dB | **+0,017** | −0,002 | +0,021 | −2,4 % | 1 |

Au seuil de 5 dB, Zimtohrli extrait par extrait : Spector −11,5 %, Eminem −5,6 %, Classical −2,4 %,
Airbourne −1,7 % ; mais Takemitsu +4,4 %, Beethoven 59 +3,9 %, Zombie Zombie +2,1 % (+13,4 % sans
décision).

- **La décision réduit nettement les dégâts** (Zombie Zombie +13 % → +2 %) et garde le gain sur la
  musique percussive (Spector −12 %, Eminem −6 %). Plus le seuil est strict, mieux c'est.
- **Mais PEAQ ne suit toujours pas** : l'ODG reste légèrement négatif (−0,003) et le classique
  calme perd encore un peu (Takemitsu, Beethoven 59, Mravinsky). Combiné au candidat v4, le folding
  échange un peu de PEAQ (+0,017 → +0,014) contre un peu de Zimtohrli (−2,4 → −3,5 %).
- **Pas de gain net pour l'instant.** Le folding reste en option sur la branche. Pistes s'il fallait
  insister : un critère qui regarde aussi la variation de l'enveloppe de la cible (ne copier que
  dans les trames où les aigus bougent), ou un étalement à la manière d'Opus pour casser la
  structure tonale recopiée.

### Pourquoi le folding marche chez Opus et pas chez MULE : deux vérifications

Mêmes cellules (classes de la production), 10 extraits, aplatissement médian des bandes remplies
de bruit :

| | erreur de forme | aplatissement |
|---|---|---|
| MULE, bruit | 2,62 dB | 0,56 |
| MULE, ces bandes codées à l'allocation 1 (`code12`, `code16`) | **5,0 dB** | **1,2** |
| Opus 128 | 2,06 dB | 0,88 |
| Opus 96 | 2,33 dB | 0,87 |
| Opus 64 | 2,50 dB | 0,83 |

- **Hypothèse réfutée : Opus garde l'enveloppe même à bas débit.** À 64 kb/s, où il code beaucoup
  moins de bandes et s'appuie davantage sur le folding, l'aplatissement ne passe que de 0,88 à
  0,83. Son remplissage préserve vraiment l'enveloppe ; ce n'était pas seulement du codage.
- **Chez MULE, coder un peu est pire que remplir de bruit.** À l'allocation 1, une bande ne garde
  que quelques raies isolées : l'enveloppe devient exagérée (1,2) et l'erreur double (5,0 dB). Le
  débit ne bouge presque pas (127,5 → 127,8 kb/s) : ces bandes sont presque entièrement à zéro.
  C'est le défaut de la garde tonale seule, en grand.
- **Ce qui manque à MULE, c'est l'étalement d'Opus.** Opus ne laisse jamais une bande peu codée,
  ou recopiée, sous forme de quelques raies isolées : sa rotation redistribue l'énergie sur la
  bande, avec un niveau choisi par trame selon que le contenu est tonal ou bruité. Ajoutons ses
  trames de 20 ms. MULE n'a que trois remplissages possibles : bruit plat (enveloppe aplatie),
  copie (raies recopiées), ou raies isolées (enveloppe exagérée). Le bruit dans les zéros de la
  v4 est un premier pas vers l'étalement : il comble les trous des bandes codées.

## v4 : la rotation des bandes peu codées, à la manière de l'étalement d'Opus (drapeau `MULE_ROT`)

Prototype paramétrique ; avec le drapeau, l'en-tête passe à 28 octets :
- octet 24 : l'angle à l'allocation 1 (`rot_deg`, en degrés), divisé par 2 toutes les 2 allocations ;
- octet 25 : la dernière allocation tournée (`rot_amax`) ;
- octet 26 : la première bande tournée (`rot_b0`) ;
- octet 27, bit 0 : un niveau d'étalement de 2 bits par canal et par trame (`rot_dyn`) — 0 aucun,
  1 à 3 pour 0,5, 1 et 1,5 fois l'angle ; sans ce bit, le niveau est toujours 1.

**Au décodeur**, après la lecture des niveaux d'une bande codée, les valeurs (Q24) de chaque
fenêtre de la bande sont tournées comme dans CELT (`exp_rotation1`) : une passe montante puis
une passe descendante entre voisins, puis, à partir de 8 raies, une passe entre raies distantes
d'environ √n. Les cosinus et sinus Q15 sont calculés une fois à l'initialisation ; le décodeur
du baladeur, en entiers seulement, devra les tabuler.

**À l'encodeur**, l'inverse exact est appliqué aux cibles avant le treillis (`band_prep`) :
les passes en ordre inverse, chacune parcourue à l'envers, avec −s. Le bruit débit-distorsion est
mesuré dans le domaine tourné, ce que la rotation, orthogonale, autorise. L'angle dépend de
l'allocation, connue avant la quantification. Le niveau par trame, s'il est actif, est décidé
avant le codage, d'après la planéité des bandes (comme la décision d'étalement d'Opus).

**Vérifications.**
- Sans le drapeau, la sortie v3 est identique au bit près.
- Avec rotation, le rapport signal sur bruit ne bouge pas (Spector 19,37 → 19,38 dB, Takemitsu
  24,56 dB) : l'inverse est exact.
- La rotation touche 8 à 16 % des bandes codées au-dessus de 2,8 kHz jusqu'à l'allocation 4, et
  20 à 29 % jusqu'à l'allocation 6. Le signal décodé change d'environ −19 dB.
- Mesure à débit égal de R0 à R2 en cours (`rot_12.csv`).

### Rotation, R0 à R2 sur 12 extraits (`rot_12.csv`), à 135 kb/s, contre la production v3

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| R0, 20° | +0,002 | +0,001 | −0,001 | +0,0 % | 0 |
| R0, 40° | +0,003 | +0,001 | −0,001 | +0,6 % | 1 |
| R0, 60° | +0,002 | −0,000 | −0,002 | +0,2 % | 1 |
| R0, 40° jusqu'à l'allocation 6 | +0,003 | −0,001 | −0,002 | +0,7 % | 1 |
| R1, 40°, niveau par trame | +0,001 | −0,002 | −0,001 | +0,8 % | 1 |
| R1, 60° | +0,001 | −0,003 | −0,002 | +0,5 % | 1 |
| R2, R1 + garde | +0,002 | +0,002 | −0,006 | **+4,1 %** | 8 |
| R2, R1 + garde + bruit dans les zéros −6 dB | +0,013 | −0,006 | +0,005 | −0,8 % | 4 |
| rappel : garde + bruit dans les zéros −6 dB | **+0,017** | −0,002 | **+0,021** | **−2,4 %** | 1 |

Diagnostic d'enveloppe : aucun changement (bandes codées avec beaucoup de zéros : 1,24 → 1,24 à
1,26 dB). La rotation mélange des raies voisines en fréquence ; elle change la texture spectrale
(plus de raies isolées), pas la répartition dans le temps à l'intérieur de la trame.

- **Seule, la rotation est neutre** : ODG +0,002 à +0,003, les autres juges à zéro ou un peu en
  dessous. La décision par trame n'y change rien.
- **Avec la garde tonale, elle nuit** (Zimtohrli +4,1 %, 8 régressions) : elle étale la raie que la
  garde vient de coder. Le décodeur ne sait pas distinguer une bande gardée d'une autre bande à
  l'allocation 1.
- **Elle n'ajoute rien au candidat v4** et lui retire une partie de son gain (ViSQOL +0,021 →
  +0,005, Zimtohrli −2,4 → −0,8 %). Le bruit dans les zéros remplit déjà les trous que la rotation
  devait combler, sans étaler les raies.
- **R3 (validation sur 30 extraits) n'est pas lancée** : aucun réglage ne bat la référence sur les
  12 extraits. La rotation reste en option sur la branche, désactivée.
- Pourquoi elle sert à Opus et pas à MULE : chez Opus, la forme d'une bande est normalisée et codée
  par quelques impulsions, qui laissent la bande presque vide sans étalement. Chez MULE, le
  treillis code les coefficients eux-mêmes ; avec le bruit dans les zéros, les trous sont déjà
  comblés.

## v4 : réévaluation de la combinaison TNS, recette d'Apple, coder plutôt que remplir

### Ce que fait Apple : lecture des facteurs d'échelle et du TNS (`eval/aac_frames.py`)

Le lecteur décode maintenant le Huffman des facteurs d'échelle (table 4.A.1 de la norme, reprise
de `libavcodec/aactab.c`) pour atteindre les drapeaux d'impulsions et de TNS du premier canal,
puis les filtres TNS (fenêtre, longueur, ordre).

| extrait | blocs courts Apple / FDK / MULE | TNS, trames longues : Apple / FDK | TNS, trames courtes : Apple / FDK |
|---|---|---|---|
| Spector | **16,9** / 2,0 / 4,3 % | 1,3 / 13,1 % | 15,5 / 69,2 % |
| Eminem | **20,2** / 6,8 / 13,0 % | 3,7 / 14,6 % | 48,1 / 88,6 % |
| Salut c'est cool | 7,2 / 5,2 / 8,0 % | 2,2 / 7,2 % | 59,6 / 82,4 % |
| Lebanon Hanover | 17,7 / 10,2 / 19,5 % | 0,7 / 6,2 % | 46,1 / 92,4 % |
| Max Richter, Takemitsu | < 1 % | 0,2 à 0,3 % | – |

Apple n'utilise presque pas le TNS sur ses trames longues. Sa recette pour l'enveloppe des aigus
tient en deux points : beaucoup plus de blocs courts sur la musique percussive (Spector : 4 fois
plus que MULE), et des bandes codées plutôt que remplies (sous 16 kHz, presque aucune bande à
zéro). Le détecteur d'attaques de MULE réagit aux montées d'énergie au-dessus de 3 kHz : il ne
voit pas les charlestons et les sifflantes, qui font varier l'enveloppe des aigus sans former
d'attaque franche.

### Coder plutôt que remplir (`code12a2nf`, `code12a3nf`, `code16a3nf`)

On force à l'allocation 2 ou 3 les bandes hautes à 0 bit, avec le bruit dans les zéros à −6 dB.
Aplatissement des bandes concernées (6 extraits) : 0,55 → 0,58 à 0,60. Une bande faible reste
surtout faite de zéros. Sans bruit dans les zéros, elle se réduit à des raies isolées (enveloppe
exagérée, 1,2 avec `code12`) ; avec, le bruit stationnaire domine (enveloppe plate). Il faudrait
beaucoup plus de bits pour qu'elle suive le signal. **Écarté.**

### Le TNS sur le bruit (drapeau `MULE_TNF`)

Avec le drapeau, l'en-tête passe à 30 octets (octet 28 : première bande).

**À l'encodeur**, pour chaque trame longue et chaque canal :
- un modèle tout-pôle le long des fréquences, calculé sur le vecteur codé au-dessus de la bande
  `tnf_b0` (autocorrélation avec fenêtre de retard, puis Levinson) ;
- transmis si son gain de prédiction atteint `tnf_gain_db` : 1 bit, l'ordre moins 1 sur 3 bits,
  puis chaque coefficient de réflexion sur 4 bits (sin(i·π/16), comme l'essai du commit 4b5bc50).

**Au décodeur** : le bruit des bandes à 0 bit passe dans 1/A(z) le long des fréquences, puis
chaque bande est remise à son énergie d'origine. Les bandes codées ne sont pas touchées.

**Vérifications.** La sortie v3 est identique au bit près, le rapport signal sur bruit ne bouge
pas, et les 42 tests passent.

**Aplatissement des bandes remplies.**
- Au seuil de 1,5 dB, le filtre est rarement envoyé : 0,55 → 0,58.
- **Forcé (seuil 0) : 0,54 → 0,80**, et **0,83 à partir de 6 kHz** (Opus 0,92). L'erreur de forme
  baisse un peu (2,87 → 2,65 dB). Le filtre a le bon sens.
- Mesure à débit égal en cours (`tnf_12.csv`).

### Le TNS sur le bruit, à débit égal (`tnf_12.csv`), 12 extraits, 135 kb/s, contre la production v3

| variante | débit à q égal | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|---|
| ordre 8, forcé, dès 2,8 kHz | +1,4 % | −0,011 | −0,016 | −0,003 | +4,0 % | 15 |
| ordre 8, forcé, dès 6 kHz | +1,2 % | −0,008 | −0,012 | −0,001 | +2,0 % | 7 |
| ordre 4, forcé, dès 6 kHz | +0,7 % | −0,004 | −0,007 | −0,000 | +0,6 % | 1 |
| ordre 8, dès 6 kHz + garde + bruit dans les zéros | +1,4 % | +0,010 | −0,014 | +0,021 | −0,7 % | 11 |
| ordre 4, dès 6 kHz + garde + bruit dans les zéros | +0,9 % | +0,013 | −0,008 | +0,022 | −2,1 % | 4 |
| rappel : garde + bruit dans les zéros | +0,3 % | **+0,017** | −0,002 | +0,021 | **−2,4 %** | 1 |

Ordre 4, Zimtohrli par extrait : Spector −10,8 %, Eminem −4,5 % ; tous les autres +0,3 à +5,9 %.

- **Même profil que le folding.** L'enveloppe s'améliore nettement (0,54 → 0,83), mais seule la
  musique percussive en profite (Spector, Eminem) ; ailleurs, le gain d'enveloppe ne vaut pas les
  bits qu'il coûte (0,7 à 1,4 % de débit) ni la forme imposée au bruit. Avec le candidat v4, il
  n'ajoute rien.
- **Bilan de l'axe « résolution temporelle des aigus ».** Le défaut est réel et localisé (le bruit
  de remplissage, stationnaire sur 46 ms), et deux outils savent le corriger : le folding décidé
  par trame, le TNS sur le bruit. Mais les juges ne le récompensent que sur la pop percussive, et
  le font payer ailleurs. Ce n'est pas le levier principal de l'écart avec Opus. Les options
  restent sur la branche, désactivées.
- Piste restante, encodeur seul, inspirée d'Apple : un détecteur de blocs courts qui réagit aussi à
  la variation de l'enveloppe des aigus (Spector : Apple 17 % de blocs courts, MULE 4 %).

## Le spectrogramme d'ABBA (observation de l'auteur : résolution perdue et blancs vers 13 et 17 kHz)

Extrait `abba` (EBU SQAM), MULE q −7, candidat v4 (garde + bruit dans les zéros −6 dB), Opus 128.
L'original porte une raie continue à **15,7 kHz** (sans doute un sifflement de ligne vidéo,
15 734 Hz), au milieu de la bande 20 de MULE (13,4-17,2 kHz).

Décisions de MULE (premier canal) : bande 20 remplie de bruit dans 68 % des trames, codée dans
32 % (allocation médiane 5, 65 % de zéros) ; bande 21 (17,2-19,9 kHz) toujours remplie de bruit.

| 12-20 kHz, cellules STFT (23 ms × 43 Hz) | kb/s | trous (> 10 dB sous l'original) | excès (> 10 dB au-dessus) |
|---|---|---|---|
| MULE v3 | 119,3 | 10,1 % | 11,9 % |
| MULE candidat v4 | 119,9 | 9,0 % | **6,3 %** |
| Opus 128 | 150,7 | 5,1 % | 6,6 % |

- Ce que l'auteur voit est le défaut déjà identifié sur Takemitsu, en plus visible :
  - pendant les 8 premières secondes, la raie disparaît, remplacée par un pavé de bruit plat sur
    toute la bande 20 : la « perte de résolution » et la marche à 13,4 et 17,2 kHz ;
  - de 9 à 12 s, la bande est codée avec beaucoup de zéros, qui font des blancs verticaux.
- **Le candidat v4 corrige l'essentiel** : la raie revient et le pavé de bruit disparaît (excès
  11,9 → 6,3 %, au niveau d'Opus). La raie reste en pointillé : la garde ne se déclenche que dans
  les trames où le critère de crête passe. Opus aussi la rend en pointillé.
- Les trous restent plus nombreux que chez Opus (9,0 contre 5,1 %), et Opus dépense 26 % de bits
  de plus sur cet extrait.

### Le spectrogramme des castagnettes

Extrait `castanets` (EBU SQAM) : 16 % de blocs courts. Bandes 19 et 20 codées dans 79 et 59 %
des trames, avec 57 et 61 % de zéros ; bande 21 toujours remplie de bruit.

| 12-20 kHz | kb/s | trous (> 10 dB sous l'original) | excès |
|---|---|---|---|
| MULE v3 | 109,7 | 12,6 % | 4,6 % |
| MULE candidat v4 | 110,0 | **7,8 %** | 5,0 % |
| Opus 128 | 131,5 | 12,1 % | 4,1 % |

- Les « blancs » sont ici les zéros des bandes codées : des taches noires entre les coups de
  castagnettes, vers 10-13 et 15-17 kHz. Ce sont du vrai silence dans une bande codée avec une
  allocation moyenne.
- **Le bruit dans les zéros les comble** : trous 12,6 → 7,8 %, moins qu'Opus (12,1 %), pour
  0,3 kb/s.
- MULE coupe à 19,98 kHz alors que l'original monte à 22 kHz : c'est la bande passante, le piège
  des 20 kHz, laissé de côté.

## Hypothèse : un manque de bits entre 11 et 16 kHz (`hibits_12.csv`)

Option `hi_db` : une marge de masquage supplémentaire (plus de bits) à partir de la bande `hi_b0`.
12 extraits, 135 kb/s, à débit égal contre la production :

| variante | débit à q égal | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|---|
| +3 dB dès 10,3 kHz (`hi3`) | +5 % | −0,010 | −0,018 | −0,000 | +7,4 % | 22 |
| +6 dB dès 10,3 kHz (`hi6`) | +11 % | −0,034 | −0,040 | −0,002 | +17,6 % | 29 |
| +6 dB dès 8,3 kHz (`hi6b18`) | +17 % | −0,043 | −0,044 | −0,001 | +21,0 % | 31 |
| `mid_db` 4 dB jusqu'à la bande 21 (`midhi22`) | +14 % | −0,018 | −0,016 | −0,001 | +16,1 % | 25 |

**Hypothèse réfutée, nettement.** Prendre des bits au reste du spectre pour les donner aux aigus
dégrade presque tous les extraits, et Zimtohrli le plus fortement (+7 à +21 %). Seuls quelques
morceaux denses gagnent un peu en ODG à +3 dB (Airbourne +0,031, Eminem +0,021, Spector +0,016).
La répartition actuelle des bits entre aigus et reste du spectre est la bonne pour les juges. Les
défauts visibles au spectrogramme (pavés de bruit, trous) ne valent pas des bits pris ailleurs ;
le candidat v4 les corrige pour 0,3 kb/s. Option laissée dans l'encodeur, désactivée.

## Les spectrogrammes vers 160 kb/s (MULE q −10, Opus 160, Apple q82)

Fichiers et images : `eval/spectro_compare.py`, quatre extraits (ABBA, castagnettes, Takemitsu,
Spector).

- **Takemitsu est le cas le plus parlant.** L'original porte tout un peigne de raies entre 14 et
  20 kHz.
  - **MULE v3** : la bande 21 (17,2-20 kHz) est remplie de bruit plat dans toutes les trames, même
    à 160 kb/s, et les raies y disparaissent. La bande 20 est codée avec beaucoup de trous.
  - **Candidat v4** : il restaure les raies de la bande 20, mais pas celles de la bande 21. La garde
    tonale ne vise qu'une raie isolée : un peigne de raies n'a pas de crête assez marquée pour la
    déclencher.
  - **Opus** garde les raies dans les deux bandes. **Apple** les garde jusque vers 17,5 kHz, met à
    zéro tout ce qui est entre elles, et coupe au-dessus.
- **ABBA** : à 160 kb/s, la bande 20 de MULE v3 est codée, avec des trous en bandes verticales ;
  le candidat v4 les comble. Apple garde la raie à 15,7 kHz intacte, au prix de zéros partout
  autour.
- La bande 21 n'est jamais codée par MULE sur ces extraits : son modèle la juge sous le seuil
  absolu d'audition (élevé à 17-20 kHz). Opus, qui n'a pas de masque, la code.

## Hypothèse : des bandes plus étroites dans les aigus (24 bandes)

Variante de compilation `MULE_BANDS24`, dans un répertoire séparé (`make BUILD=build-nb24
CFLAGS="... -DMULE_BANDS24"`, puis `MULE_BUILD=build-nb24`) : la bande 20 est coupée à 15,3 kHz
et la bande 21 à 18,6 kHz. La table des bornes de bandes est désormais mise en commun dans
`mule.h` (`MULE_EDGES_INIT`). Les contextes du codage entropique ne changent pas : les nouvelles
bandes restent dans la classe 2. L'en-tête annonce 24 bandes, et l'aller-retour est cohérent. À q
égal, le débit varie de −4,4 % (Spector) à +0,6 % (Takemitsu). Mesure à débit égal en cours
(`nb24_12.csv`).

### 24 bandes, à débit égal (`nb24_12.csv`), 12 extraits, 135 kb/s, contre la production v3 (22 bandes)

| variante | débit à q égal | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|---|
| 24 bandes | −3 % | −0,029 | −0,027 | **+0,021** | **−5,5 %** | 18 |
| 24 bandes + garde + bruit dans les zéros | −2,8 % | −0,007 | −0,026 | **+0,032** | **−7,6 %** | 15 |
| rappel : 22 bandes + garde + bruit dans les zéros | +0,3 % | **+0,017** | −0,002 | +0,021 | −2,4 % | 1 |

24 bandes + garde + bruit dans les zéros, par extrait :

| | ODG | ViSQOL | Zimtohrli |
|---|---|---|---|
| Takemitsu | +0,053 | +0,217 | **−35,7 %** |
| Mravinsky | +0,062 | +0,078 | −19,6 % |
| Zombie Zombie | +0,036 | +0,053 | −14,7 % |
| Max Richter | +0,037 | +0,131 | −11,9 % |
| Beethoven 59 | +0,023 | +0,046 | −8,5 % |
| Belenos | **−0,200** | **−0,158** | **+15,7 %** |
| Salut c'est cool, Classical, Lebanon Hanover | −0,014 à −0,034 | ≈ 0 | −6 à +3 % |

- **Sur la musique tonale, c'est le plus gros gain mesuré depuis le début** : ViSQOL et Zimtohrli
  progressent fortement (Takemitsu −36 %, Mravinsky −20 %). Les raies des bandes hautes y sont
  enfin codées.
- **Mais PEAQ recule, et Belenos s'effondre** (−0,20 d'ODG). À q égal, les 24 bandes **retirent
  des bits** aux aigus du rock dense : Belenos passe de 149 à 136 kb/s (−9 %), Airbourne −5 %. Le
  seuil absolu de chaque demi-bande est pris à son point le plus sensible, donc plus haut dans la
  demi-bande supérieure, et le masque y monte. Même à son propre débit, Belenos reste moins bon
  (environ −0,1 d'ODG à 162 kb/s), et il est très sensible au débit.
- **Deux effets sont mêlés** : la résolution (le bon) et un changement de répartition des bits dû
  au seuil absolu par demi-bande (le mauvais). Suite : séparer les deux, en gardant le seuil absolu
  de la bande d'origine pour ses deux moitiés, et essayer la coupe de la seule bande 20 ou de la
  seule bande 21.

### Les seuils : le seuil absolu de la bande d'origine (`ath_parent`), et une seule bande coupée

`ath_parent` : chaque bande coupée garde le seuil absolu par coefficient de sa bande v3, c'est-à-dire
son point le plus sensible **et** sa largeur. Le seuil par coefficient est divisé par la largeur de
la bande, et une demi-bande avait donc un seuil 3 dB plus haut. Variantes de compilation :
`MULE_SPLIT` 1 (bande 20 seule, 23 bandes, `build-s20`), 2 (bande 21 seule, `build-s21`), 3 (les
deux, 24 bandes). Sans coupe, l'option ne change rien (production identique au bit près).

12 extraits, 135 kb/s, à débit égal contre la production v3 (`nb24ap_12.csv`, `s20_12.csv`,
`s21_12.csv`) :

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions | Belenos, ODG | Takemitsu, Zimtohrli |
|---|---|---|---|---|---|---|---|
| 24 bandes, seuil par demi-bande | −0,029 | −0,027 | +0,021 | −5,5 % | 18 | −0,232 | −30,7 % |
| 24 bandes, seuil d'origine | −0,007 | −0,000 | +0,040 | −6,2 % | 9 | −0,009 | −26,6 % |
| bande 20 coupée, seuil d'origine | −0,005 | +0,003 | +0,025 | −6,1 % | 7 | −0,002 | −27,4 % |
| bande 21 coupée, seuil d'origine | −0,002 | −0,005 | +0,014 | +0,4 % | 2 | −0,002 | +2,4 % |
| 24 bandes, seuil d'origine + garde + bruit dans les zéros | +0,011 | −0,007 | **+0,050** | −8,4 % | 8 | −0,003 | −37,4 % |
| **bande 20 coupée, seuil d'origine + garde + bruit dans les zéros** | **+0,013** | −0,003 | +0,034 | **−8,3 %** | 6 | −0,003 | **−38,2 %** |
| bande 21 coupée, seuil d'origine + garde + bruit dans les zéros | +0,016 | −0,006 | +0,036 | −2,1 % | 5 | +0,018 | −20,5 % |
| rappel : 22 bandes + garde + bruit dans les zéros | +0,017 | −0,002 | +0,021 | −2,4 % | 1 | +0,017 | −23,5 % |

- **Le seuil d'origine supprime l'effet indésirable** : Belenos passe de −0,23 à −0,01, et PEAQ
  avancé revient à zéro. C'était bien le seuil absolu par demi-bande qui retirait des bits au rock.
- **La coupe de la bande 20 porte l'essentiel du gain.** Celle de la bande 21 n'apporte presque rien
  à Zimtohrli : au-dessus de 17 kHz, le seuil absolu reste trop haut pour que les raies soient
  codées.
- **Bande 20 coupée + candidat v4, contre le candidat v4 seul** : Zimtohrli −8,3 % contre −2,4 %,
  ViSQOL +0,034 contre +0,021, mais ODG +0,013 contre +0,017, et 6 régressions contre 1. Extrait
  par extrait :
  - la musique tonale progresse nettement (Zimtohrli : Takemitsu −38 %, Mravinsky −17 %, Zombie
    Zombie −14 %, Belenos −8 %, Classical −7 %), et Beethoven 59 passe de +4,2 à −5,5 % ;
  - le rock et la pop perdent un peu en PEAQ avancé (Lebanon Hanover −0,052, Spector −0,038,
    Eminem −0,035, Airbourne −0,027), et en ODG sur Airbourne et Salut c'est cool (−0,02).
- Suite : valider la coupe de la bande 20 avec le candidat v4 sur les 30 extraits.

### Validation sur `test` : bande 20 coupée (seuil d'origine) + candidat v4 (`s20v4_test.csv`)

Intervalles bootstrap à 95 %. Zimtohrli en écart relatif, plus petit = mieux.

| | ODG @128 | @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | Zimtohrli @128 | @160 |
|---|---|---|---|---|---|---|---|---|
| candidat v4 (22 bandes), contre v3 | **+0,018** [+0,012 ; +0,025] | **+0,013** | −0,010 | −0,005 | +0,017 | +0,008 | −1,3 % | −0,2 % |
| bande 20 coupée + v4, contre v3 | +0,009 [−0,001 ; +0,019] | −0,008 | −0,015 | −0,006 | **+0,023** | +0,011 | **−6,5 %** [−9,6 ; −4,0] | **−5,8 %** |
| bande 20 coupée + v4, contre v4 | −0,009 [−0,016 ; −0,002] | **−0,021** [−0,032 ; −0,010] | −0,005 | −0,001 | +0,006 | +0,003 | **−5,4 %** [−6,9 ; −4,0] | **−5,7 %** |

Distribution de l'ODG à 128 kb/s : médiane / p10 / écart type / pire.
- v3 : −0,151 / −0,256 / 0,070 / −0,308
- v4 : **−0,133** / −0,225 / 0,063 / −0,278
- bande 20 coupée + v4 : −0,146 / **−0,208** / **0,054** / −0,288

- **Les juges se contredisent.** Zimtohrli donne un gain net et sûr à la coupe de la bande 20 (−5,4 à
  −5,7 % de mieux que le candidat v4, sans aucune régression), ViSQOL un petit gain. PEAQ la
  sanctionne, surtout à 160 kb/s (−0,021 d'ODG contre le candidat v4), avec 17 extraits de rock et de
  pop en recul de 0,02 à 0,08 (New Order −0,069, Red Fang −0,075, Judas Priest −0,064).
- **La distribution se resserre encore** (écart type 0,054, p10 −0,208), mais la médiane recule par
  rapport au candidat v4.
- Selon la règle du projet (des juges en désaccord, donc l'écoute tranche), la coupe de la bande 20
  n'est pas adoptée sur les mesures seules. Le candidat v4 à 22 bandes reste le seul où tous les
  juges vont dans le même sens. Écoute à prévoir : un rock à 160 kb/s (Red Fang ou New Order), où
  PEAQ la sanctionne, et Takemitsu à 128 kb/s, où Zimtohrli la récompense le plus.

## Spectrogrammes à débit égal par extrait (cible : le débit d'Apple q63 sur chaque extrait)

L'auteur remarque que les comparaisons à réglage fixe désavantagent MULE sur les extraits calmes :
à q −7, Takemitsu reçoit 105 kb/s contre 125 pour Opus et 122 pour Apple. Les notes globales,
interpolées au même débit moyen sur 30 extraits, restent équitables : elles mesurent aussi la
répartition des bits entre extraits, choix propre à chaque codec. Pour les comparaisons visuelles,
chaque codec est donc réglé sur le débit d'Apple, extrait par extrait (dichotomie sur q pour MULE,
sur le débit nominal pour Opus, à 0,6 kb/s près). Fichiers : `scratchpad/eq_wav/`.

**Observation de l'auteur** : les écarts d'Apple sont presque toujours négatifs (il retire, il
n'ajoute pas), alors que MULE « bave » sur les fréquences voisines. Mesure, 8-20 kHz, cellules STFT
à moins de 60 dB du maximum, moyenne sur 6 extraits :

| | énergie ajoutée (> +6 dB) | énergie retirée (< −6 dB) | bilan d'énergie 8-20 kHz |
|---|---|---|---|
| MULE v3 | 9,2 % | 11,6 % | −0,4 dB |
| MULE v4 | 9,0 % | 10,9 % | −0,4 dB |
| MULE v4, bande 20 coupée | 9,4 % | 11,6 % | −0,4 dB |
| Opus | 10,6 % | 10,5 % | +0,1 dB |
| Apple AAC | **4,2 %** | **31,4 %** | **−1,0 dB** |

- **Confirmé : Apple ne fait presque que retirer.** C'est la logique d'AAC-LC : pas de remplissage
  de bruit (une bande à zéro est muette), et une quantification dont l'arrondi tire les valeurs vers
  zéro. Ses erreurs sont d'un seul signe, et il perd de l'énergie (−1,0 dB, −4,6 dB sur Takemitsu).
- **MULE ne bave pas plus qu'Opus.** Tous deux conservent l'énergie de chaque bande, transmise à
  part, et répartissent leurs erreurs des deux côtés. Leur « bavure » vient du remplissage :
  l'énergie d'une raie non codée est étalée sur toute la bande. C'est le plus visible sur Takemitsu
  (18 % de cellules ajoutées) : le bruit plat de la bande 21 remplit les creux entre les raies du
  peigne.
- Ce sont deux philosophies d'erreur : AAC laisse des trous, MULE et Opus mettent du bruit à la
  bonne énergie. Les juges ont jusqu'ici préféré le bruit (couper ou rendre muet les aigus a toujours
  été sanctionné). Mais, sur les raies, la précision d'AAC est meilleure.

## Le coût réel d'une bande de plus

Coût de l'information auxiliaire (énergies, allocations, mode et échappements d'allocation), compté
comme le codec le code : modèles adaptatifs, distributions initiales apprises, remises à zéro aux
paquets clés. 22 bandes contre 23 (bande 20 coupée, seuil d'origine), même q (−7), 10 extraits.

| extrait | bits de plus par canal, trame et groupe | dont énergie | dont allocation | kb/s de plus |
|---|---|---|---|---|
| Takemitsu, Max Richter, Mravinsky | 2,4 à 2,8 | 2,0 à 2,2 | 0,4 à 0,6 | 0,21 à 0,24 |
| ABBA, castagnettes, Eminem, Airbourne | 5,0 à 5,3 | 2,5 à 3,5 | 1,9 à 2,6 | 0,44 à 0,59 |
| Spector, Lebanon Hanover, Belenos | 5,7 à 7,2 | 3,1 à 3,7 | 2,7 à 3,5 | 0,50 à 0,64 |
| **moyenne** | **4,75** | | | **0,45 (0,35 % à 128 kb/s)** |

- Une bande de plus coûte environ 2 à 3,5 bits d'énergie, plus une allocation presque gratuite si
  la bande reste à 0 bit (musique calme) et de 2 à 3,5 bits si elle est codée (rock). C'est 2 à
  5 fois plus que chez AAC (environ 1 bit par facteur d'échelle quand il bouge peu), mais 0,45 kb/s
  en moyenne seulement.
- **Ce coût n'explique pas le recul de PEAQ sur le rock.** À q égal, la coupe fait surtout baisser
  les bits des **coefficients** sur le rock : Spector 124,0 → 117,8 kb/s, Airbourne 131,9 → 124,5,
  Belenos 145,1 → 138,3, alors que la musique calme ne bouge pas. Même avec le seuil absolu
  d'origine, les deux demi-bandes reçoivent moins de bits que la bande entière : la planéité et
  l'étalement du masquage, calculés sur des bandes plus étroites, relèvent leurs masques. C'est une
  nouvelle répartition des bits, que la comparaison à débit égal ne compense qu'en moyenne.

### 24 bandes, frontières déplacées (`s4_12.csv`, `s5_12.csv`), 12 extraits, 135 kb/s, contre la production v3

- **A** (`MULE_SPLIT` 4) : les bandes 19 et 20 coupées en deux (10,3 / 11,9 / 13,4 / 15,3 / 17,2 / 20 kHz).
- **B** (`MULE_SPLIT` 5) : cinq bandes régulières d'environ 1,9 kHz (10,3 / 12,2 / 14,1 / 16,0 / 17,9 / 20 kHz).

Toutes avec le seuil absolu d'origine (`ath_parent`).

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions | ODG rock (6) | ODG tonal (6) |
|---|---|---|---|---|---|---|---|
| A seule | −0,003 | +0,012 | +0,022 | −6,4 % | 7 | −0,023 | +0,017 |
| B seule | −0,006 | +0,011 | +0,033 | −4,3 % | 9 | −0,027 | +0,016 |
| bande 20 coupée seule | −0,005 | +0,003 | +0,025 | −6,1 % | 7 | −0,025 | +0,016 |
| bandes 20 et 21 coupées | −0,007 | −0,000 | +0,040 | −6,2 % | 9 | −0,030 | +0,015 |
| **A + candidat v4** | **+0,016** | **+0,006** | +0,033 | **−9,9 %** | **4** | −0,006 | **+0,039** |
| B + candidat v4 | +0,012 | +0,005 | +0,041 | −9,1 % | 7 | −0,009 | +0,033 |
| bande 20 coupée + v4 | +0,013 | −0,003 | +0,034 | −8,3 % | 6 | −0,009 | +0,035 |
| bandes 20 et 21 coupées + v4 | +0,011 | −0,007 | +0,050 | −8,4 % | 8 | −0,012 | +0,035 |
| candidat v4 (22 bandes) | +0,017 | −0,002 | +0,021 | −2,4 % | 1 | +0,012 | +0,023 |

- **A + candidat v4 est le meilleur compromis mesuré.** Les quatre juges sont positifs : l'ODG est
  au niveau du candidat v4 (+0,016 contre +0,017), PEAQ avancé passe de −0,002 à +0,006, ViSQOL
  +0,033, et Zimtohrli −9,9 %, le meilleur chiffre de toute l'étude. Il y a 4 régressions. Le rock
  ne perd presque plus rien (−0,006), et la musique tonale gagne +0,039.
- Couper la bande 19 (10,3-13,4 kHz) plutôt que la bande 21 est le bon choix : au-dessus de
  17 kHz, le seuil absolu empêche de toute façon les raies d'être codées.
- Suite : valider A + candidat v4 sur les 30 extraits.

### Validation de « A + candidat v4 » sur les 30 extraits (`s4v4_test.csv`) : le gain ne tient pas

Contre le candidat v4 à 22 bandes, à débit égal (IC à 95 %) :

| | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions ODG |
|---|---|---|---|---|---|
| 128 kb/s | −0,011 [−0,020 ; −0,003] | −0,010 | +0,004 | −2,8 % [−5,0 ; −0,6] | 14 |
| 160 kb/s | −0,027 [−0,037 ; −0,017] | −0,002 | +0,002 | −5,0 % [−7,0 ; −2,9] | 19 |

Contre la production v3 : ODG +0,007 à 128 kb/s, −0,014 à 160 kb/s. Distribution à 128 kb/s :
écart type 0,055 (v4 : 0,063), p10 −0,218 (v4 : −0,225), mais médiane −0,152 (v4 : −0,133).

- **Les régressions sont toutes dans le rock** (New Order, Orange Goblin, Red Fang, Steel Panther,
  Judas Priest…). Zimtohrli reste favorable en moyenne, mais il pénalise aussi Orange Goblin,
  New Order/Joy Division et Astroqueen (+5 à +10 %).
- **Le jeu de 12 extraits était biaisé** : 6 extraits calmes ou tonals sur 12, contre 8 sur 30
  dans le jeu de test.
- **Cause : la répartition des bits.** À q égal, les bandes étroites font baisser le débit de
  6,9 % sur le rock (de −4,0 à −10,7 %) et de 3,4 % seulement sur la musique calme. À débit moyen
  égal, le rock perd donc des bits au profit du reste. Les masques des bandes étroites sont plus
  hauts (tonalité et étalement calculés sur moins de raies), et ce n'est pas le coût des énergies
  (0,45 kb/s par bande).
- **Piste** : calculer le modèle psychoacoustique sur les bandes d'origine (masque, tonalité,
  seuil absolu) et ne coder qu'avec les bandes fines. On séparerait ainsi le gain de résolution
  du changement de répartition des bits.

## Bruit en pente, à la manière du floor de Vorbis (sonde `MULE_SLOPE`, `slope_12.csv`)

Dans les trames longues, une bande remplie de bruit prend la pente en dB du niveau de ses bandes
voisines (les deux si elles sont audibles, sinon celle qui l'est). La pente est bornée à ±12 dB aux
bords de la bande, et l'énergie de la bande reste exacte. Aucun bit : seul le décodeur change, le
débit est identique, et la production v3 reste exacte au bit près.

- Effet mesuré (écart entre les deux moitiés de la bande) : sur la bande 20, la pente est presque
  juste (Takemitsu : −3,5 dB, original −4,1, sans pente −0,1). Sur la bande 21, tirée de la seule
  voisine du dessous, elle reste trop faible (+1 dB contre +3 à +9 dans l'original), et va dans le
  mauvais sens sur Takemitsu.
- 12 extraits, à q égal (donc à débit égal) :

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| pente dès 2,8 kHz, contre v3 (q −6 / −9) | +0,003 / +0,003 | +0,002 / +0,001 | +0,041 / +0,028 | −3,3 / −3,7 % | 3 / 2 |
| pente dès la bande 19, contre v3 | +0,003 / +0,003 | +0,002 / +0,001 | +0,042 / +0,029 | −2,6 / −3,1 % | 3 / 2 |
| pente dès 2,8 kHz + v4, contre v4 | +0,002 / +0,001 | +0,001 / −0,000 | +0,017 / +0,013 | −2,6 / −2,8 % | 1 / 1 |
| pente dès la bande 19 + v4, contre v4 | +0,001 / +0,001 | +0,000 / −0,000 | +0,017 / +0,013 | −1,8 / −2,2 % | 1 / 1 |

- Les quatre juges vont dans le même sens, sans régression ODG (pire −0,016). Les seules
  régressions sont ViSQOL sur Airbourne (−0,011, juste au seuil) et, sans la v4, Zimtohrli sur
  Beethoven 59 et Belenos (+4 à +6,5 %). Avec la v4, Zimtohrli n'en a plus aucune.
- Pente dès 2,8 kHz un peu meilleure que dès la bande 19. Validation de « pente + v4 » sur
  30 extraits : `slv4_test.csv`.

### Validation de « pente + v4 » sur 30 extraits (`slv4_test.csv`), contre le candidat v4, à débit égal

| q (≈ kb/s) | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| −6 (121) | +0,0015 [+0,0003 ; +0,0029] | +0,000 | +0,005 [−0,002 ; +0,014] | −1,4 % [−2,5 ; −0,6] | ViSQOL 5 |
| −9 (151) | +0,0009 [−0,0003 ; +0,0023] | −0,001 | +0,003 | −1,2 % [−2,7 ; −0,2] | ViSQOL 4 |
| −12 (182) | −0,0020 [−0,0039 ; −0,0004] | −0,001 | +0,002 | −0,5 % (n.s.) | ODG 1, ViSQOL 4, Zimtohrli 1 |

- Le gain se réduit sur 30 extraits : à peine positif à 120-150 kb/s, légèrement négatif à 180 kb/s.
- ViSQOL pénalise toujours les mêmes extraits, électroniques ou denses : Crystal Castles (jusqu'à
  −0,029), Astroqueen (−0,034), Dance with the Dead, Airbourne. Hypothèse : à côté de bandes
  codées très fortes, la pente tirée des voisines exagère l'inclinaison du bruit.
- **Non retenu tel quel** : sous le seuil d'un changement de format (+0,01), et les juges ne sont pas
  unanimes. Il reste en sonde. Pistes : borner la pente plus bas (±6 dB), ou ne l'appliquer que
  quand les deux voisines sont audibles.

**Décision de l'auteur (21/11/2026) : la pente actuelle entre dans le candidat v4** (elle ne
coûte rien et apporte de petits gains). Nouveau candidat : `slnfm6tg` (pente dès 2,8 kHz, bruit
dans les zéros à −6 dB, garde tonale). Affinage de la pente noté dans `docs/TODO.md`.

## Classes par sous-partition, à la manière des classes de résidu de Vorbis (sonde `MULE_SUBPART`)

Dans les trames longues, une bande codée à partir de la bande 19 (au moins 2 sous-partitions de
4 unités, soit 32 raies ; la dernière prend le reste : 4, 5 et 4 sous-partitions pour les bandes
19, 20 et 21) peut laisser des sous-partitions au bruit. Après les allocations du canal : 1 bit
brut par bande concernée (au moins une sous-partition en bruit), puis 1 bit par sous-partition.
Les raies laissées au bruit sont sautées par le codage des coefficients : le masque est porté par
la structure `group`, donc `band_n` et `coef_index` les sautent partout (choix d'allocation,
Viterbi chaîné, codage, décodage). Leur bruit reprend l'énergie de la bande moins celle des raies
codées, au moins 1/16 du niveau de la bande par raie. L'encodeur laisse au bruit une
sous-partition dont la raie la plus forte reste sous la cible du masque plus `sp_db`. Une bande
entièrement en bruit passe à l'allocation 0.

- Usage (q −7, bandes 19-21 codées en trames longues, avec au moins une sous-partition en bruit) :
  Takemitsu 21 %, ABBA 22 % (25 % à +6 dB), Spector 0,6 % (16 % à +6 dB), Lebanon Hanover 0,2 %
  (10 % à +6 dB), Max Richter 0 %. Le débit augmente un peu à q égal (+0,1 à +0,4 kb/s) :
  l'indicateur coûte 1 bit par bande codée, et des zéros en TCQ coûtaient déjà peu.
- Mesure sur 12 extraits : `sp_12.csv`.

**Correctifs avant la mesure.** (1) Les indicateurs passent par le rANS : un flux adaptatif de
2 symboles et 3 contextes (`MULE_S_SPART` : l'indicateur de bande ; le bit de chaque
sous-partition selon celui de la précédente), au départ uniforme, sans table entraînée ; les flux
existants ne changent pas (v3 exacte au bit près). (2) Le niveau du bruit des sous-partitions
sautées, « énergie de la bande moins celle des raies codées », est la différence de deux grandes
énergies dans une bande tonale : la première mesure (faite pendant une recompilation, supprimée)
donnait Zimtohrli +96 à +141 % sur Takemitsu. Il est borné à (D/4)² par raie : une sous-partition
sautée reste sous le masque, environ D²/12 à sa raie la plus forte.

Mesure sur 12 extraits (`sp_12.csv`), contre le candidat v4 (`slnfm6tg`), à débit égal :

| variante | ODG 128 / 145 kb/s | ODG avancé | ViSQOL | Zimtohrli | régressions 128 / 145 |
|---|---|---|---|---|---|
| seuil −6 dB (`spm6v4`) | −0,006 / −0,007 | −0,002 / −0,001 | −0,001 / 0,000 | +0,8 / +1,2 % | 2 / 5 |
| seuil 0 dB (`spv4`) | −0,007 / −0,011 | −0,001 / −0,002 | 0,000 / 0,000 | +1,2 / +1,8 % | 3 / 6 |
| seuil +6 dB (`spp6v4`) | −0,018 / −0,027 | −0,006 / −0,003 | +0,001 / 0,000 | +3,1 / +4,5 % | 6 / 10 |
| dès la bande 17, 0 dB (`sp17v4`) | −0,008 / −0,011 | −0,002 / −0,002 | 0,000 / 0,000 | +1,4 / +1,9 % | 3 / 6 |

- **Négatif, et d'autant plus que davantage de sous-partitions vont au bruit.** Les régressions
  sont sur Belenos (ODG −0,05 à −0,09), Eminem, Salut c'est cool et Takemitsu (Zimtohrli +3 à
  +20 %). Le débit ne baisse pas (+0,1 kb/s à q égal) : les raies sous le masque coûtaient déjà peu
  en TCQ.
- **Enseignement** : les raies faibles que la TCQ code sous le masque (souvent ±1, ou un zéro avec
  le bruit de `nf_coded`) valent mieux, pour tous les juges, qu'un bruit au bon niveau. Le défaut
  des aigus de MULE est le bruit plat des bandes sans bits, pas le codage des bandes codées. Le
  sens utile des sous-partitions serait l'inverse, coder une sous-partition dans une bande sans
  bits, mais la garde tonale le fait déjà à l'échelle de la bande, et les sous-partitions
  sautées autour de la raie ont aussi régressé (Takemitsu).
- **Non retenu.** La sonde reste dans le code (`sp`), désactivée.

## Affinage du bruit des bandes sans bits (`slr_12.csv`)

Trois règles, côté décodeur seul (octet 30 de l'en-tête, bits 5 à 7) : pente bornée à ±6 dB au lieu
de ±12 (`sl6v4`) ; pente seulement entre deux voisines audibles, sinon bruit plat (`slbv4`) ; bande
21 qui tombe d'au moins 4 dB d'un bord à l'autre (`sltv4`) ; et leurs combinaisons (`slbtv4`,
`sl6btv4`). 12 extraits, débit identique, contre le candidat v4 (`slnfm6tg`), q −6 / −9 :

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| ±6 dB | −0,000 / +0,000 | −0,000 / +0,000 | +0,000 / +0,000 | +0,0 / −0,0 % | 0 / 0 |
| deux voisines | −0,001 / −0,000 | +0,001 / +0,001 | −0,008 / −0,008 | +0,2 / +0,0 % | 2 / 2 |
| bande 21 qui tombe | −0,000 / +0,000 | −0,001 / −0,001 | −0,022 / −0,021 | +0,7 / +1,0 % | 2 / 4 |
| deux voisines + bande 21 | −0,001 / −0,000 | −0,000 / −0,000 | −0,020 / −0,020 | +0,6 / +0,9 % | 2 / 4 |
| les trois | −0,001 / +0,000 | +0,000 / −0,000 | −0,020 / −0,020 | +0,7 / +0,9 % | 3 / 4 |

- Aucune ne fait mieux que la pente actuelle. ±6 dB est neutre ; les autres font régresser
  ViSQOL sur Max Richter (jusqu'à −0,20) et Zombie Zombie.
- **Max Richter : son spectre monte vers 20 kHz** (−110 dB vers 17 kHz, −104 dB à 20 kHz, un bruit
  d'enregistrement). Une règle fixe de chute inverse la forme ; « deux voisines » aplatit la bande
  21, qui n'en a qu'une. Aucune règle fixe ne convient à tous : la suite logique serait de
  transmettre l'inclinaison de la bande 21 quand elle est remplie (2 bits par trame longue et par
  canal, environ 0,2 kb/s).
- La pente actuelle reste dans le candidat. Spectrogrammes et WAV à débit égal :
  `scratchpad/eq_wav/*_eqrate_slope.png`, `*_2b_mule_v4_slope_*kbps.wav`.

**Décision de l'auteur (21/11/2026)** : à l'écoute, pas de différence perçue entre avec et sans
pente ; les juges étant cohérents sur la pente bornée à ±6 dB (les quatre à ±0,0002 près, aucune
régression sur 12 extraits), elle remplace la pente à ±12 dB dans le candidat v4 : **`sl6v4`**
(`nf_slope` 1, `nf_slope_mode` 1, bruit dans les zéros à −6 dB, garde tonale). Confirmation sur
30 extraits : `sl6v4_test.csv`.

### Confirmation de la pente à ±6 dB sur 30 extraits (`sl6v4_test.csv`)

- **Contre la pente à ±12 dB : identique.** Les quatre juges sont à ±0,0002 près, aucune
  régression ; ViSQOL +0,0002 à +0,0003, significatif mais minuscule.
- **Contre le candidat sans pente** (`nfcm6tg`), q −6 / −9 / −12 (≈ 121 / 151 / 182 kb/s) : ODG
  +0,0016 [+0,0004 ; +0,0029] / +0,0010 / −0,0022 ; Zimtohrli −1,4 % [−2,5 ; −0,6] / −1,3 % / −0,5 % ;
  ViSQOL +0,006 / +0,003 / +0,002, avec les mêmes régressions ViSQOL qu'à ±12 dB (Crystal Castles,
  Astroqueen, Dance with the Dead, Airbourne).
- **Le candidat v4 complet contre la production v3**, à q égal (même débit à 0,3 kb/s près) :
  ODG +0,022 [+0,015 ; +0,029] / +0,019 [+0,012 ; +0,027] / +0,002 ; ViSQOL +0,025 / +0,013 / +0,005 ;
  Zimtohrli −3,2 % / −1,9 % / −0,7 % ; mais PEAQ avancé −0,009 / −0,005 / −0,003 (5 régressions à
  121 kb/s sur le rock : New Order/Joy Division, And One, Spector, Dance with the Dead, Eminem). Le
  gain fond vers 180 kb/s.
- La pente à ±6 dB est confirmée dans le candidat v4.

### Faut-il borner la pente ? (question de l'auteur)

Pentes réelles (q −9, 10 extraits, 19 220 bandes remplies en trames longues dès la bande 12, écart
aux bords de la bande) : médiane 2,5 dB, p90 6,4 dB, p99 22 dB, max 27 dB. Au-delà de 6 dB : 12 %
des bandes ; au-delà de 12 dB : 5 %, presque toutes sur Belenos (76 % de ses bandes remplies),
ailleurs jamais (max 5 à 11 dB).

- Pour l'oreille et les juges, la borne compte peu : ±6 et ±12 dB donnent les mêmes notes sur
  30 extraits, alors qu'elles diffèrent sur 12 % des bandes.
- Pour le décodeur, une borne reste nécessaire : `exp2_q16` et la mise à l'échelle du bruit ne sont
  valables que jusqu'à environ ±24 dB, et un flux abîmé peut donner n'importe quel écart d'énergie
  entre voisines (décalages hors limites, comportement indéfini). Une pente extrême concentrerait
  aussi le bruit sur quelques raies au bord de la bande.
- Proposition pour figer la v4 : une borne fixe (±6 dB, adoptée), sans bits de mode dans l'en-tête,
  puisque les deux autres règles sont écartées.

**Simplification (21/11/2026, décision de l'auteur)** : les bits de mode de l'octet 30 sont
supprimés. La pente est bornée à ±6 dB, en dur dans le décodeur ; l'octet 30 ne porte plus que
la bande de départ. Les variantes `sl6v4` et `slnfm6tg` donnent désormais la même chose (la
seconde mesurait ±12 dB avant ce changement). Les variantes `slbv4`, `sltv4`, `slbtv4` et
`sl6btv4` sont retirées.

## Le modèle psychoacoustique et les raies tonales (travail autonome, nuit du 20 au 21/11)

Remarque de l'auteur : on serait limité par le modèle psychoacoustique de l'encodeur, qui
protège mal les notes tonales, plus que par le format ; à l'écoute, Apple fait mieux sur tout ce
qui est tonal.

**Outil** : `eval/tonal_lines.py`. Il repère les raies stables de l'original (maxima locaux à
12 dB au moins au-dessus de la médiane de ±1 kHz, présents sur deux trames voisines, dès 1 kHz)
et classe ce que chaque codec en fait : gardée (à 3 dB près, elle dépasse encore de 6 dB son
entourage décodé), atténuée, amplifiée, noyée (elle ne dépasse plus). Pour MULE, la trace dit où
la raie s'est perdue (trame courte, bande sans bits, coefficient à 0, coefficient codé).
`--match aapl_q63` règle MULE par extrait sur le débit d'Apple.

**Mesure** (12 extraits, 79 828 raies, MULE au débit d'Apple par extrait ; Opus 128 à son débit,
souvent plus haut) :

| raies noyées | 1-10 kHz | bande 19 (10,3-13,4) | bande 20 (13,4-17,2) | bande 21 (17,2-20) |
|---|---|---|---|---|
| MULE v3 | ≤ 0,2 % | 0,4 % | 25,5 % | 78 % |
| candidat v4 | ≤ 0,2 % | 0,4 % | 16,9 % | 78 % |
| Apple | ≤ 0,1 % | 0,5 % | **3,4 %** | 76 % |
| Opus | ≤ 0,1 % | 0,3 % | 3,8 % | 12 % |

- Sous 10 kHz, tout le monde garde plus de 99 % des raies. **L'écart avec Apple est tout entier
  dans la bande 20** ; dans la bande 21, Apple coupe autant que MULE.
- Takemitsu domine : 50 % de raies noyées (v4), Apple 32 %, Opus 4 %. Beethoven 59 : v4 3,3 %,
  Apple 0,7 %.
- **Où les raies se perdent** (candidat v4) : dans les bandes sans bits (5,5 % de toutes les
  raies, presque toutes les noyées) ; dans les bandes codées, les raies sont gardées (89 % de
  toutes les raies, 0,1 % noyées). C'est la décision d'allocation, pas la finesse de quantification.
- **Pourquoi ces bandes restent sans bits** : pour 98 % des raies concernées, le masque de la
  bande est le **seuil absolu d'audition**, pas le masquage. Terhardt, avec 96 dB pour la pleine
  échelle, au point le plus sensible de la bande : environ 33 dB SPL pour la bande 20, mais 88 dB SPL
  pour la bande 21 (il faudrait −8 dBFS pour y coder quelque chose). 15 % des raies noyées
  dépassent pourtant la cible de la bande : la garde tonale les manque.
- Cela explique l'échec de `hi_db` (« plus de bits dans les aigus ») : il agit sur le décalage de
  masquage, avant la comparaison au seuil absolu, donc sans effet sur ces bandes.
- Essais (`psy_12.csv`, contre le candidat v4) : seuil absolu −6 et −12 dB (`ath_db`) ; garde
  tonale à 12 dB sous la cible au lieu de 6 (`tg_db`) ; et deux corrections qui visent la
  précision des raies codées plutôt que ce mécanisme : tonalité tirée aussi de la crête de la
  bande (`ton_crest_db`, nouveau paramètre) et masques raie par raie jusqu'en haut (`fine_nb` 22).

Résultats (`psy_12.csv`, contre le candidat v4, à débit égal, 128 / 145 kb/s) :

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| seuil absolu −6 dB | −0,003 / −0,006 | −0,002 / −0,007 | +0,001 / +0,005 | +1,9 / +5,5 % | 11 / 15 |
| seuil absolu −12 dB | −0,009 / −0,019 | −0,008 / −0,019 | +0,014 / +0,017 | +4,7 / +12,7 % | 17 / 25 |
| garde tonale à 12 dB | 0,000 / +0,000 | 0,000 / 0,000 | 0,000 / 0,000 | +0,0 / +0,1 % | 0 / 0 |
| crête (10 dB) | −0,017 / −0,017 | −0,017 / −0,025 | −0,002 / −0,002 | +5,3 / +11,3 % | 18 / 23 |
| masques raie par raie jusqu'en haut | −0,004 / −0,009 | −0,004 / −0,023 | +0,004 / +0,001 | +0,7 / +8,0 % | 7 / 16 |

- Abaisser le seuil absolu coûte +3 à +7,5 kb/s à q égal ; à débit égal, seul ViSQOL le
  récompense, PEAQ et Zimtohrli le sanctionnent (surtout le rock). Pour les juges, les raies
  faibles de la bande 20 ne valent pas les bits qu'elles coûtent ailleurs.
- La garde tonale plus généreuse ne change rien : les raies manquées sont des peignes, pas des
  raies isolées, et la condition de crête les écarte.
- La crête et les masques raie par raie dépensent des bits sans convaincre. Aucune variante
  retenue.

**Bruit autour des raies** (même mesure, `skirt` : puissance ajoutée ou retirée de 2 à 6 raies de
part et d'autre d'une raie gardée) : médiane environ 0 dB pour tous ; p90 MULE +1,2 à +1,3 dB,
Apple +1,6, Opus +2,0 (10-20 kHz : MULE +3,2, Apple +2,9, Opus +3,8). MULE ne bave pas plus
qu'Apple autour des partiels.

**Continuité dans le temps : les raies de la bande 20 clignotent.** Part des raies qui passent,
d'une trame à la suivante, de gardée à noyée ou l'inverse :

| | 1-10 kHz | 10-13,4 kHz | 13,4-17,2 kHz |
|---|---|---|---|
| MULE v3 | 0,1 % | 0,3 % | 7,9 % |
| candidat v4 | 0,1 % | 0,4 % | **8,4 %** |
| Apple | 0,05 % | 0,4 % | **1,8 %** |
| Opus | 0,07 % | 0,4 % | 3,9 % |

Par extrait (10-20 kHz) : Beethoven 59 v4 24 % (v3 14 %, Apple 0,6 %), Lebanon Hanover 13 % (6 %),
Takemitsu 20 % (14 %), Mravinsky 4 % (0 %). Un partiel qui apparaît et disparaît d'une trame à
l'autre gazouille (« birdies ») : candidat sérieux pour ce que l'auteur entend sur le tonal.
Mécanisme : dans la bande 20, la puissance de la bande oscille autour du seuil absolu, la bande
passe de codée à remplie de bruit ; `alloc_hyst` ne joue qu'entre deux allocations non nulles. La
garde tonale aggrave Beethoven 59 en codant la bande par intermittence.

**Correction** (encodeur seul) : `stick_db`, une hystérésis codée/bruit. Dans une trame longue
après une trame longue, une bande codée la fois précédente et laissée à 0 reste codée à
l'allocation 1 (`tg_a` avec la garde) tant que sa puissance, ou avec la garde sa raie la plus
forte, reste à moins de `stick_db` sous la cible. Essais 3, 6, 10 dB sur le candidat v4
(`stick_12.csv`).

Premier essai (`stick_12.csv`) : faux. Les trois seuils donnent les mêmes notes, le débit ne
bouge pas (+0,1 kb/s), et les extraits tonals régressent fortement (Beethoven 59 ViSQOL −0,15,
Mravinsky Zimtohrli +18 à +20 %, Classical, Takemitsu). Cause : la branche « garde tonale » de
l'hystérésis gardait la bande dès que sa raie la plus forte restait à `stick_db` + 6 dB sous la
cible, sans la condition de crête de la garde. Une bande dont la note s'est éteinte restait codée
à l'allocation 1, son bruit quantifié grossièrement au lieu d'être rempli, et le pic d'un bruit
dépasse presque toujours ce seuil (d'où des seuils sans effet). Corrigé : la branche exige
aussi une raie isolée (`lone_line`, partagée avec la garde tonale). Nouvel essai : `stick_12b.csv`.

Résultat corrigé (`stick_12b.csv`, contre le candidat v4, 128 / 145 kb/s ; débit inchangé) :

| seuil | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| 3 dB | −0,005 / −0,008 | +0,002 / +0,002 | −0,007 / −0,007 | +0,8 / +0,7 % | 4 / 7 |
| 6 dB | −0,005 / −0,009 | +0,004 / +0,002 | −0,016 / −0,015 | +1,4 / +1,9 % | 6 / 9 |
| 10 dB | −0,006 / −0,008 | +0,003 / +0,001 | −0,028 / −0,024 | +2,5 / +3,8 % | 10 / 9 |

Négatif, et d'autant plus que l'hystérésis colle : les régressions sont sur les extraits tonals
(Beethoven 59, Mravinsky, Classical, Takemitsu). Vérification en cours : l'hystérésis réduit-elle
vraiment les bascules (`tonal_stick.csv`) ?

**L'hystérésis ne réduit presque pas le clignotement** (`tonal_stick.csv`) : bascules dans la
bande 20 8,4 % → 7,5 % (3 dB) et 6,6 % (10 dB). Décomposition des bascules du candidat v4 dans la
bande 20, selon le sort de la raie dans les deux trames (trace) :

| transition | part des bascules | taux de bascule |
|---|---|---|
| coefficient à 0 → à 0 | 17,5 % | 19 % |
| codée → bande sans bits | 14,7 % | 40 % |
| codée → coefficient à 0 | 14,4 % | 22 % |
| coefficient à 0 → codée | 10,9 % | 19 % |
| bande sans bits → codée | 9,9 % | 36 % |
| bande sans bits → bande sans bits | 9,3 % | 19 % |
| codée → codée | 2,7 % | 0,3 % |

- Un quart seulement des bascules vient d'une bande qui alterne codée/bruit (ce que visait
  l'hystérésis). L'essentiel vient de raies de bandes codées quantifiées tantôt à zéro, tantôt
  non : une raie dont l'amplitude tourne autour du demi-pas passe à zéro une trame sur deux, et le
  bruit qui la remplace ressort ou non au hasard. Une raie franchement codée ne clignote presque
  jamais.
- **Correction suivante** (encodeur seul) : `peak_w`, dans le Viterbi chaîné, un poids plus fort
  sur l'erreur des coefficients qui sont des pics spectraux (au moins `peak_db` au-dessus de la
  moyenne de la bande et pas plus faibles que leurs voisins à ±2 raies ; trames longues, dès la
  bande 12) : la TCQ garde ces raies au lieu de les mettre à zéro. Essais 2, 4, 8 ; 4 à 6 dB
  (`peak_12.csv`).

Résultat (`peak_12.csv`, contre le candidat v4, 128 / 145 kb/s ; +0,2 à +0,5 kb/s à q égal,
+1,5 kb/s à 6 dB) :

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| poids 2 | −0,001 / −0,002 | −0,001 / −0,001 | +0,002 / +0,002 | −0,8 / −0,8 % | 0 / 1 |
| poids 4 | −0,001 / −0,003 | −0,001 / −0,002 | +0,003 / +0,003 | −0,9 / −0,3 % | 0 / 2 |
| poids 8 | −0,001 / +0,001 | −0,004 / −0,004 | +0,004 / +0,003 | −0,9 / −0,2 % | 1 / 0 |
| poids 4, pic à 6 dB | −0,004 / −0,005 | −0,014 / −0,010 | +0,008 / +0,007 | −0,9 / +0,1 % | 3 / 4 |

Presque neutre, juges partagés (PEAQ un peu négatif, ViSQOL et Zimtohrli un peu positifs). La
question est l'effet sur le clignotement (`tonal_peak.csv`).

**Effet sur le clignotement** (bascules dans la bande 20, mêmes 12 extraits) : candidat v4 8,4 %,
hystérésis 3 dB 7,5 %, 10 dB 6,6 %, poids sur les pics 2 : 9,4 %, 8 : 10,0 % ; Apple 1,8 %. Le
poids garde un peu plus de raies (noyées 23,1 → 21,4 %, 10-20 kHz) mais par intermittence : il
augmente le clignotement. Aucune des deux corrections ne le règle.

**Exemple d'écoute** (`scratchpad/flicker_wav/`, au débit d'Apple) : Beethoven 59 (142 kb/s) et
Mravinsky (135 kb/s), original, candidat v4, Apple. Sur Beethoven 59, une raie continue à
15,6 kHz dans l'original : MULE la rend en pointillés, Apple la garde continue (et coupe le reste
au-dessus de 16 kHz environ).

### Bilan de la nuit

- L'outil `eval/tonal_lines.py` localise le défaut : MULE garde ses raies aussi bien qu'Apple
  sous 13,4 kHz, ne bave pas plus autour des partiels, mais dans la bande 20 (13,4-17,2 kHz) il en
  noie davantage (16,9 % contre 3,4 %) et surtout **les fait clignoter** (8,4 % de bascules par
  trame contre 1,8 %).
- Le mécanisme n'est pas le masquage mais le **seuil absolu** (bandes sans bits) et le **demi-pas
  de quantification** (raies codées tantôt à 0, tantôt non) : des raies faibles qui oscillent
  autour d'un seuil de décision dur.
- Rien n'est adopté. Les leviers essayés (seuil absolu plus bas, garde tonale plus large, crête,
  masques raie par raie, hystérésis codée/bruit, poids sur les pics) sont négatifs ou neutres pour
  les juges, et aucun ne supprime le clignotement.
- Pistes : (1) une décision **temporelle par raie**, comme le suivi de stabilité des partiels du
  modèle 2 de MPEG : qu'une raie stable dans le temps garde la même décision (codée ou non) d'une
  trame à l'autre, en mémorisant les raies codées ; (2) côté décodeur, un bruit de remplissage
  qui ne fasse pas « ressortir » une raie au hasard une trame sur deux (bruit corrélé d'une trame
  à l'autre sur les raies tonales, par exemple) ; (3) l'écoute de l'auteur pour confirmer que ce
  clignotement est bien ce qu'il entend.

## Encodeur qui suit les raies (`trk`, étapes 0 et 1, 21/11/2026)

Proposition validée par l'auteur : suivre chaque raie dans le temps pour que la décision « codée
ou non » soit continue d'une trame à l'autre (`core/enc_track.c`, encodeur seul, format inchangé).

- **Deux passes.** La première encode normalement mais relève seulement, par trame longue et par
  canal, les pics de la FFT (au moins `trk_prom` 12 dB au-dessus de la moyenne en dB des ±32 raies,
  pas plus faibles que leurs voisins à ±2, dès la bande `trk_b0` 12 jusqu'à 19,98 kHz, 48 au plus ;
  énergie des 3 raies, étalonnée en unités MDCT par le rapport des énergies totales) et la cible de
  chaque bande (masque × qualité). Son résultat est jeté. La FFT est employée parce que le
  coefficient MDCT d'une sinusoïde stable varie d'une trame à l'autre avec sa phase : un seuil sur
  les valeurs MDCT ferait clignoter une note parfaite.
- **Suivi** : un pic est relié au pic le plus proche (±1 raie) de la trame précédente, ou à
  défaut de l'avant-dernière (trou d'une trame comblé).
- **Décision par raie suivie** : codée sur toute sa vie si elle dure au moins `trk_len` (4)
  trames et si son rapport médian (énergie de la raie sur cible × largeur de la bande, soit son
  niveau face au seuil d'une sinusoïde) atteint `trk_db`.
- **Deuxième passe** : plancher d'allocation pour une bande qui tient une raie codée (le niveau
  unité D/2 au plus la moitié de l'amplitude de la raie), appliqué aussi après le choix
  débit-distorsion ; dans le Viterbi chaîné, le niveau 0 est interdit aux deux coefficients MDCT
  les plus forts autour de la raie. En M/S, les raies des deux canaux protègent le canal M.
- La raie « non codée » n'est pas encore empêchée d'être codée par intermittence (le volet
  « jamais » de la proposition).

**Étape 0** : le suivi retrouve 95 à 99 % des raies que `tonal_lines.py` voit dans la bande 20
(Beethoven 59, Takemitsu ; Spector 84 %). Débit et décodage normaux, encodage environ 7 s par
extrait (deux passes). Étalonnage vérifié avec des sinusoïdes à 15 kHz : codée jusqu'à −70 dBFS
(26 dB SPL), laissée au bruit à −80 dBFS (16 dB SPL), pour un seuil de Terhardt d'environ 33 dB
SPL et q −9. Les raies qui clignotent dans la bande 20 sont donc sous le seuil d'audition de
MULE : rapport médian des raies suivies (≥ 4 trames) d'environ −12 à −15 dB (Beethoven 59,
Takemitsu), d'où aucune décidée codée à `trk_db` 0.

**Étape 1** : essais à `trk_db` 0, −12, −18 (`trk_12.csv`), puis clignotement (`tonal_trk.csv`).

Résultats de l'étape 1 (`trk_12.csv`, contre le candidat v4, à débit égal, 128 / 145 kb/s ; +0,1 à
+0,6 kb/s à q égal) et clignotement (`tonal_trk.csv`, au débit d'Apple) :

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions | bascules bande 20 | noyées bande 20 |
|---|---|---|---|---|---|---|---|
| candidat v4 | | | | | | 8,4 % | 16,5 % |
| suivi 0 dB | −0,001 / −0,000 | −0,000 / −0,001 | +0,000 / +0,000 | +0,0 / +0,1 % | 0 / 0 | | |
| suivi −12 dB | −0,003 / −0,001 | −0,001 / −0,002 | −0,001 / −0,003 | +0,3 / +0,8 % | 2 / 3 | 5,4 % | 8,8 % |
| suivi −18 dB | −0,002 / −0,001 | +0,000 / −0,001 | −0,016 / −0,010 | +0,7 / +1,2 % | 4 / 6 | **3,1 %** | **4,9 %** |
| Apple | | | | | | 1,8 % | 3,1 % |

- **Le suivi règle le mécanisme** : Beethoven 59 passe de 23,8 % de bascules à 1,5 % (Apple 0,6 %),
  la raie à 15,6 kHz redevient continue sur le spectrogramme.
- **Les juges ne suivent pas** : ViSQOL pénalise justement les extraits corrigés (Beethoven 59
  −0,08 à −0,10, Takemitsu −0,04 à −0,08 à −18 dB).
- **Le spectrogramme montre pourquoi** : le plancher fait coder toute la bande 20 à une allocation
  basse pour une raie ; la plupart des autres coefficients tombent à zéro, et le bruit des zéros
  (`nf_coded`, −6 dB) ne remplace pas le bruit de remplissage à la bonne énergie : la bande se vide
  autour de la raie.
- **Correction** : `sp` 2, les sous-partitions dans le bon sens. Une bande que le suivi fait passer
  de bruit à codée ne code que les sous-partitions (environ 0,7 kHz) qui tiennent ses raies ; le
  reste garde un bruit à l'énergie de la bande moins celle des raies codées (`MULE_SUBPART`, v4).
  Essais `tkm18spv4`, `tkm12spv4` (`trksp_12.csv`, `tonal_trksp.csv`). Fichiers d'écoute :
  `scratchpad/flicker_wav/*_3_mule_v4_suivi_*` (Beethoven 59, Mravinsky, Takemitsu).

Premier essai `sp` 2 (`trksp_12.csv`) : la bande restait creuse autour de la raie, comme sans
sous-partitions (ViSQOL Beethoven 59 −0,11, Zimtohrli +9 à +13 %), bien que le clignotement tombe
(bande 20 : 2,9 % à −18 dB). Cause : la borne (D/4)² posée sur le bruit des sous-partitions
sautées (contre l'erreur sur Takemitsu) ; ici le pas est fixé par une raie faible, donc petit, et la
borne écrase le bruit. Correction (décodeur, sonde `MULE_SUBPART`) : la borne ne joue que si les
raies codées portent la moitié de l'énergie de la bande ou plus (bande tonale) ; une bande codée
pour une raie suivie faible garde son bruit. Spectrogramme : la bande 20 de Beethoven 59 garde son
bruit, la raie à 15,6 kHz reste en grande partie continue. Nouvel essai : `trksp2_12.csv`,
`tonal_trksp2.csv`.

Deuxième essai (`trksp2_12.csv`) : Beethoven 59 ne régresse plus, mais Takemitsu s'effondre
(Zimtohrli +39 à +42 %, ViSQOL −0,14 à −18 dB). Le spectrogramme montre que les raies du peigne
sont continues, mais le bruit des sous-partitions sautées clignote à son tour (salves entre 13,4
et 14,7 kHz) : la borne bascule d'une trame à l'autre selon que les raies codées portent ou non la
moitié de l'énergie. Estimer le niveau du bruit au décodeur par différence n'est pas fiable.

**Correction, à la manière de Vorbis** : l'encodeur mesure le niveau du bruit des sous-partitions
sautées et l'envoie, 3 bits bruts par bande à sous-partitions sautées, par pas de 3 dB sous le
niveau de la bande (`MULE_SUBPART`). Spectrogramme de Takemitsu : les salves ont presque disparu
(une reste vers 3,8 s), les raies du peigne restent continues. Troisième essai : `trksp3_12.csv`,
`tonal_trksp3.csv`.

Troisième essai (`trksp3_12.csv`, contre le candidat v4, 128 / 145 kb/s) :

| variante | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| suivi −18 dB + sous-partitions | −0,002 / −0,001 | +0,000 / −0,001 | −0,007 / −0,002 | +0,5 / +1,1 % | 2 / 2 |
| suivi −12 dB + sous-partitions | −0,004 / −0,002 | −0,002 / −0,003 | −0,000 / −0,001 | +0,8 / +1,9 % | 2 / 2 |

Il ne reste presque qu'une régression, Takemitsu (ViSQOL −0,07 / −0,03 à −18 dB ; Zimtohrli +7 à
+14 % à −12 dB) ; Beethoven 59 et Mravinsky sont neutres. Juges proches de zéro, encore un peu
négatifs : c'est maintenant à l'écoute de trancher.

**Remarque de l'auteur : on s'entraînerait sur des artefacts d'enregistrement de Beethoven 59 et
Takemitsu.** Vérification (raies de 13,4 à 20 kHz de l'original, `tonal_12b.csv`) :
- **Beethoven 59** : 85 % de ces raies sont une seule raie constante à 15,61 kHz, présente sur
  58 % des trames, quelle que soit la musique. C'est la fréquence de balayage ligne des téléviseurs
  et moniteurs cathodiques (15 625 Hz, PAL/SECAM) : un sifflement capté à l'enregistrement, pas
  la musique. Peu d'adultes l'entendent.
- **Takemitsu** : un peigne de raies à fréquences fixes de 15 à 19 kHz (18,99 kHz sur 37 % des
  trames, 17,66 et 16,24 kHz sur environ 20 %), sans rapport apparent avec les notes : bande
  magnétique, électronique ou parasites, en tout cas douteux comme « note tonale ».
- Les autres extraits ont peu de raies dans ces bandes, dispersées (au plus 5 % des trames pour
  une même fréquence).
- Conséquence : la mesure du clignotement dans la bande 20 et l'écart avec Apple viennent surtout
  de ces deux extraits, donc en bonne partie d'artefacts. Le suivi des raies ne peut pas être
  adopté sur cette base ; seule la validation sur 30 extraits (en cours, `tkm18sp_test.csv`) et
  l'écoute de passages musicaux comptent. Sous 13,4 kHz, là où sont les notes, la mesure ne montre
  pas de déficit de MULE face à Apple : ce que l'auteur entend sur le tonal reste à identifier.

## Belenos (cornemuse) : MULE remplit les creux entre les harmoniques

Proposé par l'auteur : un extrait très tonal et sans artefact, l'un des plus difficiles. Au débit
d'Apple (133-134 kb/s, fichiers `eq_wav`), écart décodé − original, médiane (p90) :

| région | creux entre partiels : MULE v3 | candidat v4 | Opus | Apple | partiels (tous) |
|---|---|---|---|---|---|
| 0,2-1 kHz | +3,4 (+13,4) | +3,4 (+13,3) | +2,8 (+11,6) | **+0,6 (+5,5)** | ≈ 0 |
| 1-4 kHz | +3,1 (+13,2) | +3,2 (+13,5) | +4,0 (+14,1) | **+1,3 (+9,2)** | −0,1 |
| 4-10 kHz | +2,7 (+12,4) | +3,3 (+13,1) | +4,3 (+15,0) | **+1,2 (+9,6)** | −0,1 |
| 10-16 kHz | +0,8 (+7,8) | +1,0 (+8,4) | +3,9 (+14,0) | +0,6 (+9,3) | −0,1 à −0,3 |

(Creux : minima locaux à plus de 2 raies d'un partiel, à 70 dB au plus sous le maximum de la trame.)

- Les partiels sont rendus au même niveau par tous ; c'est le fond entre les notes qui change :
  MULE et Opus y ajoutent environ 3 dB (13 dB au p90), Apple 0,6 à 1,3 dB. Le contraste harmonique
  baisse : la remarque de l'auteur (« MULE bave, Apple ne fait que retirer »), mesurée sur un vrai
  instrument et dans les fréquences des notes.
- Mécanisme probable : Apple quantifie avec une zone morte (un petit coefficient va à zéro) ; la
  TCQ de MULE n'a pas de zéro dans la moitié de ses états : un coefficient presque nul y est
  reconstruit à ±D/2 quand le treillis l'impose. Le bruit des zéros du candidat v4 en ajoute un peu
  (4-10 kHz : +3,3 dB contre +2,7 en v3).
- Correction à essayer (encodeur seul) : dans le Viterbi, une erreur qui ajoute de l'énergie
  (|reconstruction| > |original|) coûte plus cher qu'une erreur qui en retire.

### Le suivi des raies sur 30 extraits (`tkm18sp_test.csv` : suivi −18 dB, sous-partitions, niveau de bruit transmis)

ODG par extrait à débit moyen égal (interpolé, sans extrapolation) :

| 128 kb/s | médiane | p10 | p25 | p75 | p90 | écart type | pire |
|---|---|---|---|---|---|---|---|
| MULE v3 | −0,151 | −0,256 | −0,189 | −0,116 | −0,084 | 0,070 | −0,308 (Zombie Zombie) |
| candidat v4 | −0,130 | −0,221 | −0,172 | −0,094 | −0,072 | 0,063 | −0,280 (Belenos) |
| v4 + suivi | −0,133 | −0,219 | −0,174 | −0,102 | −0,077 | 0,060 | −0,269 (Belenos) |
| Opus | −0,092 | −0,141 | −0,125 | −0,078 | −0,052 | 0,113 | −0,685 (Belenos) |
| Apple | −0,277 | −0,456 | −0,372 | −0,217 | −0,206 | 0,120 | −0,683 (Zombie Zombie) |

| 160 kb/s | médiane | p10 | p25 | p75 | p90 | écart type | pire |
|---|---|---|---|---|---|---|---|
| MULE v3 | +0,009 | −0,149 | −0,026 | +0,042 | +0,104 | 0,082 | −0,176 (Takemitsu) |
| candidat v4 | +0,016 | −0,107 | −0,025 | +0,081 | +0,108 | 0,079 | −0,165 (Takemitsu) |
| v4 + suivi | +0,030 | −0,111 | −0,026 | +0,074 | +0,093 | 0,077 | −0,163 (Lebanon Hanover) |
| Opus | +0,010 | −0,051 | −0,012 | +0,038 | +0,054 | 0,075 | −0,302 (Belenos) |
| Apple | −0,013 | −0,114 | −0,053 | +0,025 | +0,049 | 0,068 | −0,195 (Zombie Zombie) |

Médianes des autres juges à 128 kb/s : ViSQOL v4 4,668, suivi 4,671, Opus 4,627, Apple 4,519 ;
Zimtohrli (×10⁻⁴, plus bas = mieux) v4 3,53, suivi 3,54, Opus 3,16, Apple 3,75.

- **Le suivi ne change presque rien en général** : médiane −0,133 contre −0,130 à 128 kb/s,
  +0,030 contre +0,016 à 160 ; dispersion un peu plus serrée, pire extrait un peu meilleur. À q égal
  (+0,3 à +0,6 kb/s) : ODG +0,000 à +0,004, Zimtohrli −0,4 %, ViSQOL ≈ 0, 0 à 2 régressions
  (Takemitsu, Beethoven 59 en ViSQOL). Neutre : son effet se limite aux extraits à raies fixes,
  surtout des artefacts.
- Figure : `scratchpad/dist30.png`.

**Correction : poids asymétrique dans le Viterbi** (`tcq_up_w`, encodeur seul) : une erreur qui
ajoute de l'énergie (|reconstruction| > |original|) coûte `tcq_up_w` fois plus. Creux de Belenos au
débit d'Apple, médiane (p90) en dB, et niveau des partiels :

| | 0,2-1 kHz | 1-4 kHz | 4-10 kHz | 10-16 kHz | partiels |
|---|---|---|---|---|---|
| candidat v4 | +3,4 (+13,2) | +3,2 (+13,5) | +3,3 (+13,1) | +1,0 (+8,4) | −0,0 à −0,1 |
| poids 2 | +3,1 (+12,6) | +2,8 (+12,9) | +2,8 (+12,4) | +0,7 (+7,8) | −0,1 à −0,2 |
| poids 4 | +2,5 (+11,9) | +2,1 (+11,7) | +2,2 (+11,6) | +0,3 (+7,2) | −0,1 à −0,4 |
| poids 8 | +1,9 (+11,4) | +1,8 (+11,2) | +1,9 (+11,3) | +0,0 (+7,0) | −0,2 à −0,5 |
| poids 16 | +1,5 (+10,5) | +1,3 (+10,9) | +1,4 (+10,8) | −0,3 (+6,5) | −0,3 à −0,6 |
| sans bruit des zéros | +3,7 (+13,6) | +3,2 (+13,1) | +2,8 (+12,5) | +0,8 (+7,8) | −0,0 à −0,1 |
| poids 8, sans bruit des zéros | +2,0 (+11,7) | **+1,2 (+10,3)** | **+0,1 (+8,6)** | **−0,7 (+5,0)** | −0,2 à −0,5 |
| Apple | +0,6 (+5,5) | +1,3 (+9,1) | +1,2 (+9,6) | +0,6 (+9,3) | −0,0 à −0,3 |

- Le poids vide les creux de façon régulière ; sans le bruit des zéros du candidat v4, le poids 8
  atteint ou dépasse Apple au-dessus de 1 kHz. Sous 1 kHz, MULE reste au-dessus (+2,0 contre +0,6).
- Conflit avec le candidat v4 : son bruit dans les zéros (`nf_coded`) remplit justement les creux.
- Mesure sur 12 extraits (`up_12.csv`) : poids 4 et 8 avec le candidat, poids 8 sans bruit des
  zéros, poids 8 avec un bruit des zéros à −12 dB, candidat sans bruit des zéros (témoin).

Figure de répartition du billet (outillage du blog, style Excalidraw) : `enc_fig3_v4` de
`docs/blog/tools/figs_enc.py`, `docs/blog/fig/enc-fig3-v4.svg` et `-160.svg` (Opus, MULE v4,
MULE v3, Apple).

Mesure sur 12 extraits (`up_12.csv`, première version, poids sur tout dépassement) : très mauvais
pour tous les juges et tous les extraits. À 128 kb/s, contre le candidat v4 : poids 4 ODG −0,145,
ViSQOL −0,042, Zimtohrli +17 % (38 régressions) ; poids 8 −0,216 / −0,072 / +35 % (47) ; poids 8
sans bruit des zéros −0,278 / −0,120 / +56 % ; poids 8 avec bruit des zéros à −12 dB −0,233 /
−0,107 / +45 %. Le témoin sans bruit des zéros perd lui aussi (−0,012, ViSQOL −0,013, Zimtohrli
+4 %, 13 régressions) : `nf_coded` est utile. Cause : le poids pénalise tout dépassement, gros
coefficients compris ; le quantificateur arrondit tout vers le bas et le signal perd de l'énergie
partout (partiels de Belenos déjà −0,5 dB). Bien plus brutal qu'une zone morte, qui n'agit que
sur les petits coefficients.

**Version restreinte** : le poids ne joue que pour un coefficient sous le demi-pas (|x| < D/2),
c'est-à-dire les ±1 forcés par les états impairs de la TCQ. Belenos, au débit d'Apple : creux
+2,6 / +2,5 / +2,6 dB (poids 4) et +2,0 / +2,1 / +2,3 (poids 16) de 0,2 à 10 kHz, contre +3,4 / +3,2
/ +3,3 ; partiels inchangés (−0,0 à −0,1). Mesure : `up2_12.csv`.

Résultat de la version restreinte (`up2_12.csv`, contre le candidat v4, 128 / 145 kb/s) : rejetée
par les quatre juges, d'autant plus que le poids est fort.

| poids | ODG | ODG avancé | ViSQOL | Zimtohrli | régressions |
|---|---|---|---|---|---|
| 4 | −0,054 / −0,043 | −0,037 / −0,018 | −0,011 / −0,008 | +16 / +10 % | 40 / 30 |
| 8 | −0,087 / −0,073 | −0,070 / −0,042 | −0,013 / −0,010 | +27 / +21 % | 42 / 40 |
| 16 | −0,112 / −0,094 | −0,101 / −0,065 | −0,016 / −0,010 | +36 / +30 % | 43 / 39 |

- Une zone morte dure (proposition de l'auteur) serait le cas limite d'un poids infini : les juges
  la sanctionneraient au moins autant. Non implémentée pour l'instant.
- Les ±1 forcés par la TCQ agissent comme un fin bruit qui garde l'énergie des passages faibles ;
  les juges le préfèrent nettement à des zéros, comme partout dans cette étude (coupures, seuil
  absolu, zéros : la perte d'énergie est punie). D'où aussi la médiane PEAQ très basse d'Apple.
- Mais l'oreille de l'auteur préfère Apple sur le tonal : cas où l'écoute tranche. Fichiers de
  Belenos au débit d'Apple : `scratchpad/belenos_wav/` (original, candidat v4, poids 4, poids 16,
  Apple).

**Écoute de l'auteur (Belenos)** : pas de différence perçue entre le candidat v4, les poids 4 et 16
et Apple. Spectrogrammes (`belenos_wav/belenos_0-8k.png`, `belenos_0-2k_zoom.png`,
`belenos_2-3k.png`) : sous 2,5 kHz, la différence d'Apple avec l'original est presque nulle ;
entre 3 et 8 kHz, Apple creuse de profonds trous entre les harmoniques (et sur certaines
harmoniques). MULE répartit une erreur modérée sur tout le spectre.

**L'artefact entre 2 et 3 kHz** (remarqué par l'auteur) : un seul creux, vers 2,45-2,6 kHz pendant
les 4,3 premières secondes, dans la bande 11 (2,41-2,76 kHz, sous la frontière de `nf_coded` et
des masques raie par raie à 2,76 kHz). Original environ −90 à −100 dB, partiels voisins −30 à
−40 dB. Le candidat v4 le remplit d'environ +15 dB : les ±1 forcés de la TCQ, au pas de la bande,
réglé pour ses partiels. Le poids 16 le vide plus que l'original. Apple le garde à peu près (bandes
de facteur d'échelle plus étroites). L'énergie de chaque bande est exacte pour tous (±0,1 dB).
Même rempli, le creux reste environ 45 dB sous les partiels voisins : masqué, ce qui explique que
l'auteur n'entende pas de différence. Pas prioritaire : visible mais inaudible, toutes les
corrections dans l'encodeur sont punies par les juges, et une correction propre demanderait un pas
plus fin dans les bandes basses (changement de format).

Bilan de la piste « tonal » : les défauts visibles sont soit des artefacts d'enregistrement
(Beethoven 59, Takemitsu), soit masqués (creux de Belenos). Aucun défaut tonal à la fois mesurable
et audible trouvé ; il faudrait un passage où l'auteur entend Apple meilleur. `tcq_up_w` (restreint
aux coefficients sous le demi-pas) et `trk` restent des options, désactivées.

## Gel du format v4 (21/11/2026)

Décision de l'auteur : figer la v4 avec le candidat `sl6v4`. Synthèse : `docs/V4.md` ; format
normatif : `spec/FORMAT.md` (version 4).

- **Format** : octet 8 à 4, en-tête de 22 octets comme la v3 (drapeaux de la v3 seulement) ; par
  canal et par trame, 3 bits bruts du niveau du bruit des zéros ; bruit des zéros et bruit en pente
  (±6 dB) à partir de la bande 12, toujours actifs. Le décodeur lit v4, v3 et v2. L'encodeur écrit
  la v4, garde tonale active par défaut (`tg` 1, `nf_off_db` −6).
- **Nettoyage** : toutes les sondes et options d'essai de la branche retirées (repliement,
  rotation, TNS, coupures, bandes coupées `MULE_SPLIT`, seuil absolu de la bande d'origine,
  `hi_db`, sous-partitions et leur flux rANS, suivi des raies `core/enc_track.c`, hystérésis, poids
  sur les pics, poids asymétrique, tonalité par la crête). 98 variantes d'évaluation retirées de
  `eval/refcodecs.py`. Les réglages qui existaient sur `main` restent.
- **Vérification** : la v4 figée décode exactement le même son que le candidat `sl6v4` sur 5
  extraits (empreintes du PCM identiques), 9 octets d'en-tête de moins par fichier : les mesures
  de `sl6v4_test.csv` valent pour la v4. Vecteurs de test : v3 gelés dans `tests/vectors/v3`, v4
  écrits dans `tests/vectors` ; 56 tests verts.
- **QEMU** (Cortex-M3, même décodeur, flux v3 et v4 du même extrait, 10 s, exact au bit près) :
  abba q −12 836 278 → 871 920 instructions par trame (+4,3 %), pire 944 800 → 963 560 ; abba q −7
  789 410 → 841 349 (+6,6 %), pire +3,6 % ; Belenos q −7 922 261 → 950 978 (+3,1 %), pire +2,7 %.
  État 49 372 octets ; code de `dec.c` 16 989 → 18 433 octets.
- **ABX à 128 kb/s** : kit `data/listen/v4/` (`eval/abx_v4.py`) : glockenspiel, clavecin,
  castagnettes, Belenos, Lebanon Hanover, Takemitsu ; AAC Apple en VBR contraint 128 (`aaplc_128`,
  110 à 140 kb/s selon l'extrait) et MULE v4 au même débit. Résultats : `eval/results/V4-ABX.md`.

## Répartition des notes Zimtohrli (21/11/2026) et correction des fichiers d'Opus et d'Apple

`ref_test.csv` (Opus) et `aapl_test.csv` (Apple) dataient d'avant le `%.6g` de `run_eval.py` :
Zimtohrli y est arrondi à 1e-4 (11 et 12 valeurs distinctes sur 270 et 180). Remesurés en entier
sur les 30 extraits : `ref2_test.csv` (opus 112 à 176) et `aapl2_test.csv` (q63 à q91), précis ;
PEAQ identique aux anciens fichiers (seul l'arrondi de Zimtohrli était en cause). Les comparaisons
Zimtohrli de MULE contre MULE n'étaient pas touchées ; les médianes d'Opus et d'Apple données
pendant la v4 l'étaient (Opus 3,16 annoncé à 128 kb/s, 3,38 en réalité).

Figure `enc-fig5-zimt` (et `-160`, `-en`, `docs/blog/tools/figs_enc.py`) ; distance ×1e-4 par
extrait, à débit moyen égal (plus bas = mieux) :

| | médiane 128 | p10-p90 128 | pire 128 | médiane 160 | p10-p90 160 | pire 160 |
|---|---|---|---|---|---|---|
| Opus | **3,38** | 2,43-4,16 | 4,44 (Steel Panther) | 2,26 | 1,53-2,87 | 3,02 (Belenos) |
| MULE v4 | 3,53 | 2,57-4,73 | 6,39 (Garbage) | 1,80 | 1,28-2,33 | 4,61 (Garbage) |
| MULE v3 | 3,49 | 2,57-5,35 | 6,59 (Garbage) | **1,77** | 1,27-2,77 | 4,54 (Garbage) |
| Apple | 4,12 | 3,44-4,96 | 5,20 (Dance with the Dead) | 2,29 | 1,86-2,60 | 2,79 (Takemitsu) |

- À 128 kb/s, Opus a la meilleure médiane ; à 160 kb/s, MULE passe nettement devant (1,8 contre
  2,3 pour Opus et Apple). La v4 resserre surtout le haut de la distribution (p90 5,35 → 4,73 à
  128 kb/s), sa médiane bouge peu.
- Zimtohrli ne voit pas les mêmes extraits que PEAQ : le pire de MULE est Garbage (et non Belenos
  ou Zombie Zombie), et Belenos est son extrait le plus facile, alors qu'il est le pire pour PEAQ.

## Pourquoi Zimtohrli pénalise autant Garbage (21/11/2026)

Remarque de l'auteur : Zimtohrli est probablement un meilleur juge que PEAQ à ces débits ; il
pénalise beaucoup Garbage (pire extrait de MULE). Zimtohrli ×1e-4 :

| Garbage | ~128 kb/s | ~160 kb/s | ~200 kb/s |
|---|---|---|---|
| MULE v4 | 6,86 | 4,90 | 3,94 |
| Opus | 3,97 | 2,67 | 2,19 (173 kb/s) |
| Apple | 5,42 | 2,58 (167 kb/s) | 1,33 (206 kb/s) |

Diagnostic (scratchpad `zimt_diag.py`, à ~128 kb/s, MULE v4 q −6, Opus 128, Apple q63) :
- **Erreur gardée dans une seule bande** (l'original ailleurs) : 12-21 kHz MULE 3,66, Opus 0,30,
  Apple 1,54 ; sous 12 kHz, MULE fait jeu égal avec Opus (0,5 à 1,1). Par passage de 3 s, MULE
  passe de 3,4 à 8,6, Opus reste vers 3,7-4,2. Stéréo hors de cause (L, R, S comme Opus).
- **Pas une coupure** : l'original a un contenu fort jusqu'à 20 kHz et MULE en rend l'énergie
  moyenne à 0,5 dB près.
- **L'énergie des aigus fluctue d'une trame à l'autre** : écart-type de l'erreur d'énergie
  12-20 kHz dans le temps, analyse de 46 ms, MULE 1,65 dB contre 0,54 pour Opus (5,8 ms : 3,12
  contre 1,11) ; Spector 0,94, Lebanon Hanover 0,50.
- **Par décision de l'encodeur** (bandes 19-21, trames longues) : bandes remplies de bruit
  (35 %) écart médian +0,49 dB, écart-type 3,83 dB (Spector 2,38) ; bandes codées justes
  (écart-type 0,22 à 0,93 dB). L'énergie d'une bande de bruit, mesurée sur toute la fenêtre longue,
  est restituée stationnaire : les aigus de Garbage (cymbales, charleston) varient vite, le bruit ne
  suit pas. C'est le défaut d'enveloppe du début de la v4, à l'échelle des trames.
- **Essais d'encodeur** (erreur 12-21 kHz) : `code16` (bandes à partir de la 16 codées à
  l'allocation 1 au lieu du bruit) 3,66 → 2,42 pour +0,2 kb/s ; `tr7` (plus de blocs courts) 3,12 ;
  `tr99` (aucun) 4,21 ; `sh6` sans effet.
- Pistes (encodeur seul, format v4 inchangé) : réévaluer `code16` sur 30 extraits avec Zimtohrli
  comme critère principal ; une « garde d'enveloppe » qui code une bande des aigus au lieu de la
  remplir quand son énergie varie fortement dans la trame.
