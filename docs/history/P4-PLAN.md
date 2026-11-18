# P4 : plan, qualité de l'encodeur

Point de départ (format v1, fichiers réels, corpus P0) : à 128 kb/s, ODG de −0,44, contre −0,48 pour Vorbis et −0,30 pour Opus. MULE est devant sur l'ODG avancé et le NMR. Ses points faibles sont les sons tonals clairsemés (triangles, glockenspiel, orgue, violon), entre −0,2 et −0,33 face à Vorbis.

## Objectifs

| Critère | Cible |
|---|---|
| ODG de base @128 / @160 | ≤ −0,35 / ≤ −0,20 |
| ODG avancé, NMR | garder l'avance |
| Pire écart d'un extrait face à Vorbis | ≥ −0,10 |
| Coût en calcul du décodeur | +20 % au plus, toujours compatible avec la virgule fixe |
| ABX à 160 kb/s sur les extraits critiques | non distinguable de l'original : porte **G2** |

## Méthode (P4.0)

- **Corpus** : `dev` = les 36 extraits P0 plus 30 tirés au hasard dans la bibliothèque (graine 2026), utilisé pour régler ; `test` = 30 autres, utilisés seulement aux jalons (`eval/corpus_p4.json`, `run_eval.py --set`).
- **Comparaison** : `eval/p4_compare.py`, à débit égal (128/160), avec intervalle de confiance à 95 % par rééchantillonnage des extraits, et liste des extraits qui régressent, à débit corrigé.
- **Acceptation** :
  - changement avec perte : écart d'ODG ≥ +0,01, intervalle de confiance qui exclut 0, aucun extrait < −0,05 ;
  - changement sans perte : ≥ 0,5 % de débit en moins.
- **Critère principal** : la moyenne de l'ODG de base et de l'ODG avancé. Le NMR vient en second, ViSQOL sert seulement de contrôle aux jalons.
- Leviers **E** (encodeur seul) ou **F** (format). Les leviers F sont prototypés dans l'encodeur, puis regroupés dans un seul **format v2**, avec leur coût pour le M3 chiffré.

## Étapes

| Étape | Contenu |
|---|---|
| P4.0 | infrastructure (corpus, comparaison, ABX) |
| P4.1 | A1 diagnostic des sons tonals ; A2 garde contre le remplacement par du bruit ; E1 point de reconstruction décalé (F) ; E2 zone morte selon la tonalité |
| P4.2 | codage entropique sans perte : D1 contextes, D2 vitesse d'adaptation, D3 énergies, D4 allocation prédite (F) |
| P4.3 | A3 tonalité par coefficient, B1 à B4 psychoacoustique v2 |
| P4.4 | E3 allocation optimisée débit-distorsion, E4 RDOQ avec le débit exact |
| P4.5 | C1 hystérésis M/S, C2 rotation par bande (F), C3 intensity (F) |
| P4.6 | si nécessaire : F1 `tf_change`, F2 bloc 512/1024, G1 niveau de bruit transmis |
| P4.7 | format v2 dans le C, CDF réentraînées (table 2), jeu de test, ABX, **G2** |

Le détail des leviers et des gains attendus figure dans le message de plan (conversation du 16/11/2026). Le journal des résultats est dans `eval/results/P4-LOG.md`.
