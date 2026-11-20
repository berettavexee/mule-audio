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
