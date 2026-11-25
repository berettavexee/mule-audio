# EBU SQAM samples through MULE at `--bitrate 128`

Listen to MULE without building anything: 16 tracks of the EBU SQAM disc, encoded with the
current encoder and decoded by the reference decoder.

- `decoded/`: 16-bit / 44.1 kHz stereo FLAC, lossless copies of the WAV output of `mule-dec`,
  sample-aligned with the originals (same length, no delay to compensate).
- `mule/`: the encoded MULE files (Ogg container), to check the rates or decode them yourself.

Encoder: `mule-enc --bitrate 128 original.flac out.mule` (26/11/2026, format v5).
Decoder: `mule-dec in.mule out.wav`.

The originals are the tracks of the same number on the EBU SQAM disc (Sound Quality Assessment
Material, EBU Tech 3253), available from the EBU. They are not included: compare against your own
copy.

## About the bitrate

`--bitrate` works like opusenc's: VBR, with a slow rate leveler that pulls each track toward the
requested rate. Its quality-to-rate curve was calibrated on a music library. These SQAM items are
sparse (solo instruments, speech), so the encoder spends less than requested: **99 kb/s on
average** over the 16 files (file size, container and headers included).

| file | duration | rate |
|---|---|---|
| sqam05_pitch_pipe | 28 s | 24.0 kb/s |
| sqam08_violin | 71 s | 112.3 kb/s |
| sqam21_trumpet | 36 s | 89.6 kb/s |
| sqam27_castanets | 20 s | 100.0 kb/s |
| sqam32_triangles | 74 s | 97.8 kb/s |
| sqam35_glockenspiel | 59 s | 83.5 kb/s |
| sqam40_harpsichord | 53 s | 104.1 kb/s |
| sqam48_vocal_quartet | 28 s | 106.4 kb/s |
| sqam49_speech_female_english | 23 s | 95.7 kb/s |
| sqam50_speech_male_english | 22 s | 96.3 kb/s |
| sqam57_organ_bach | 20 s | 89.8 kb/s |
| sqam58_guitar_sor | 16 s | 99.7 kb/s |
| sqam60_piano_schubert | 92 s | 104.7 kb/s |
| sqam65_orchestra_strauss | 112 s | 113.9 kb/s |
| sqam69_abba | 33 s | 111.6 kb/s |
| sqam70_eddie_rabbitt | 21 s | 95.5 kb/s |

## Caveats

All the tuning was done with objective measures (Zimtohrli first, then PEAQ and a noise-to-mask
ratio) on music, not on SQAM; my own ABX tests at 128 kb/s could not tell MULE from the original.
Critical listening reports, good or bad, are exactly what I am looking for.
