/* Model layout and initial CDFs (decoder and encoder): the streams of core/mule.h (spec 3) and the
 * trained tables of core/init_cdf.h. */
#include "mule.h"
#include "init_cdf.h"

const int mule_init_cdf_id = MULE_INIT_CDF_ID;
const int mule_stream_nsyms[MULE_S_COUNT] = {2, 4, 2, 16, 16, 2, 16, 16, 16};
const int mule_stream_nctx[MULE_S_COUNT] = {1, 1, 3, 9, 6, 1, 16, 96, 1};
const int mule_stream_off[MULE_S_COUNT] = {0, 1, 2, 5, 14, 20, 21, 37, 133};

/* Every model to its initial state (a key packet, spec 4): the trained CDF of its stream and
 * context, or the uniform one for a stream without table. */
void mule_models_reset(mule_models *ms)
{
    for (int s = 0; s < MULE_S_COUNT; s++) {
        const uint16_t *init = mule_init_cdf[s];
        int n = mule_stream_nsyms[s];
        for (int c = 0; c < mule_stream_nctx[s]; c++) {
            mule_model *m = &ms->m[mule_stream_off[s] + c];
            if (init)
                mule_model_init_cdf(m, n, init + (size_t)c * (size_t)(n + 1));
            else
                mule_model_init(m, n);
        }
    }
}
