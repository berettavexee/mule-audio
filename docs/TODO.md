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

## v4 (branche `v4`)

- **Candidat actuel** (21/11/2026) : bruit dans les zéros des bandes codées (`nf_coded`,
  −6 dB), garde tonale (`tg`), bruit en pente dans les bandes remplies (`nf_slope`, dès 2,8 kHz,
  bornée à ±6 dB : `nf_slope_mode` 1 ; variante `sl6v4`).
- **Inclinaison transmise de la bande 21** (à essayer) : les règles fixes du 21/11 ont échoué
  (Max Richter monte vers 20 kHz, la plupart des extraits descendent) ; envoyer l'inclinaison de
  la bande 21 quand elle est remplie de bruit, 2 bits par trame longue et par canal (environ
  0,2 kb/s). Viser aussi les régressions ViSQOL de la pente sur Crystal Castles, Astroqueen et
  Dance with the Dead.
