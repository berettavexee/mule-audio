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
    double low_db;      /* extra masking offset in bands 0-7 (10 dB) */
    double mid_db;      /* extra masking offset in bands 8 .. mid_hi-1 (4 dB) */
    int mid_hi;         /* (17) */
    double ton_scale;   /* flatness (dB below noise's) of a fully tonal band (20) */
    double tcap_db;     /* cap of the tonal masking offset 14.5 + z (25 dB; <= 0: none) */
    int alloc_auto;     /* allocation reference: per group, band or frame (else band; 1) */
    int alloc_hyst;     /* keep the previous frame's a_b within +-alloc_hyst (1) */
    /* C encoder only (P4, axes 1 to 3: eval/results/P4-LOG.md, E-LOG.md, E2-LOG.md) */
    int fft_tonal;      /* tonality from the flatness of a Hann FFT power spectrum (1) */
    double fft_noise_db; /* flatness of noise in that spectrum (4) */
    double rd_lambda;   /* > 0: per band, choose a-1, a, a+1 by (noise/mask) + lambda * bits, the
                         * bits from a copy of the adaptive models (exact costs; 2); 0 off */
    double tcq_lam;     /* TCQ Viterbi rate weight without tcq_rd ((D/2)^2 units; 0.3) */
    int tcq_rd;         /* 1: the Viterbi's rate from the tracked models (contexts from each
                         * survivor's tails, inter-frame context, escapes, sign), levels nearest
                         * and +-4; needs rd_lambda > 0 (1) */
    double tcq_rdl;     /* with tcq_rd: rate weight relative to the allocation's (0.5) */
    double fine_p;      /* > 0: long frames' band targets from fine_w-line sub-band masks (Bark
                         * density spreading, the band's tonality), their power mean of exponent
                         * -fine_p (8); 0 off */
    int fine_w;         /* lines per sub-band (1) */
    int fine_nb;        /* fine masks below this band only (12; 0: all) */
    double pre_db;      /* > 0: pre-echo control (AAC's rpelev): a long frame's mask at most this
                         * many dB above the previous long frame's (10); 0 off */
    int nf_bias;        /* noise-filled bands' energy sent this many 1.5 dB steps lower (0; PEAQ
                         * and ViSQOL disagree, E2-LOG.md: left to a listening test) */
    int tcq_states;     /* trellis of 8, 16, 32 or 64 states (64; header byte 20) */
    int tcq_chain;      /* 1: the trellis state runs on across a group's bands, one Viterbi over
                         * them (needs tcq_rd and rd_lambda); 0: restarted at 0 in each band, for
                         * comparisons only (1; header flag MULE_TCQ_CHAIN) */
    int coef_a8;        /* coefficient alphabet of 8 symbols, escape at 7; 0: 16 symbols, escape
                         * at 15, for comparisons only (1; header flag MULE_COEF_A8) */
    int tcq_rd_states;  /* encoder speed: the trellis of the RD choice's per-band estimates
                         * (a-1, a, a+1), 8 to 64; 0: tcq_states (8) */
    int tg;             /* zero-bit tonal bands (eval/results/N-LOG.md): 0 off (production),
                         * 1 guard: the band gets allocation 1 if its strongest line is within
                         * tg_db of the mask target; 2 muted: sent silent instead of noise (0) */
    double tg_db;       /* guard: the strongest line at least the target minus this (dB; 6) */
    int tg_a;           /* guard: the allocation given (1 .. MULE_AMAX; 1) */
    int group_mode;     /* adaptive grouping: 0 the window's energy only, 1 also per frequency
                         * region (1; eval/results/N-LOG.md) */
    double tr_db;       /* transient detector: energy rise over its decaying memory (10 dB) */
    double short_db;    /* noise target offset in short frames (0 dB; < 0: more bits) */
    double tg_ton;      /* a lone line: the band's strongest coefficient this many dB above the
                         * strongest of a noise of the same lines, 2 ln n times the mean (5) */
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
