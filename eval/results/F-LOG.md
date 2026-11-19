# Robustesse de la v3 : fuzzing (19/11/2026, branche `refactor`)

Outils : `tools/fuzz/` (README), gcc seul (ni libFuzzer ni AFL sur la machine) : AddressSanitizer
et UndefinedBehaviorSanitizer qui s'arrêtent au premier rapport, couverture des arêtes par
`-fsanitize-coverage=trace-pc` (à la manière d'AFL).

## L'encodeur sur des entrées hostiles (`enc_edge.c`)

NaN, infinis, valeurs de 1e30, dénormaux, carrés pleine échelle, continu, saturation ×8, clics,
entrée vide et de 1 à 3 échantillons, à q −30, −7 et +10 ; chaque flux doit se décoder en
entier.

- **Trouvé** : un échantillon NaN atteint l'énergie d'une bande, et sa conversion en entier
  (comportement indéfini) donnait INT_MIN, puis un dépassement dans la prédiction des énergies.
  Un fichier source flottant abîmé suffisait. **Corrigé** : les échantillons non finis sont lus
  comme du silence (`pcm_sample`, `enc_int.h`), et l'énergie rejette NaN. Test ajouté
  (`tests/test_dec.py::test_damaged_input_samples`).
- Ensuite : les 34 cas s'encodent et se décodent en entier, sans rapport.

## Le décodeur, fuzzing guidé par la couverture (`fuzz_dec.c`)

Le décodeur tel que le firmware le compile (`MULE_NO_MALLOC`). Une entrée = un en-tête puis des
paquets, avec des recherches (seek) et des tampons de sortie trop courts ; chaque paquet dans
son propre bloc mémoire (une lecture au-delà est un rapport d'ASan) ; tampons de garde autour de
la sortie ; 2 s au plus par entrée. Graines : les vecteurs de test v3 et v2, et des extraits
synthétiques codés avec chaque variante d'en-tête (8 à 64 états, en chaîne ou non, 8 ou 16
symboles) à trois débits (103 graines).

- **Trouvé en 20 s** : un dépassement d'entier signé dans les additions de la FFT en virgule
  fixe, sur un flux malformé qui respecte pourtant toutes les bornes du format (énergies,
  allocations, magnitudes d'échappement énormes). Comportement indéfini en C ; le Cortex-M3
  faisait le tour (wrap), sans plantage. **Corrigé** : ces additions passent par `wadd` / `wsub`,
  le même tour mais défini. Aucune sortie ne change (vecteurs, empreinte et instructions QEMU
  identiques).
- **Campagne** : 8 instances × 30 minutes, **1 241 343 exécutions, aucun échec** (ni rapport
  des sanitizers, ni blocage, ni écriture hors du tampon, ni valeur de retour impossible).

Limite : la couverture plafonne vite (environ 420 arêtes, corpus de 103 à 123 entrées) ; sans
instrumentation des comparaisons, les mutations franchissent mal les contrôles exacts (en-tête,
état final du rANS). Comme une suite d'octets quelconque se décode en symboles, les chemins
profonds (énergies, allocations, échappements, synthèse) sont tout de même parcourus à chaque
paquet. La campagne de novembre sur le firmware (cible `mule`, v2, 549 287 exécutions après le
correctif des bornes) avait le même résultat.
