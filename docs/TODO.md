# À faire

## Ce soir

1. **Installer clang** (à faire par toi, il faut les droits administrateur) :
   `sudo apt install clang` (libFuzzer est fourni avec : `clang -fsanitize=fuzzer`).
2. **Passer le fuzzing du décodeur à libFuzzer** (`tools/fuzz/`) :
   - le même harnais, avec un point d'entrée `LLVMFuzzerTestOneInput` à côté du moteur maison
     (qui reste pour les machines sans clang) ;
   - l'instrumentation des comparaisons (`-fsanitize=fuzzer` la fournit, plus
     `-use_value_profile=1`) : elle doit franchir les contrôles exacts que le moteur maison passe
     mal (en-tête, état final du rANS) et faire monter la couverture, qui plafonne aujourd'hui à
     environ 420 arêtes ;
   - un dictionnaire (`MULEHead`, octets de version et de drapeaux) ;
   - les graines de `tools/fuzz/mkseeds.py`, inchangées.
3. **Relancer une campagne** (8 instances × 30 minutes au moins, `-jobs=8 -workers=8`), sous
   ASan et UBSan, et consigner le résultat dans `eval/results/F-LOG.md`.

## Ensuite

- Publier `main` sur GitHub (export anonymisé) : la passe qualité, l'alignement de la qualité
  par défaut, les outils de fuzzing et les deux correctifs de robustesse n'y sont pas encore.
- Porter le décodeur v3 dans la branche Mule du firmware, puis mesurer RAM et charge sur
  l'appareil. À ce moment-là, reprendre l'idée du **prototype mémoire en 16 bits** (`acc`,
  `pend` : 10 à 15 Kio de RAM pour une erreur de l'ordre de l'arrondi final, environ 0,3 à
  0,5 LSB). Mis de côté le 19/11/2026 : le travail se fait sur PC pour l'instant. Il change la
  sortie normative du décodeur (nouveaux vecteurs de test).

## v4 (format figé le 21/11/2026, dans `main` depuis le 22/11, `docs/V4.md`)

- **Écoute ABX à 128 kb/s** : kit `data/listen/v4/` (MULE v4 contre l'original, contre AAC Apple),
  résultats dans `eval/results/V4-ABX.md`. À régénérer avant l'écoute (`eval/abx_v4.py`) : la garde
  d'enveloppe est entrée dans la production après l'écriture du kit.
- **Réglage Zimtohrli** (22/11/2026) : `low_db` est à la borne haute de l'espace de recherche (15) ;
  une recherche courte à bornes élargies pourrait aller plus loin.
- **Portage** du décodeur v4 dans la branche Mule du firmware, puis mesure sur l'appareil (QEMU :
  +3 à +7 % d'instructions par trame, +1,4 Kio de code, `docs/PORT.md` §8).
- **Inclinaison transmise de la bande 21** (idée non essayée) : envoyer l'inclinaison de la bande 21
  quand elle est remplie de bruit, 2 bits par trame longue et par canal (environ 0,2 kb/s), aucune
  règle fixe ne convenant à tous les extraits (Max Richter monte vers 20 kHz).
- Pistes refermées au gel (sondes retirées du code, résultats dans `eval/results/N-LOG.md`) :
  bandes plus fines, sous-partitions, suivi des raies, poids et zone morte dans la quantification,
  réglages du modèle psychoacoustique. Le clignotement des raies de la bande 20 venait surtout
  d'artefacts d'enregistrement (Beethoven 59 : 15 625 Hz, Takemitsu).

## v5 (figée le 22/11/2026, `docs/V5.md`)

- Retenus : repliement dans les trames courtes, niveau du bruit des zéros codé par un modèle ;
  dans l'encodeur, le détecteur d'attaques corrigé (mémoire à 1 dB par bloc), le détecteur des
  aigus à 6 dB, son veto tonal.
- Essayés et écartés (sondes retirées au gel, résultats dans `eval/results/N-LOG.md`) : bruit en
  pente centré sur les sommets, bruit qui suit l'enveloppe des bandes codées, bande source choisie,
  blocs de 512 et découpages mixtes (`docs/V5-512.md`), TF par bande, `hi_db`, `nf_gate`,
  critères de repliement par trame, coupure des groupes à l'attaque.
- À faire : porter le décodeur v5 sur l'appareil après la v4 (sous QEMU : +0,1 à +1,3 %
  d'instructions par trame contre la v4, `docs/PORT.md`).
- Ouvert : le pré-écho qui reste dans les trames courtes (environ 6 dB d'excès sur l'attaque de
  Garbage étudiée, avec ou sans coupure de groupe) relève des fenêtres, pas du regroupement ; la
  voix de femme (PEAQ −0,022, Zimtohrli mieux) peut être écoutée.
- Étude pour Opus : PVQ en treillis (`eval/pvq_trellis.py`) : +0,15 à +0,3 dB avec la pyramide
  K+1 pour demi-pas ; un vrai réseau décalé pourrait récupérer 0,2 à 0,5 dB de plus.
