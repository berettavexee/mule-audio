# The encoder's settings

*Version française : [ENC-PARAMS.fr.md](ENC-PARAMS.fr.md).*

As of 24/11/2026. This document lists the fields of `mule_enc_params` (`core/mule_enc.h`): what each
one does, its production value (`mule_enc_defaults`, `core/enc.c`) and where that value comes from.
`py/mule/params.py` (`Params`) mirrors the same fields for Python; `py/mule/native.py` copies them
into the C structure.

**None of this is part of the format.** The decoder ignores these settings, except three that set
header flags (`tcq_states`, `tcq_chain`, `coef_a8`, see *Quantization*). All the others can be
changed without touching the decoder or the firmware.

**How to read the "origin" column.** Dates refer to the logs in `eval/results/` (mostly
`N-LOG.md`; also `E-LOG.md`, `E2-LOG.md`, `B-LOG.md`, `M-LOG.md`, `P4-LOG.md`). "Prototype" means
the value comes from the first Python encoder and was never measured on its own since. "Probe"
marks a setting added for an experiment and off by default, because the experiment gave nothing or
is not finished.

## The command line's two modes

`tools/mule-enc` always starts from `mule_enc_defaults`, then:

- **`-q dB`** (pure quality VBR) sets `q_db` only. The rate follows the music.
- **`--bitrate N`** (default 128, as in `opusenc`): `params.for_bitrate(N)` overrides five values:

  | field | value | `mule_enc_defaults` |
  |---|---|---|
  | `q_db` | −9.21 × log2(N / 76.4) | −7 |
  | `rc_k` | 2 | 0 (leveler off) |
  | `rc_max` | 15 dB | 9 dB |
  | `opa_mode` | 3 (mix with Opus's table) | 0 |
  | `opa_alpha` | 0.75 | 0.5 |

  Adopted on 23/11 (leveler) and 24/11/2026 (C75 mix), on the 300-track campaign.

The "default" values below are those of `mule_enc_defaults`. For `--bitrate`, apply the table above
on top of them.

## Quality and rate

| field | role | default | origin |
|---|---|---|---|
| `q_db` | Noise target relative to the masking threshold: the quality setting. Lower = more bits. | −7 | About 128 kb/s on a music library (`tools/mule_enc.py`). With `--bitrate`, computed from the R(q) curve. |
| `rc_k` | Rate leveler: each frame moves `q_db` by `rc_k × rc_slope × log2(R / R(q))`, R being the smoothed rate. Draws each track toward the requested rate; the spread in log is divided by 1 + `rc_k`. | 0 (off); 2 with `--bitrate` | 300-track campaign, 23/11/2026. |
| `rc_tau` | The leveler's rate smoothing (frames). | 200 (4.6 s) | Chosen at design time, not swept. |
| `rc_max` | The leveler's largest move of `q_db` (dB). | 9; 15 with `--bitrate` | 15 chosen among the `rc*m15` variants of `refcodecs` (23/11/2026). |
| `rc_r0` | Curve R(q) = `rc_r0` × 2^(−q / `rc_slope`): a setting's mean rate. | 76.4 kb/s | Fit on the 300-track campaign (23/11/2026). |
| `rc_slope` | That curve's slope (dB of `q_db` per doubling of the rate). | 9.21 | Same fit. |
| `opa_mode` | Opus's per-band allocation table (CELT `band_allocation`, BSD), at rate `opa_kbps`. 1: replaces the masks; 2: takes only its tilt; 3: geometric mix with the masks. | 0; 3 with `--bitrate` | Mode 3 adopted on 24/11/2026 (better on every judge at 96/128/160 kb/s, 300 tracks). |
| `opa_kbps` | Rate at which to read the table. | 0 = R(`q_db`) | — |
| `opa_eta` | Share of half the rate given to one channel's coefficients (the table's calibration). | 0.8 | Chosen at design time, not swept. |
| `opa_k` | Mode 2: the tilt's scale. | 1 | Mode 2 not adopted. |
| `opa_alpha` | Mode 3: the (log) share of our masks; the rest comes from Opus's table. | 0.5; 0.75 with `--bitrate` | Grid on *dev*, confirmed on *test* then on the 300 tracks (C75, 24/11/2026). The CMA-ES search of 24/11 suggests ~0.67 at 96 kb/s (to be validated). |
| `opa_ton_k` | Mode 3: our masks' share moved by `opa_ton_k` × (t − 0.15), t the frame's mean tonality (exhale's idea). | 0 (off) | Probe of 26/11/2026, rejected both ways (`B9-REPORT.md` 12). |

## Frames, short blocks and groups

| field | role | default | origin |
|---|---|---|---|
| `keyframe` | Frames between two key packets (multiple of 4). Rate cost against seek time. | 40 (0.93 s) | `M-LOG.md`: 80 and 160 frames save only 0.17 and 0.26 % of the rate. 40 kept. |
| `tr_db` | Transient detector: energy rise above its memory (dB). | 8.5 | 10 before 20/11/2026 (`N-LOG.md`). |
| `tr_decay_db` | The detector's memory decay per block of 128. | 1 dB | 3 before 22/11/2026: a voice's glottal pulses were taken for attacks (`N-LOG.md`). |
| `tr_pitch` | Pitch veto (exhale's pitch-lag test): an attack block whose filtered signal repeats itself one period earlier (normalised correlation above this threshold, periods of 1.5-20 ms) is not an attack. 0: off. | 0.7 | Adopted on 26/11/2026 with `tns_k` (`B9-REPORT.md` 11, 15, 16). Fixes pitchpipe (−3.9 → +0.1 ODG). 0.5 loses real attacks (castanets, organ). |
| `tns_k` | TNS's prediction gain as a temporal cue (exhale), without the filter: in a long frame, a band of at least 16 coefficients whose order-4 LPC over frequency predicts G dB has its masks lowered by `tns_k` × (G − 1.5) dB, 6 dB at most. 0: off. | 1 | Adopted on 26/11/2026 (13, 16): voices −12 to −16 % Zimtohrli distance; piano slightly down on PEAQ basic. 3: violin +26 %. |
| `tr_hf` | A second detector pass on the high-passed signal. | 1 | 22/11/2026 (`N-LOG.md`). |
| `tr_hf_fc` | That high-pass's cutoff. | 8000 Hz | Same series. |
| `tr_hf_db` | That pass's threshold. | 6 dB | 8.5 before v5 (the corrected detector, `N-LOG.md`). |
| `tr_hf_ton` | Tonal veto: a frame made short by the highs pass alone stays long if its bands 12-21 are flatter than −`tr_hf_ton` dB. | 10 dB | v5 (the Belenos case, `N-LOG.md`). |
| `groups` | Short frames: 0 adaptive grouping, 8 one energy per block, 1 a single group. | 0 | Prototype; adaptive confirmed in `N-LOG.md`. |
| `group_mode` | Adaptive grouping: 0 the window's energy only, 1 also per frequency region. | 1 | 20/11/2026 (`N-LOG.md`). |
| `group_db` | Energy jump that opens a new group. | 12 dB | 6 before `group_mode` 1 (20/11/2026, `N-LOG.md`). |
| `short_db` | Noise target offset in short frames (< 0: more bits). | 0 | Probe (Lebanon Hanover, `N-LOG.md`), no gain. |

## Psychoacoustic model (the per-band masks)

| field | role | default | origin |
|---|---|---|---|
| `ath_db` | Shift of the absolute threshold in quiet. | 0 | Lever G (`refcodecs` `athm6` … `athp6`), no gain. |
| `ath_rel_db` | Relative threshold in quiet (Vorbis/LAME style): lowered in quiet passages, by `ath_rel_db` at most. | 0 (off) | Probe of 23/11/2026. |
| `ath_ref_db` | That relative threshold's reference level. | −14 dBFS | A loud passage of music. |
| `ath_rel_rel` | The level follower's fall. | 0.5 dB/frame (22 dB/s) | Chosen at design time. |
| `tonal_all` | Every masker treated as tonal. | 0 | Prototype (comparisons only). |
| `fft_tonal` | Tonality from the flatness of a Hann FFT spectrum (else from the MDCT). | 1 | P4 axes (`P4-LOG.md`). |
| `fft_noise_db` | Reference flatness of noise in that spectrum. | 3.4 | Zimtohrli tuning, 22/11/2026 (4 before; CMA-ES, `N-LOG.md`). |
| `ton_scale` | Flatness (dB below noise's) of a fully tonal band. | 20 | Prototype. |
| `tcap_db` | Cap of the tonal masking offset 14.5 + z. ≤ 0: no cap. | 15.3 | Zimtohrli tuning, 22/11/2026 (25 before). |
| `low_db` | Extra masking offset in bands 0-7 (< 1.4 kHz). | 15 | Zimtohrli tuning, 22/11/2026 (10 before). |
| `mid_db` | The same in bands 8 to `mid_hi` − 1 (1.4 to 8 kHz). | 6.1 | Zimtohrli tuning, 22/11/2026 (4 before, `P4-LOG.md`). |
| `mid_hi` | End of the `mid_db` zone. | 17 | `P4-LOG.md`. |
| `spread_mode` | Mask spreading: 0 Schroeder, 1 Terhardt (level-dependent), 2 the minimum, 3 Schroeder then Terhardt beyond `sp_dz`. | 3 | 20/11/2026 (`N-LOG.md`); 0 before. |
| `sp_dz` | Mode 3: Schroeder up to this distance above the masker (Bark). | 2 | Same series. |
| `fine_p` | Fine masks in long frames: sub-bands of `fine_w` lines, the band's target being their power mean of exponent −`fine_p`. 0: off. | 8 | Axis 1 (`E-LOG.md`, combination lf8n12r05, confirmed on *test*). |
| `fine_w` | Lines per sub-band. | 1 | Same axis. |
| `fine_nb` | Fine masks below this band only. | 12 | Same axis. |
| `pre_db` | Pre-echo control (AAC's rpelev): a long frame's mask is at most `pre_db` above the previous one's. | 9.7 | Axis 2 (`E2-LOG.md`, 10), then the Zimtohrli tuning of 22/11/2026. |
| `dyn_a` | Opus dynalloc style: masks lowered by the band's excess over the lower envelope. | 0 (off) | Probe, no gain. |
| `bf_rel_db` | Band floor: a band within `bf_rel_db` of the strongest gets a mask at most `bf_snr_db` under its power. | 0 (off) | Probe of 23/11/2026 (the `bf*` variants of `refcodecs`), no gain. |
| `bf_snr_db` | See above. | 0 | — |
| `hf_db` | High-band tilt: masks raised along a ramp up to `hf_db` in the last band. | 0 (off) | Probe of 24/11/2026, no gain. |
| `hf_band` | The ramp's first band. | 16 | — |

## Stereo

| field | role | default | origin |
|---|---|---|---|
| `stereo` | 0 automatic (L/R or M/S per band, by perceptual entropy), 1 L/R, 2 M/S. | 0 | Prototype; `refcodecs` `lr`, `ms` for comparisons. |

## Allocation (bits per band)

| field | role | default | origin |
|---|---|---|---|
| `alloc_auto` | Reference for coding the allocations: the cheaper of the previous band and the previous frame (else per band). | 1 | Prototype. |
| `alloc_hyst` | Keep the previous frame's allocation if the new one differs by at most `alloc_hyst` (fewer allocation bits, less flicker). | 1 | Prototype; see `N-LOG.md`. |
| `rd_lambda` | Rate-distortion choice per band between a−1, a and a+1: (noise/mask) + λ × bits, the bits counted on a copy of the adaptive models. 0: off. | 2.42 | Axis 3 (`E-LOG.md`, 2), then the Zimtohrli tuning of 22/11/2026. |
| `alloc_trellis` | That choice made by one Viterbi over the bands (exhale's scale-factor trellis) instead of band after band. | 0 (off) | Probe of 26/11/2026, rejected: all four judges worse, encoder 1.6 times slower (14). |
| `zh_db` | On/off hysteresis: a band noise-filled in the previous frame is coded only if its energy exceeds its target by `zh_db`. | 0 (off) | Probe of 24/11/2026 (Purcell): ±1 % effects, not adopted. |
| `zh_keep_db` | A coded band goes back to noise only if its energy falls `zh_keep_db` below its target. | 0 (off) | Same probe. |

## Quantization (TCQ) and coding

The first three set the header: changing them gives a stream the decoder reads, but they are no
longer the production v5 settings. They are for comparisons.

| field | role | default | origin |
|---|---|---|---|
| `tcq_states` | Trellis of 8, 16, 32 or 64 states (header byte 20). | 64 | Format v3 (`B-LOG.md`, `C-LOG.md`). |
| `tcq_chain` | The trellis state runs on from band to band within a group: one Viterbi (flag `MULE_TCQ_CHAIN`). | 1 | Format v3. |
| `coef_a8` | Coefficient alphabet of 8 symbols, escape at 7 (flag `MULE_COEF_A8`). | 1 | Format v3. |
| `tcq_rd` | The Viterbi counts the rate with the tracked models (contexts, escapes, sign). Needs `rd_lambda` > 0. | 1 | Axes 1 and 3 (`E-LOG.md`). |
| `tcq_rdl` | Weight of the rate in that Viterbi, relative to the allocation's. | 0.48 | `E-LOG.md` (0.5), then the Zimtohrli tuning of 22/11/2026. |
| `tcq_lam` | Weight of the rate in the Viterbi when `tcq_rd` = 0 (unused in production). | 0.3 | `M-LOG.md`, `VARIANTS-BC.md`. |
| `tcq_rd_states` | Speed: a smaller trellis for the rate-distortion choice's estimates. 0: `tcq_states`. | 8 | `B-LOG.md`: encoder twice as fast, same quality. |

### `rd_lambda` and `tcq_rdl`: two rate-distortion trade-offs

The encoder decides in two steps, and each one weighs bits against noise:

1. **Allocation**, band by band: each band's resolution `a`. The choice between a−1, a and a+1
   minimizes `noise / mask + rd_lambda × bits`.
2. **Trellis quantization (TCQ)**, coefficient by coefficient: the Viterbi looks for the sequence
   of levels that minimizes `distortion + λ × bits`, the bits counted with the entropy coder's
   adaptive models (`tcq_rd` = 1).

`tcq_rdl` sets the Viterbi's λ relative to the allocation's (`core/enc_tcq.c`):

    λ = tcq_rdl × rd_lambda × (the band's noise target) / (quantization step)²

So the bits are weighed in the same units, noise relative to the mask, as in the allocation.

- **Low `tcq_rdl`** (toward 0): the Viterbi favours precision and takes the levels closest to the
  signal, even costly ones.
- **High `tcq_rdl`**: it accepts a little more error to save bits. It prefers small levels and
  zeros, which are cheaper, and the zeros are then noise-filled (`nf_off_db`).

At equal rate, the bits saved in the Viterbi go back to the allocation, which can code more bands
or code them more finely. The CMA-ES search of 24/11 (`--bitrate` mode) raises `tcq_rdl` from 0.48
to 0.60-0.66 at 96 and 128 kb/s, together with louder noise filling: more bands covered, with
slightly coarser coefficients. To be validated.

## Empty bands and noise filling

| field | role | default | origin |
|---|---|---|---|
| `nf_off_db` | Level of the noise that replaces the zero coefficients of a coded band: the measured level plus this offset. | −6 dB | v4 (`N-LOG.md`). The CMA-ES search of 24/11 suggests ~−4.3 at 96 kb/s (to be validated). |
| `nf_bias` | Energy of noise-filled bands sent `nf_bias` steps of 1.5 dB lower. | 1 | 21/11/2026: Zimtohrli better, ViSQOL worse, adopted by the author (`N-LOG.md`; first trial in `E2-LOG.md`). |
| `nf_top` | From this band up, a band at allocation 0 is sent silent instead of noise-filled. | `MULE_NB` (22: never) | Probe (`code*`, `N-LOG.md`). |
| `tg` | Zero-bit tonal bands: 1 guard (the band gets `tg_a` if its strongest line is within `tg_db` of the target), 2 silent, 0 off. | 1 | Format v4 (`N-LOG.md`). |
| `tg_db` | Guard: margin of the strongest line under the target. | 6 dB | `N-LOG.md` (sweep `tg1d0` … `tg1d18`). |
| `tg_a` | Guard: the allocation given. | 1 | `N-LOG.md`. |
| `tg_band` | Guard: from this band up only. | 0 | `N-LOG.md` (`tg1b19`, `tg1b20` without gain). |
| `tg_ton` | A lone line: the band's strongest exceeds by this many dB that of a noise with the same number of lines (2 ln n × mean). | 5 dB | `N-LOG.md`. |
| `eg` | Envelope guard (Garbage): in a long frame, a band at allocation 0 from `eg_band` up is coded at `eg_a` if its energy over the 8 short blocks peaks `eg_db` above its mean. Noise filling is stationary over the window. | 1 | 21/11/2026 (`N-LOG.md`). |
| `eg_band` | See above. | 16 | Same series (`eg6b12`, `eg6b19`). |
| `eg_db` | See above. | 5 dB | 6 at first; 5 adopted with `nf_bias` 1 (`N-LOG.md`, Zimtohrli). |
| `eg_a` | See above. | 1 | Same series (`eg6a2` without gain). |

## The settings that were actually tuned

Most values above were set once, on one measurement, and have not moved since. Eight of them were
tuned together by CMA-ES against Zimtohrli on 22/11/2026 (`low_db`, `mid_db`, `tcap_db`,
`fft_noise_db`, `rd_lambda`, `tcq_rdl`, `pre_db`, then `eg_db` with `nf_bias`). A new search, in
`--bitrate` mode at 96, 128 and 160 kb/s, is running on 24/11/2026 (`eval/m6_tune.py --space b9`).
It covers the seven psychoacoustic settings plus `opa_alpha` and `nf_off_db`.

Values chosen without a dedicated measurement, candidates for further search: `ton_scale`,
`opa_eta`, `rc_tau`, `alloc_auto`, `ath_rel_rel`.

## Adding a setting

1. The field and its documentation in `core/mule_enc.h`, at the end of the structure. The cffi
   binding reads the structure from this file: there is no second definition to keep in sync.
2. The production value in `mule_enc_defaults` (`core/enc.c`), and its validation in `params_ok`
   if it has a domain.
3. The field in `Params` (`py/mule/params.py`) and its copy in `py/mule/native.py`.
4. The measurement variants in `VARIANTS` (`eval/refcodecs.py`).
5. A line in this document and in its French version.
