# Evaluation

How MULE was measured. Every decision in the project was taken here: at equal real bitrate, on
excerpts never used for tuning, with bootstrap confidence intervals, and only when several
metrics agree. The logs of every measurement are in `results/` (in French).

The corpus is not included (EBU SQAM and a private library): `corpus.py` shows how it was cut,
the library's root in `MULE_LIBRARY`. Sets: `p0` (references), `dev` (66 excerpts, tuning),
`test` (30, never tuned on), `train` (200, initial CDFs only).

## The pipeline

| Script | What it does |
|---|---|
| `corpus.py`, `corpus_train.py` | build the excerpts (`data/corpus`, `data/train`) |
| `refcodecs.py` | one codec configuration by name (`mule[-variant]_<q>`, `opus_<kbps>`, `vorbis_q<q>`): encode, decode, rate |
| `metrics.py` | alignment, SNR, internal NMR, and PEAQ (GstPEAQ), ViSQOL, 2f, Zimtohrli when installed |
| `run_eval.py` | a set of configurations over a corpus set: `results/<tag>.csv` and a summary |
| `p4_compare.py` | two codec families at equal rate (interpolated per item), bootstrap intervals, regressions |

Typical use: `python eval/run_eval.py --set dev --tag mytest mule_-6 mule_-9 mule-v2_-6 mule-v2_-9`
then `python eval/p4_compare.py eval/results/mytest.csv --base mule-v2 --vs mule`.

## Tools for the format and the encoder

| Script | What it does |
|---|---|
| `train_cdf.py` | trains the initial CDFs (`py/mule/init_cdf.npz`, then `tools/gen_init_cdf.py`) |
| `ctx_lab.py` | entropy-coding experiments on the encoder's symbol trace: contexts, alphabets, adaptation (M-LOG, B-LOG, C-LOG) |
| `entropy_gain.py` | what the entropy coding is worth (the README's table) |
| `tcq_sim.py` | trellis sizes and chaining on a Laplacian model, before the codec (B-LOG) |
| `m6_tune.py`, `m6_validate.py` | CMA-ES tuning of the encoder settings, rate-bracketed, and its validation (M-LOG, B-LOG) |
| `frame_diag.py`, `mov_diag.py` | where MULE loses to Opus, window by window, and which PEAQ variables say so (D-LOG) |
| `mov_compare.py` | PEAQ's variables (MOVs) for any configurations, means, per item (`--per-item`) and what carries the ODG gap (N-LOG) |
| `bad_frames.py` | PEAQ's disturbed frames, frame by frame: which items, which frequencies (N-LOG) |
| `segment_odg.py` | PEAQ's ODG passage by passage (windows of a few seconds) (N-LOG) |
| `aac_frames.py` | what an AAC-LC encoder decided, read from its frames: block types, short-window groups, bandwidth, M/S, zeroed bands, frame sizes (N-LOG) |
| `gstpeaq-local.patch` | the local GstPEAQ changes these tools need (`PEAQ_MOVS`, `PEAQ_FRAMES`; LGPL-2 like GstPEAQ) |

## `archive/`

One-off scripts of past phases, kept as they were run (their import paths fixed). **Read one
before running it**: several have no options and start their work at once, and the listening kits
write into `data/listen/`.

| Script | Phase |
|---|---|
| `abx_kit_g3.py`, `abx_kit_g64.py` | listening kits G3 (128/160 kb/s, format v2) and 64 kb/s |
| `p4_diag.py`, `item_sweep.py`, `peaq_movs.py` | diagnostics of phases P4 and E (E-LOG, E2-LOG) |
| `ema_context_sim.py` | the M8 simulation (M-LOG) |
| `c_models.py` | model update every N symbols (C-LOG); needs the experiment's code, commit `05dd7a1` |

## Logs (`results/`)

`P0-REFERENCES`, `P1-BLOCKS`, `P2-ESTIMATE`, `P3-BITSTREAM`, `P4-LOG` (format v2), `E-LOG` and `E2-LOG` (encoder axes),
`G2-ABX`, `G3-ABX` (listening), `M-LOG` (measurements M1-M8), `B-LOG` (the trellis, format v3),
`C-LOG` (decoder cost), `D-LOG` (the gap to Opus), `H-LOG` (Haar, rejected), `F-LOG` (fuzzing).
