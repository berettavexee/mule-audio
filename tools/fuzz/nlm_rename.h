/* core/dec.c's API renamed, for the second build that tools/fuzz/fuzz_dec.c compares with the
 * reference (-DFUZZ_DIFF): the build for cores without a 32 x 32 -> 64 multiply. */
#define mule_dec_init nlm_dec_init
#define mule_dec_size nlm_dec_size
#define mule_dec_new nlm_dec_new
#define mule_dec_free nlm_dec_free
#define mule_dec_channels nlm_dec_channels
#define mule_dec_pre_skip nlm_dec_pre_skip
#define mule_dec_packet nlm_dec_packet
#define mule_dec_seek nlm_dec_seek
#define mule_dec_set_fft nlm_dec_set_fft
#define mule_dec_set_fft_mem nlm_dec_set_fft_mem
