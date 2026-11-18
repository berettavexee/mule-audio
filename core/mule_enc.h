/* MULE C encoder (core/enc.c). With rd_lambda, tcq_rd, fine_p and pre_db off it makes the
 * decisions of py/mule/encoder.py (the Python prototype), exactly (tests/test_cenc.py). */
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
    double group_db;    /* adaptive grouping threshold (6 dB) */
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
} mule_enc_params;

void mule_enc_defaults(mule_enc_params *p);
/* pcm: L interleaved stereo samples (double, full scale 1.0), 44.1 kHz. tags: "KEY=value".
 * Returns 0 and a malloc'd Ogg MULE file (free with mule_free), and the audio packet bytes. */
int mule_encode(const double *pcm, int64_t L, const mule_enc_params *p,
                const char *const *tags, int ntags, uint8_t **out, size_t *out_len,
                size_t *audio_bytes);
/* The coding operations only (as py/mule/encoder.py's Ops): model index or -nbits, value;
 * frame_start[0..frames]. Arrays malloc'd (mule_free). For tests and comparisons. */
int mule_encode_ops(const double *pcm, int64_t L, const mule_enc_params *p, int32_t **model,
                    uint32_t **val, int64_t *n, int64_t **frame_start, int *frames);
void mule_free(void *p);

#endif
