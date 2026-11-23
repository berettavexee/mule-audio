/* QEMU benchmark of the fixed-point decoder: decodes the embedded packets (packets.h), counts
 * instructions with the CMSDK timer under -icount shift=0 (1 instruction = 1 ns of virtual
 * time; the timer runs at 25 MHz: 1 tick = 40 instructions), and hashes the output (FNV-1a)
 * to check it equals the PC build's. */
#include <stdint.h>
#include <string.h>
#include "mule.h"
#include "packets.h"

void semi_puts(const char *s);

#define TIMER0_CTRL  (*(volatile uint32_t *)0x40000000u)
#define TIMER0_VALUE (*(volatile uint32_t *)0x40000004u)
#define TIMER0_RELOAD (*(volatile uint32_t *)0x40000008u)

static uint8_t dec_mem[52 * 1024] __attribute__((aligned(8)));
static int16_t pcm[8 * 1024 * 2];

static void put_u(const char *label, uint64_t v)
{
    char b[64];
    int n = 0;
    while (*label)
        b[n++] = *label++;
    char t[24];
    int k = 0;
    do
        t[k++] = (char)('0' + v % 10);
    while ((v /= 10) && k < 23);
    while (k)
        b[n++] = t[--k];
    b[n++] = '\n';
    b[n] = 0;
    semi_puts(b);
}

#ifdef MULE_PROF
static uint32_t prof_t, prof_cur;
static uint64_t prof_acc[8];
void mule_prof_mark(int section)
{
    uint32_t t = TIMER0_VALUE;
    prof_acc[prof_cur] += prof_t - t;
    prof_t = t;
    prof_cur = (uint32_t)section;
}
#endif

int main(void)
{
    mule_dec *d = mule_dec_init(dec_mem, sizeof dec_mem, mule_head, sizeof mule_head);
    if (!d) {
        semi_puts("init failed\n");
        return 1;
    }
    TIMER0_RELOAD = 0xffffffffu;
    TIMER0_VALUE = 0xffffffffu;
    TIMER0_CTRL = 1;
#ifdef MULE_PROF
    prof_t = TIMER0_VALUE;
#endif
    uint32_t hash = 2166136261u, frames = 0, worst = 0;
    uint64_t total = 0;
    for (uint32_t i = 0; i < MULE_NPACKETS; i++) {
        uint32_t t0 = TIMER0_VALUE;
        int n = mule_dec_packet(d, mule_packets + mule_offsets[i], (int)(mule_offsets[i + 1] - mule_offsets[i]),
                                  pcm, 8 * 1024);
        uint32_t dt = t0 - TIMER0_VALUE;
        if (n < 0) {
            put_u("packet error at ", i);
            return 2;
        }
        total += dt;
        uint32_t f = (uint32_t)n / MULE_F;
        frames += f;
        if (f && dt / f > worst)
            worst = dt / f;
        const uint8_t *b = (const uint8_t *)pcm;
        for (uint32_t k = 0; k < (uint32_t)n * 4; k++)
            hash = (hash ^ b[k]) * 16777619u;
    }
    put_u("frames ", frames);
    put_u("instructions_total ", total * 40);
    put_u("instructions_per_frame ", total * 40 / (frames ? frames : 1));
    put_u("worst_frame_instructions ", (uint64_t)worst * 40);
    put_u("hash ", hash);
    put_u("state_bytes ", mule_dec_size());
#ifdef MULE_PROF
    static const char *const names[8] = {"prof_read ", "prof_pre ", "prof_fft ", "prof_post ",
                                         "prof_window ", "prof_output ", "prof_noise ", "prof_ms "};
    for (int i = 0; i < 8; i++)
        put_u(names[i], prof_acc[i] * 40 / (frames ? frames : 1));
#endif
    return 0;
}
