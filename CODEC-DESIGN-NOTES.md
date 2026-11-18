# Notes de conception — codec musique léger pour Echo Mini

Passation d'une discussion de conception (claude.ai, 15–16 nov. 2026) vers Claude Code.
À placer dans le dépôt `berettavexee/echo-mini-opus` (ou à référencer depuis `CLAUDE.md`).

## Contexte et contraintes

- Cible : lecteur Snowsky Echo Mini, **Cortex-M3** (pas de FPU, pas d'extension DSP/SIMD ; MUL 32 bits 1 cycle, `SMULL`/`SMLAL`, `UDIV` matériel), compilé avec GCC.
- Usage : **lecture de fichiers musicaux uniquement** (pas de temps réel, pas de vidéo, pas de pertes de paquets).
- Débit visé : **128–192 kb/s stéréo**, proche de la transparence.
- Asymétrie voulue : **encodeur lourd sur PC**, **décodeur minimal** sur la cible.
- Sources majoritairement en 44,1 kHz.

## 1. Conclusions sur Opus

- La musique passe par **CELT**. C'est **SILK** (et le mode hybride) qu'on peut retirer, pas CELT.
- Retirer SILK réduit la taille du code, mais ne fait rien gagner en CPU sur les trames CELT seules.
- Mode de chaque paquet, donné par l'octet TOC (`config = toc >> 3`) :
  - 0–11 : SILK
  - 12–15 : hybride
  - 16–31 : CELT seul

  Rejeter proprement ce qui n'est pas du CELT seul.
- `opusenc --music` à ≥ 64 kb/s stéréo produit en pratique du CELT seul. À vérifier en lisant les TOC.
- **44,1 kHz est impossible en Opus standard.** CELT est construit autour de 48 kHz, et l'API ne sort que 8, 12, 16, 24 ou 48 kHz. Un rééchantillonnage 48 → 44,1 coûterait du CPU au lieu d'en gagner. Opus Custom accepte 44,1 kHz, mais son flux est incompatible avec Ogg Opus.
- Priorité : passer le DAC/I²S en 48 kHz si le matériel le permet. Sinon, rééchantillonneur polyphase en virgule fixe (speexdsp, qualité 0 à 3).
- Compiler avec `FIXED_POINT` et `DISABLE_FLOAT_API`.

**Voie 0, le « profil Opus ».** On modifie l'encodeur pour qu'il produise uniquement du CELT seul en trames de 20 ms, sans préfiltre de hauteur. Le décodeur peut alors supprimer SILK, le mode hybride, les trames de 2,5 et 5 ms et le postfiltre. Les fichiers restent compatibles Ogg Opus.

## 2. Ce que l'usage « fichiers » permet d'abandonner

- **La faible latence.** On peut prendre des fenêtres longues à recouvrement complet (MDCT de 1024 ou 2048), puissance de 2 (FFT radix 4), et supprimer le pré-/postfiltre de hauteur. Les transitoires se traitent par commutation de blocs et/ou par `tf_change` par bande.
- **La résistance aux pertes.** On peut prédire plus fort d'une trame à l'autre et utiliser des modèles d'entropie adaptatifs, réinitialisés aux points de recherche (toutes les 1 à 2 s).
- **Le débit fixé paquet par paquet.** VBR libre, réservoir de bits, encodage en deux passes.
- **La fréquence imposée.** Grille de bandes paramétrée par la fréquence, avec 44,1 kHz natif.
- **L'allocation implicite.** On la transmet explicitement : le décodeur n'a plus rien à recalculer.

## 3. La voie Vorbis / Tremor

Vorbis répond déjà à la plupart de ces points : MDCT 256/2048, recouvrement complet, seek et lecture sans blanc gérés par Ogg, et un décodeur « bête » qui suit les décisions de l'encodeur. Tremor est entier, conçu pour ARM et utilisé par Rockbox. Son assembleur ARM est à porter en Thumb-2.

Le point faible : **les codebooks sont dans l'en-tête setup** et doivent être dépliés en RAM à chaque fichier.

Trois niveaux d'ambition :

1. **Profil Vorbis avec codebooks en ROM.** Le décodeur identifie le jeu de codebooks par hash du setup et utilise des tables précompilées, avec un repli si le jeu est inconnu. Les fichiers restent standards et on garde l'encodeur aoTuV. C'est **la référence à battre.**
2. **Vorbis modifié** (stéréo par bande, range coder) : incompatible, pour des gains modestes.
3. **Transformée Vorbis + quantification façon CELT** : un nouveau codec, avec un nouvel encodeur à écrire.

### Codebooks mesurés (libvorbis via libsndfile, stéréo)

| Qualité | Débit nominal | Codebooks | ROM estimée |
|---|---|---|---|
| q0–q3 | ~64–112 kb/s | 34–38 | 23–29 Kio |
| q4–q5 | ~128–160 kb/s | 42 | 28–29 Kio |
| q6–q10 | ~192–500 kb/s | 44 | 33–37 Kio |

| Plage | Codebooks uniques | ROM estimée |
|---|---|---|
| q5 seul | 42 | ~29 Kio |
| q4–q6 | 85 | ~75 Kio |
| q3–q8 | 136 | ~145 Kio |
| q0–q10 | 198 | ~225 Kio |

- 44,1 et 48 kHz ont des codebooks identiques, et le contenu audio n'a pas d'influence.
- 132 des 198 codebooks n'apparaissent qu'à un seul niveau de qualité.
- Le mono a son propre jeu (environ 125 codebooks de plus).
- Ces 25 à 37 Kio correspondent aussi à la RAM que Tremor alloue par fichier ouvert.
- Les jeux varient selon l'encodeur (libvorbis 1.0/1.3, aoTuV, Lancer) : garder l'identification par hash.
- Estimation de la ROM : mot de code 32 bits et longueur par entrée utilisée, index pour les codebooks creux, vecteurs VQ dépliés en int16.
- Outil : `vbooks.py` (voir plus bas).

## 4. Notes sur la PVQ

- Points de la PVQ = vecteurs entiers sur la boule L1 (hyperoctaèdre), projetés radialement sur la sphère. C'est une grille géodésique construite sur un polytope « pointu ».
- Écart de densité entre pôle et centre de face : environ N^(N/2). Mesuré avec K = 4N : ×5 pour N = 3, ×16 pour N = 4, ×10⁴ pour N = 8, ×10⁹ à 10¹¹ pour N = 16.
- **Pas de gain de remplissage de l'espace** par rapport au scalaire (réseau Zⁿ). Ses atouts sont structurels : conservation d'énergie, index sans table, débit réglable finement par K.
- CELT code l'index de façon uniforme. Daala l'a codé de façon non uniforme.
- **Projection en puissance de Duda** (x → x^p/‖x^p‖), gain annoncé ≥ 0,5 dB en erreur quadratique. Au décodeur, elle se réduit à une table de K entrées. Preprint jamais adopté par un codec.
- La densité plus forte aux pôles favorise peut-être les bandes tonales (intuition, pas de mesure).

### Alternatives à la PVQ

| Méthode | Conserve l'énergie | Finesse de débit | Coût du décodeur | ROM |
|---|---|---|---|---|
| PVQ (CELT) | oui | très fine | moyen (CWRS, normalisation) | quasi nulle |
| Scalaire + entropie contextuelle | si renormalisée | fine | faible | tables de contexte |
| Réseau RE8 (AMR-WB+, G.718) | non | par paliers | moyen (indexation) | faible |
| Arbre d'angles (theta récursif) | oui | fine | faible à moyen (tables trigo) | faible |
| TCQ | si renormalisée | fine | faible | faible |
| VQ entraînée (Vorbis, TwinVQ) | non | figée | faible | élevée |

## 5. Combinaisons retenues

**A, la plus prometteuse pour l'effort :**

- transformée Tremor (MDCT 2048/256, recouvrement complet, commutation de blocs, 44,1 kHz natif) ;
- énergies par bande à la CELT (grossière + fine), avec prédiction forte d'une trame à l'autre ;
- **quantification scalaire de la forme normalisée**, ramenée par le décodeur à l'énergie transmise, avec remplissage par bruit ou repliement ;
- **codeur arithmétique (ou rANS) à modèles adaptatifs**, sans tables statiques volumineuses ;
- allocation explicite.

L'interface « énergie + forme normalisée » permet de changer de quantificateur sans toucher au reste.

**B, le plafond le plus haut :** A avec une **TCQ à codage entropique (ECTCQ)** à la place du scalaire. Gain d'environ 1 dB en granularité, avec un décodeur léger. Le risque est dans la combinaison entre TCQ et codage par contexte.

**C, piste de recherche :** A avec une **PVQ améliorée** (theta récursif, projection de Duda, index codé de façon non uniforme).

**Ce qui pèse plus que le quantificateur :**

- l'encodeur : psychoacoustique, optimisation débit-distorsion, VBR en deux passes ;
- l'adaptation temps/fréquence par bande ;
- la stéréo par bande : M/S ou L/R, intensity dans les hautes fréquences.

**À éviter :**

- fenêtres longues + postfiltre de hauteur (redondant) ;
- allocation implicite avec un encodeur sophistiqué ;
- tables de contexte statiques volumineuses ;
- PVQ et réseau de points en même temps.

**Idées de Duda (2020) pour A :**

- modéliser les coefficients par une EPD avec κ ≈ 0,5 plutôt qu'une Laplacienne ;
- **prédire la largeur σ à partir du contexte** (environ 0,5 bit par valeur annoncé sur la DCT d'images JPEG, à vérifier sur la MDCT) ;
- dériver la quantification non uniforme d'une densité, avec un nombre impair de niveaux.

## 6. Plan de mesure

1. Mesurer le niveau 1 (Tremor avec codebooks en ROM) sur la cible : cycles par trame (`DWT->CYCCNT`), RAM maximale, temps d'ouverture d'un fichier.
2. Prototyper A en flottant sur PC.
3. Comparer à Vorbis aoTuV et à Opus à 128 et 160 kb/s, d'abord avec ViSQOL ou PEAQ, puis en ABX ou MUSHRA.
4. Porter en virgule fixe et mesurer les cycles sur la cible.
5. Remplacer le scalaire par la TCQ (B), en ne changeant que ce module.

## Outil : `vbooks.py`

Il nécessite `pip install soundfile numpy`.

- `python3 vbooks.py fichier.ogg ...` : affiche, pour chaque fichier, le nombre de codebooks, la taille du setup, un hash du jeu et une ROM brute.
- `python3 vbooks.py` sans argument : refait la mesure q0–q10 sur 44,1 et 48 kHz, en mono et en stéréo.

## Références

- Fischer, *A Pyramid Vector Quantizer*, IEEE Trans. IT, 1986
- Hamkins & Zeger, *Asymptotically Dense Spherical Codes I/II*, IEEE Trans. IT, 1997 : https://manuscript.isc.ac/Inventory/49/1401628.htm
- Valin et al., *High-Quality, Low-Delay Music Coding in the Opus Codec*, AES 2013
- Valin & Terriberry, *Perceptual Vector Quantization for Video Coding*, 2015 : https://arxiv.org/abs/1602.05209
- Svedberg et al., *MDCT Audio Coding with Pulse Vector Quantizers* (EVS), ICASSP 2015 : https://www.ericsson.com/en/reports-and-papers/research-papers/mdct-audio-coding-with-pulse-vector-quantizers
- Duda, *Improving Pyramid Vector Quantizer with power projection*, 2017 : https://arxiv.org/abs/1705.05285
- Duda, *Improving distribution and flexible quantization for DCT coefficients*, 2020 : https://arxiv.org/abs/2007.12055
- Duda, *Asymmetric Numeral Systems* : https://arxiv.org/abs/0902.0271, https://arxiv.org/abs/1311.2540
- Ragot, Bessette, Lefebvre, *Low-complexity multi-rate lattice VQ* (RE8), ICASSP 2004
- van der Ouderaa et al., *Pyramid Vector Quantization for LLMs*, 2024 : https://arxiv.org/abs/2410.16926
- Draft IETF Opus HD / QEXT : https://www.ietf.org/archive/id/draft-valin-opus-scalable-quality-extension-03.html
- Pistes d'implémentation : Opus Custom / CELT 0.11, Tremor (branche lowmem), libtremor de Rockbox, LC3/LC3plus, Musepack, Helix AAC

## Points d'attention

- **Brevets Ericsson** sur la recherche de forme et l'indexation MPVQ de la PVQ : privilégier l'indexation CWRS d'Opus, libre de droits.
- **Écosystème** : un format maison n'est lu nulle part ailleurs. Garder les originaux en FLAC et traiter ce format comme un transcodage pour l'Echo Mini.
