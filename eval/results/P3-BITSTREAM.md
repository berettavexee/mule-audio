# P3 : vrai flux binaire, décodeur C de référence

Fichiers :
- **spécification** : `spec/FORMAT.md` (normative) ;
- **cœur C** : `core/` (`model.c`, `rans.c`, `dec.c`, `mule.h`, `init_cdf.h` généré par `tools/gen_init_cdf.py`) ;
- **encodeur** : `py/mule/encoder.py` (opérations de codage dans l'ordre du décodage), `py/mule/bitstream.py` (paquets rANS, Ogg) ;
- **outils** : `build/mule-dec` (Ogg vers WAV, `make`) et `tools/mule_enc.py` (FLAC/WAV vers `.mule`, tags recopiés).

## Ce qui est vérifié (`tests/test_bitstream.py`, 34 tests au total)

- **Aller-retour** sur 7 signaux difficiles (silence, bruit, clics, sinus L≠R, balayage mono, saturation, extrait de 3 000 échantillons), à deux qualités. La sortie du décodeur C égale la reconstruction de l'encodeur à < 1e-5 près (4e-8 en pratique, l'arrondi float32).
- **Débit réel = débit estimé** à ±2 % : 131,56 contre 131,55 kb/s sur les castagnettes, 144,70 contre 144,70 sur abba.
- **Paquets** ≤ 8192 octets (2,3 Kio au maximum sur les castagnettes). Le nombre de trames se retrouve exactement.
- **Seek** : à partir d'un paquet clé, avec deux paquets ignorés avant lui et sa première trame jetée, la sortie est identique au décodage continu (< 1e-6).
- **Fichier Ogg** valide pour `ogginfo` (CRC, structure). `mule-dec` restitue la longueur exacte (lecture sans blanc : pre_skip 1024, granule de fin), et l'écart avec la reconstruction de l'encodeur est de 1,5e-8.
- **Contrôle d'intégrité** à la fin de chaque paquet : état rANS revenu à 2^16 et tous les mots lus.

## Évaluation sur fichiers réels (`p3_real.csv`, décodage par `mule-dec`)

| à débit égal | ODG @128 | ODG @160 | ODG avancé @128 | @160 | ViSQOL @128 | @160 | NMR @128 | @160 |
|---|---|---|---|---|---|---|---|---|
| Vorbis | −0,479 | −0,243 | −0,511 | −0,250 | 4,548 | 4,641 | −3,51 | −5,92 |
| Opus | **−0,301** | **−0,170** | −0,451 | −0,228 | 4,512 | 4,630 | −3,92 | −6,18 |
| MULE, estimation P2 | −0,443 | −0,234 | −0,453 | −0,180 | 4,636 | 4,650 | −4,71 | −7,90 |
| **MULE, fichiers réels** | **−0,442** | **−0,234** | **−0,450** | **−0,179** | **4,636** | **4,650** | **−4,72** | **−7,92** |

Les conclusions de P2 tiennent sur de vrais fichiers : MULE atteint la qualité de Vorbis à 128 kb/s avec **123 kb/s** (ODG de base et avancé). Pour égaler Opus à 128, il faut 149 kb/s en ODG de base et 128 kb/s en ODG avancé.

Le passage de l'estimation au réel s'accompagne de deux changements :
- les échappements des énergies et de l'allocation passent par un préfixe adaptatif (`eaesc`) ;
- le bruit des bandes non codées vient d'un LCG spécifié.

Aucun des deux ne change le résultat.

## Taille pour Cortex-M3 (`make m3size`, `-Os` Thumb-2, flottant : indicatif)

| Objet | .text |
|---|---|
| `dec.o` (syntaxe, reconstruction, IMDCT) | 4,4 Kio |
| `model.o` | 0,6 Kio |
| `rans.o` (CDF initiales et encodeur rANS, qui n'ira pas sur la cible) | 18 Kio en v0, **4,9 Kio en v1** |

Ce qu'il faudra changer pour la cible, en P6 :
- accumulateurs en double, soit 48 Kio : passer en int32 ou int16 ;
- ~~518 modèles de 36 octets (18,6 Kio)~~ : **134 modèles, soit 4,8 Kio de RAM, depuis la v1** ;
- FFT : remplacer `cos`/`sin` à la volée par des tables, ou utiliser l'accélérateur MDCT matériel ;
- `pow`/`sqrt` par bande : passer par des tables `2^(i/4)` et une `rsqrt` entière.

## Format v0 : points à revoir avant de le figer

- ~~Compacter les contextes `coef` (480 → 96)~~ : **fait**, format v1. Les paquets sont identiques au bit près (SHA-1) ; le décodeur vérifie la version et l'identifiant des tables (octet 19).
- Prendre en charge le mono, et des fréquences autres que 44,1 kHz, si besoin.
- Ajouter un CRC par paquet ? La page Ogg en porte déjà un.
