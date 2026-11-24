/* MULE encoder API (core/enc.c and its modules, core/enc_int.h). The settings below, their
 * production values in mule_enc_defaults; py/mule/params.py mirrors them for Python. */
#ifndef MULE_ENC_H
#define MULE_ENC_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    /* the format's choices (the Python prototype makes the same, rd_lambda, tcq_rd, fine_p and
     * pre_db off) */
    double q_db;        /* noise target relative to the masking threshold (quality) */
    int keyframe;       /* frames between key packets (multiple of 4; 40) */
    int groups;         /* short frames: 0 adaptive, 8 one per block, 1 single group */
    double group_db;    /* adaptive grouping threshold (12 dB; 6 before group_mode 1) */
    int stereo;         /* 0 auto (per band, perceptual entropy), 1 L/R, 2 M/S */
    double ath_db;      /* threshold in quiet shift (0) */
    int tonal_all;      /* psy: every masker tonal (0) */
    double low_db;      /* extra masking offset in bands 0-7 (15 dB; 10 before 22/11/2026) */
    double mid_db;      /* extra masking offset in bands 8 .. mid_hi-1 (6.1 dB; 4) */
    int mid_hi;         /* (17) */
    double ton_scale;   /* flatness (dB below noise's) of a fully tonal band (20) */
    double tcap_db;     /* cap of the tonal masking offset 14.5 + z (15.3 dB, 25 before 22/11/2026; <= 0: none) */
    int alloc_auto;     /* allocation reference: per group, band or frame (else band; 1) */
    int alloc_hyst;     /* keep the previous frame's a_b within +-alloc_hyst (1) */
    /* C encoder only (P4, axes 1 to 3: eval/results/P4-LOG.md, E-LOG.md, E2-LOG.md) */
    int fft_tonal;      /* tonality from the flatness of a Hann FFT power spectrum (1) */
    double fft_noise_db; /* flatness of noise in that spectrum (3.4; 4) */
    double rd_lambda;   /* > 0: per band, choose a-1, a, a+1 by (noise/mask) + lambda * bits, the
                         * bits from a copy of the adaptive models (exact costs; 2.42, 2 before 22/11/2026); 0 off */
    double tcq_lam;     /* TCQ Viterbi rate weight without tcq_rd ((D/2)^2 units; 0.3) */
    int tcq_rd;         /* 1: the Viterbi's rate from the tracked models (contexts from each
                         * survivor's tails, inter-frame context, escapes, sign), levels nearest
                         * and +-4; needs rd_lambda > 0 (1) */
    double tcq_rdl;     /* with tcq_rd: rate weight relative to the allocation's (0.48; 0.5) */
    double fine_p;      /* > 0: long frames' band targets from fine_w-line sub-band masks (Bark
                         * density spreading, the band's tonality), their power mean of exponent
                         * -fine_p (8); 0 off */
    int fine_w;         /* lines per sub-band (1) */
    int fine_nb;        /* fine masks below this band only (12; 0: all) */
    double pre_db;      /* > 0: pre-echo control (AAC's rpelev): a long frame's mask at most this
                         * many dB above the previous long frame's (9.7; 10); 0 off */
    int nf_bias;        /* noise-filled bands' energy sent this many 1.5 dB steps lower (1 since
                         * 21/11/2026: Zimtohrli better, ViSQOL worse, adopted by the author,
                         * N-LOG.md; E2-LOG.md for the first trial) */
    int tcq_states;     /* trellis of 8, 16, 32 or 64 states (64; header byte 20) */
    int tcq_chain;      /* 1: the trellis state runs on across a group's bands, one Viterbi over
                         * them (needs tcq_rd and rd_lambda); 0: restarted at 0 in each band, for
                         * comparisons only (1; header flag MULE_TCQ_CHAIN) */
    int coef_a8;        /* coefficient alphabet of 8 symbols, escape at 7; 0: 16 symbols, escape
                         * at 15, for comparisons only (1; header flag MULE_COEF_A8) */
    int tcq_rd_states;  /* encoder speed: the trellis of the RD choice's per-band estimates
                         * (a-1, a, a+1), 8 to 64; 0: tcq_states (8) */
    int tg;             /* zero-bit tonal bands (eval/results/N-LOG.md): 1 guard (production, v4):
                         * the band gets allocation tg_a if its strongest line is within tg_db of
                         * the mask target; 2 muted: sent silent instead of noise; 0 off (1) */
    double tg_db;       /* guard: the strongest line at least the target minus this (dB; 6) */
    int tg_a;           /* guard: the allocation given (1 .. MULE_AMAX, else refused; 1) */
    int tg_band;        /* guard: from this band up only (0) */
    int spread_mode;    /* psy band masks: 0 Schroeder's spreading, 1 Terhardt's (level-dependent),
                         * 2 the smaller of the two, 3 Schroeder then Terhardt beyond sp_dz (3;
                         * 0 before 20/11/2026) */
    double sp_dz;       /* spread_mode 3: Schroeder's spreading up to this many Bark above (2) */
    double dyn_a;       /* > 0: masks lowered by dyn_a times a band's excess over the lower
                         * envelope of the band levels (Opus' dynalloc criterion; 0: off) */
    double nf_off_db;   /* v4: the zero coefficients' noise level, the measured one plus this (dB; -6) */
    int nf_top;         /* from this band up, a band at allocation 0 is sent silent instead of
                         * noise-filled (MULE_NB: none) */
    int group_mode;     /* adaptive grouping: 0 the window's energy only, 1 also per frequency
                         * region (1; eval/results/N-LOG.md) */
    double tr_db;       /* transient detector: energy rise over its decaying memory (8.5 dB;
                         * 10 before 20/11/2026, eval/results/N-LOG.md) */
    double short_db;    /* noise target offset in short frames (0 dB; < 0: more bits) */
    int eg;             /* envelope guard (N-LOG.md, Garbage): in a long frame, a band left at
                         * allocation 0 from eg_band up is coded at eg_a instead of noise-filled when
                         * its energy over the 8 short blocks of the window peaks eg_db above its
                         * mean (noise filling is stationary over the window; 1, production; 0: off) */
    int eg_band;        /* (16) */
    double eg_db;       /* (5) */
    int eg_a;           /* (1) */
    double tg_ton;      /* a lone line: the band's strongest coefficient this many dB above the
                         * strongest of a noise of the same lines, 2 ln n times the mean (5) */
    int tr_hf;          /* a second transient detector pass on the signal high-passed at tr_hf_fc,
                         * threshold tr_hf_db, its attacks added (1 since 22/11/2026, 0 before) */
    double tr_hf_fc;    /* (8000 Hz) */
    double tr_hf_db;    /* (6 dB since the v5; 8.5 before) */
    double tr_hf_ton;   /* tonal veto: a frame only the highs pass made short stays long if its bands
                         * 12-21 (2.8-17 kHz, FFT of the mid) are flatter than -tr_hf_ton dB (10; 0: off) */
    double tr_decay_db; /* the detector's memory decay per block of 128 (1 dB since 22/11/2026, 3 before:
                         * a voice's glottal pulses were taken for attacks, N-LOG.md) */
    /* Relative threshold in quiet (Vorbis' ath_adjatt, LAME's adaptive ATH): the ATH is calibrated
     * for full scale at 96 dB SPL, but a quiet passage is played louder; with ath_rel_db > 0 it is
     * lowered by ath_ref_db minus the passage's level (dBFS, mean square of the frame's 2048
     * samples, both channels; a follower that rises at once and falls ath_rel_rel dB per frame),
     * by ath_rel_db at most, never raised (0: off, the absolute ATH) */
    double ath_rel_db;
    double ath_ref_db;  /* (-14 dBFS: a loud passage of music) */
    double ath_rel_rel; /* (0.5 dB per frame: 22 dB/s) */
    /* Band floor (Opus' energy-normalised allocation, Vorbis' noise floor relative to the frame's
     * peak): with bf_rel_db > 0, a band whose power per coefficient is within bf_rel_db of the
     * strongest band's of its channel and group gets a mask at most bf_snr_db under its own power
     * (so a noise target of at most bf_snr_db - q_db under it), whatever its absolute level and the
     * threshold in quiet (0: off) */
    double bf_rel_db;
    double bf_snr_db;
    /* Rate leveler (Opus' constrained VBR, Vorbis' bitrate management, softened): with rc_k > 0,
     * each frame's q_db is moved by rc_k x rc_slope x log2(R / R(q_db)), at most rc_max dB either
     * way, where R is the rate so far smoothed over rc_tau frames and R(q) = rc_r0 2^(-q / rc_slope)
     * kb/s the mean rate of the setting on a music library: a track's rate is drawn toward the
     * setting's (its spread in log divided by 1 + rc_k), the quiet sparse tracks get more bits,
     * the dense loud ones fewer (0: off, quality VBR) */
    double rc_k;
    double rc_tau;      /* (200 frames: 4.6 s) */
    double rc_max;      /* (9 dB) */
    double rc_r0;       /* (76.4 kb/s, the 300-track campaign's fit, 23/11/2026) */
    double rc_slope;    /* (9.21 dB of q_db per doubling of the rate) */
    /* Opus' band allocation (CELT's band_allocation table, libopus celt/modes.c, BSD; MULE's
     * bands 0-20 are CELT's): for the target rate opa_kbps (0: R(q_db), the rate curve above),
     * the table's rows interpolated so that the bits of a channel's coefficients make opa_eta of
     * half the rate, with CELT's default trim (alloc_trim 5 at LM 3), as bits per coefficient
     * T[b]; band 21 extrapolated. opa_mode 1: the masks replaced by the band's power over
     * 10^(0.602 T[b]) (Opus' energy-normalised allocation, at q_db's noise target); 2: the masks
     * moved by opa_k times the change of the table's shape from 128 kb/s to the target rate (its
     * mean over the coefficients removed: the tilt only); 3: the geometric mix, opa_alpha of the
     * masks and the rest of mode 1's (0: off) */
    int opa_mode;
    double opa_kbps;
    double opa_eta;     /* (0.8) */
    double opa_k;       /* (1) */
    double opa_alpha;   /* (0.5) */
    /* High-band tilt (probe, 24/11/2026): with hf_db != 0, the masks of bands hf_band and up
     * raised by hf_db times (b - hf_band + 1) / (MULE_NB - hf_band), a ramp up to hf_db in the
     * last band (> 0: fewer bits in the highs, more noise filling; 0: off) */
    double hf_db;
    int hf_band;        /* (16) */
} mule_enc_params;

void mule_enc_defaults(mule_enc_params *p);
/* pcm: L interleaved stereo samples (double, full scale 1.0), 44.1 kHz. tags: "KEY=value".
 * Returns 0 and a malloc'd Ogg MULE file (free with mule_free), and the audio packet bytes. */
int mule_encode(const double *pcm, int64_t L, const mule_enc_params *p,
                const char *const *tags, int ntags, uint8_t **out, size_t *out_len,
                size_t *audio_bytes);
/* The coding operations only: model index (>= 0) or -nbits (a raw value), and the value;
 * frame_start[0..frames]. Arrays malloc'd (mule_free). For tests and comparisons. */
int mule_encode_ops(const double *pcm, int64_t L, const mule_enc_params *p, int32_t **model,
                    uint32_t **val, int64_t *n, int64_t **frame_start, int *frames);
/* mule_encode_ops, plus a trace of the coefficient and energy symbols for the context
 * measurements (eval/ctx_lab.py): ntrace records of MULE_TRACE_W int32 (free with mule_free).
 * Coefficient record: 0, op index, frame, channel, block type, band, line, allocation class,
 * tail1, tail2, inter, e (rescale exponent), y_prev (|index| of the last long frame), |index|,
 * context, y_prev rescaled (before the cap; -1 if not inter), TCQ level (signed, D/2 units),
 * value before quantization (D/2 units, x256), the Viterbi's rate weight (x1e4), trellis state
 * after this coefficient.
 * Energy record: 1, op index, frame, channel, block type, band, Q, prediction, residual, context,
 * alpha, group, key, previous Q, M/S (1) or L/R (0), then 0s.
 * Band record (every band of each coded channel and group, after its allocation): 2, op index,
 * frame, channel, block type, band, allocation a, M/S, group, 1000 log10 of the band's mask and
 * of its coded channel's power per coefficient, Q, the group's first and end window, then 0s. */
#define MULE_TRACE_W 20
int mule_encode_trace(const double *pcm, int64_t L, const mule_enc_params *p, int32_t **model,
                      uint32_t **val, int64_t *n, int64_t **frame_start, int *frames,
                      int32_t **trace, int64_t *ntrace);
void mule_free(void *p);

#endif
