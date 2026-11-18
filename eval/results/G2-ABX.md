# G2 : résultats d'écoute ABX

Kit : `data/listen/g2/`. Procédure : voir la conversation du 17/11 et `data/listen/g2/README.md`.
16 essais par paire. **12 bonnes réponses ou plus sur 16 = différence entendue** (p = 0,038).

Casque / interface : …
Niveau d'écoute : …

## Étape 1 : A (`mule160`) contre l'original

| Extrait | Score /16 | Entendu ? | Ce qui s'entend (si oui) |
|---|---|---|---|
| organ_bach | 10 | non (p = 0,23) | |
| glockenspiel | 9 | non (p = 0,40) | |
| triangles | **12** | **limite (p = 0,038)**, à refaire | |
| violin | 7 | non (p = 0,77) | |
| harpsichord | 6 | non (p = 0,89) | |
| castanets | 7 | non (p = 0,77) | |

Résultat (17/11, `data/listen/g2/results/*__mule160.txt`) : transparent sur 5 des 6 extraits. Triangles à 12/16, au seuil : 6 tests rendent un 12/16 isolé plausible par hasard (environ 21 %), donc un second passage s'impose.

## Étape 2 : B (`B160`) contre l'original

| Extrait | Score /16 | Entendu ? | Ce qui s'entend (si oui) |
|---|---|---|---|
| organ_bach | 11 | non (p = 0,11) | |
| glockenspiel | 4 | non (p = 0,99) | |
| triangles | 10 | non (p = 0,23) | |
| violin | 8 | non (p = 0,60) | |
| harpsichord | 8 | non (p = 0,60) | |
| castanets | 5 | non (p = 0,96) | |

Résultat (17/11, `*__B160.txt`) : **aucune différence entendue sur les 6 extraits**, triangles compris (10/16). Le point faible de B selon PEAQ ne s'entend pas ici.

## Étape 3 (facultative) : 128 kb/s contre l'original, et comparaisons entre codecs

| Extrait | Paire | Score /16 | Remarque |
|---|---|---|---|
| | mule128 / orig | | |
| | B128 / orig | | |
| | B160 / mule160 | | |
| | mule160 / opus160 | | |

## Verdict G2

- **A à 160 kb/s** : transparent sur 5 des 6 extraits critiques. Triangles à 12/16, au seuil, non confirmé (second passage à faire).
- **B à 160 kb/s** : transparent sur les 6 extraits critiques.
- **G2 (une seule oreille et une seule chaîne d'écoute)** : atteint pour B ; atteint pour A, sous réserve de confirmer les triangles.
- Adopter B comme format v2 : à décider (rien d'audible ne s'y oppose ; PEAQ le place devant A).
