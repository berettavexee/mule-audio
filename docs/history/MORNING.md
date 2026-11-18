# Résumé de la nuit (17/11/2026) — à lire en premier

## État

- **P4 terminé** côté mesures, sans aucun changement de format : le décodeur v1 et `spec/FORMAT.md` restent valables. Détail dans `eval/results/P4-LOG.md`.
- **Variantes B (ECTCQ) et C (PVQ) créées**, en Python (faisabilité) puis en C (encodeur + décodeur, en vrais flux), et évaluées. Détail dans `docs/VARIANTS-BC.md`.
- Tout est commité ; 126 tests passent (`make test`).

## Résultats principaux (jeu `test`, 30 extraits non vus, à débit égal)

| | ODG @128 | ODG @160 | ODG avancé @128 | @160 | ViSQOL @128 | NMR @160 |
|---|---|---|---|---|---|---|
| Vorbis | −0,449 | −0,164 | −0,631 | −0,339 | 4,474 | −3,0 |
| Opus | **−0,118** | **0,000** | −0,446 | −0,241 | 4,539 | −4,3 |
| MULE v1 (fin P3) | n.d. | −0,173 | n.d. | −0,283 | n.d. | −3,8 |
| **A** = MULE après P4 (format v1) | −0,299 | −0,090 | −0,481 | −0,203 | 4,601 | −5,7 |
| **B** = A + TCQ λ 0,3 (format expérimental) | −0,236 | −0,053 | **−0,425** | **−0,168** | **4,606** | **−6,3** |

- P4 améliore A de +0,083 d'ODG à 160 kb/s par rapport à v1, sur des extraits jamais vus.
- B améliore encore A de +0,04 à +0,06 d'ODG, sans régression, et dépasse Opus en ODG avancé, ViSQOL et NMR.
- Opus reste devant en ODG de base.
- C (PVQ) est moins bon que A, surtout sur les sons tonals : non retenu.

## Ce que je n'ai pas pu faire sans toi

1. **Écoute ABX (porte G2)** : le kit est dans `data/listen/g2/` (12 extraits × original + A et B à 128/160 + Opus/Vorbis 160, débits dans `rates.txt`, méthode dans `README.md`). Résultats à noter dans `eval/results/G2-ABX.md`.
2. **Décision : adopter B comme format v2 ?**
   - Pour : +0,04 à +0,06 d'ODG, coût négligeable pour le décodeur (machine à 8 états).
   - Contre : changement de format, CDF à réentraîner pour B (table 2), ABX à refaire.
   - Ma recommandation : oui, si l'ABX ne révèle rien de gênant sur B, en particulier sur les **triangles**, son point faible connu.

## Ce qui a été essayé et rejeté (mesures dans `P4-LOG.md`)

- point de reconstruction décalé ;
- contextes inter-trame lissés ou de fenêtre courte ;
- classes d'allocation ;
- vitesse d'adaptation (pire avec les CDF entraînées) ;
- rotation stéréo (−0,16 % d'entropie perceptuelle) ;
- allocation prédite par l'énergie ;
- post-masquage ;
- hystérésis M/S ;
- garde contre le remplacement par du bruit ;
- zone morte tonale ;
- échelle de tonalité ;
- RD à λ 1,0 et 1,4 ;
- réentraînement des CDF (−0,04 %).

## Incidents

- **Un plantage (SIGSEGV) de `mule-dec` pendant une évaluation, non reproduit** malgré 1 584 décodages, ASan/UBSan et un test de déterminisme. Le décodeur vérifie désormais les bornes des pages Ogg, et les évaluations conservent tout fichier fautif dans `eval/results/crash/` (vide depuis).
- Des processus orphelins d'un entraînement interrompu (manque de mémoire) bloquaient un sous-agent ; je les ai arrêtés.

## Outils ajoutés

- **Encodeur C** (`core/enc.c`), 50 à 58 fois plus rapide que Python, avec des opérations identiques (test).
- `eval/p4_compare.py` (comparaison à débit égal, avec intervalle de confiance) ;
- `eval/p4_rate.py` (variantes sans perte) ;
- `eval/p4_diag.py` (NMR par bande) ;
- `eval/abx_kit.py` ;
- corpus `dev`, `test` et `train` (`eval/corpus*.py`).
