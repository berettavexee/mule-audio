/* Model layout and initial CDFs (decoder and encoder): the streams of core/mule.h (spec 3) and the
 * trained tables of core/init_cdf.h. */
#include "mule.h"
#include "init_cdf.h"
#include "init_cdf_a8.h"

const int mule_init_cdf_id = MULE_INIT_CDF_ID;
#define NSYMS_(name, nsyms, nctx) nsyms,
#define NCTX_(name, nsyms, nctx) nctx,
#define OFF_(name, nsyms, nctx) MULE_OFF_##name,
const int mule_stream_nsyms[MULE_S_COUNT] = {MULE_STREAMS(NSYMS_)};
const int mule_stream_nctx[MULE_S_COUNT] = {MULE_STREAMS(NCTX_)};
const int mule_stream_off[MULE_S_COUNT] = {MULE_STREAMS(OFF_)};
#define NTABLES ((int)(sizeof mule_init_cdf / sizeof *mule_init_cdf))   /* streams with a table */

/* mule_init_cdf with the 8-symbol coefficient alphabet's own tables (core/init_cdf_a8.h) */
static const uint16_t *const init_cdf_a8[] = {mule_init_btype, mule_init_alpha, mule_init_stereo,
                                              mule_init_energy, mule_init_alloc, mule_init_amode,
                                              mule_init_cesc8, mule_init_coef8, mule_init_eaesc};

/* The initial CDF of stream s (its contexts' n + 1 values each, one after the other), NULL for
 * a uniform start (NFLEV); n: its symbols. a8 (format flag MULE_COEF_A8): the coefficients have 8
 * symbols (escape at 7) and the escape orders their own table. Built with MULE_DEC_V5_ONLY (core
 * B), a8 is always set: the v2 tables are then not referenced, and the linker drops them. */
const uint16_t *mule_stream_init(int s, int a8, int *n)
{
#ifdef MULE_DEC_V5_ONLY
    a8 = 1;
#endif
    *n = a8 && s == MULE_S_COEF ? 8 : mule_stream_nsyms[s];
    return s < NTABLES ? (a8 ? init_cdf_a8 : mule_init_cdf)[s] : NULL;
}

/* Every model to its initial state (a key packet, spec 4): the trained CDF of its stream and
 * context, or the uniform one for a stream without table. */
void mule_models_reset(mule_models *ms)
{
    mule_models_reset_a8(ms, 0);
}

/* mule_models_reset; a8: the 8-symbol coefficient alphabet (mule_stream_init). */
void mule_models_reset_a8(mule_models *ms, int a8)
{
    for (int s = 0; s < MULE_S_COUNT; s++) {
        int n;
        const uint16_t *init = mule_stream_init(s, a8, &n);
        for (int c = 0; c < mule_stream_nctx[s]; c++) {
            mule_model *m = &ms->m[mule_stream_off[s] + c];
            if (init)
                mule_model_init_cdf(m, n, init + (size_t)c * (size_t)(n + 1));
            else
                mule_model_init(m, n);
        }
    }
}
