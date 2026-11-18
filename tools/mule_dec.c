/* mule-dec: Ogg MULE file -> 16-bit WAV, with the reference decoder (core/dec.c, integers only:
 * the samples the player plays). Pre-skip trimmed at the start, the end at the last page's
 * granule (gapless).
 * Usage: mule-dec [-H] in.mule out.wav
 *   -H  the IMDCT's FFT as the firmware emulator's HIFIACC model computes it (the exact transform
 *       in double, rounded to the nearest, unscaled: fw/tools/emu_host.py), so that the output
 *       equals what the emulated device plays, bit for bit (the firmware's mule-exact test)
 *   -x  accepted, no effect (the fixed-point decoder is the only one; older callers pass it) */
#include <math.h>
#include <stdio.h>
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#include <stdlib.h>
#include <string.h>
#include "mule.h"

/* The whole file at path, malloc'd (its size in len); NULL if it cannot be read. */
static uint8_t *slurp(const char *path, long *len)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return NULL;
    fseek(f, 0, SEEK_END);
    *len = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *b = malloc((size_t)*len);
    if (b && fread(b, 1, (size_t)*len, f) != (size_t)*len) {
        free(b);
        b = NULL;
    }
    fclose(f);
    return b;
}

/* Little-endian 16- and 32-bit values to f. */
static void le16(FILE *f, unsigned v) { fputc(v & 255, f); fputc(v >> 8 & 255, f); }
static void le32(FILE *f, unsigned long v) { le16(f, v & 0xffff); le16(f, v >> 16 & 0xffff); }

/* The canonical 44-byte header of a 16-bit PCM WAV of `frames` samples per channel. */
static void wav_header(FILE *f, int ch, int rate, unsigned long frames)
{
    int bps = 2;
    unsigned long data = frames * (unsigned long)(ch * bps);
    fwrite("RIFF", 1, 4, f); le32(f, 36 + data); fwrite("WAVEfmt ", 1, 8, f);
    le32(f, 16); le16(f, 1); le16(f, (unsigned)ch); le32(f, (unsigned long)rate);
    le32(f, (unsigned long)(rate * ch * bps)); le16(f, (unsigned)(ch * bps)); le16(f, (unsigned)(8 * bps));
    fwrite("data", 1, 4, f); le32(f, data);
}

/* The firmware emulator's HIFIACC FFT (fw/tools/emu_host.py, Accel._fft), for -H: bit-reversed
 * input, radix-2 butterflies in double with twiddles t *= w, results rounded half to even,
 * unscaled. A model of the hardware, not part of the decoder. */
static int emu_fft(int32_t *re, int32_t *im, int bits)
{
    int n = 1 << bits;
    double xr[512], xi[512];
    for (int i = 0; i < n; i++) {
        xr[i] = re[i];
        xi[i] = im[i];
    }
    for (int m = 2; m <= n; m *= 2) {
        double wr = cos(-2 * M_PI / m), wi = sin(-2 * M_PI / m);
        for (int k = 0; k < n; k += m) {
            double tr = 1, ti = 0;
            for (int j = 0; j < m / 2; j++) {
                double br = tr * xr[k + j + m / 2] - ti * xi[k + j + m / 2];
                double bi = tr * xi[k + j + m / 2] + ti * xr[k + j + m / 2];
                double ar = xr[k + j], ai = xi[k + j];
                xr[k + j] = ar + br;
                xi[k + j] = ai + bi;
                xr[k + j + m / 2] = ar - br;
                xi[k + j + m / 2] = ai - bi;
                double t = tr * wr - ti * wi;
                ti = tr * wi + ti * wr;
                tr = t;
            }
        }
    }
    for (int i = 0; i < n; i++) {
        re[i] = (int32_t)(uint32_t)(int64_t)nearbyint(xr[i]);
        im[i] = (int32_t)(uint32_t)(int64_t)nearbyint(xi[i]);
    }
    return 1;
}

/* Reads the Ogg pages (one logical stream), reassembles the packets, decodes them after the two
 * headers, trims, writes the WAV. Returns 0, 1 on an error, 2 on bad arguments. */
int main(int argc, char **argv)
{
    int a = 1;
    for (; a < argc && argv[a][0] == '-' && argv[a][1]; a++) {
        if (!strcmp(argv[a], "-H"))
            mule_dec_set_fft(emu_fft);
        else if (strcmp(argv[a], "-x"))
            break;
    }
    if (argc - a != 2) {
        fprintf(stderr, "usage: mule-dec [-H] in.mule out.wav\n");
        return 2;
    }
    long len;
    uint8_t *data = slurp(argv[a], &len);
    if (!data) {
        fprintf(stderr, "cannot read %s\n", argv[a]);
        return 1;
    }
    /* first pass: packets (offsets into a reassembly buffer) and the last granule */
    int rc = 1;
    mule_dec *d = NULL;
    FILE *out = NULL;
    uint8_t *pk = malloc(len ? (size_t)len : 1);
    long maxpk = 1024;
    long *pstart = malloc(sizeof(long) * (size_t)maxpk);
    if (!pk || !pstart) {
        fprintf(stderr, "out of memory\n");
        goto done;
    }
    long npk = 0, pl = 0, cur = 0;
    int64_t last_granule = -1;
    uint32_t serial = 0;
    int have_serial = 0;
    for (long pos = 0; pos + 27 <= len;) {
        if (memcmp(data + pos, "OggS", 4)) {
            fprintf(stderr, "bad page at %ld\n", pos);
            goto done;
        }
        int nseg = data[pos + 26];
        long body = 0;
        if (pos + 27 + nseg > len) {
            fprintf(stderr, "truncated page header at %ld\n", pos);
            goto done;
        }
        for (int i = 0; i < nseg; i++)
            body += data[pos + 27 + i];
        if (pos + 27 + nseg + body > len) {
            fprintf(stderr, "truncated page at %ld\n", pos);
            goto done;
        }
        uint32_t ser = (uint32_t)data[pos + 14] | (uint32_t)data[pos + 15] << 8 |
                       (uint32_t)data[pos + 16] << 16 | (uint32_t)data[pos + 17] << 24;
        uint64_t ugr = 0;
        for (int i = 7; i >= 0; i--)
            ugr = ugr << 8 | data[pos + 6 + i];
        int64_t gr = (int64_t)ugr;
        if (!have_serial) {
            serial = ser;
            have_serial = 1;
        }
        long p = pos + 27 + nseg;
        for (int i = 0; i < nseg; i++) {
            int l = data[pos + 27 + i];
            if (ser == serial) {
                if (cur == 0) {
                    if (npk + 1 >= maxpk) {
                        long *np = realloc(pstart, sizeof(long) * (size_t)(2 * maxpk));
                        if (!np)
                            goto done;
                        pstart = np;
                        maxpk *= 2;
                    }
                    pstart[npk] = pl;
                }
                memcpy(pk + pl, data + p, (size_t)l);
                pl += l;
                cur += l;
                if (l < 255) {
                    npk++;
                    cur = 0;
                }
            }
            p += l;
        }
        if (ser == serial && gr >= 0)
            last_granule = gr;
        pos = p;
    }
    pstart[npk] = pl;
    if (npk < 3) {
        fprintf(stderr, "no audio packets\n");
        goto done;
    }
    d = mule_dec_new(pk + pstart[0], (int)(pstart[1] - pstart[0]));
    if (!d) {
        fprintf(stderr, "not a MULE stream (MULEHead)\n");
        goto done;
    }
    int ch = mule_dec_channels(d), skip = mule_dec_pre_skip(d);
    int64_t total = last_granule - skip;
    out = fopen(argv[a + 1], "wb");
    if (!out) {
        fprintf(stderr, "cannot write %s\n", argv[a + 1]);
        goto done;
    }
    wav_header(out, ch, 44100, (unsigned long)(total > 0 ? total : 0));
    int16_t pcm[8 * MULE_F * 2];
    int64_t pos = 0, written = 0;
    for (long i = 2; i < npk; i++) {
        int n = mule_dec_packet(d, pk + pstart[i], (int)(pstart[i + 1] - pstart[i]), pcm, 8 * MULE_F);
        if (n < 0) {
            fprintf(stderr, "packet %ld: decoding error %d\n", i, n);
            goto done;
        }
        for (int k = 0; k < n; k++, pos++) {
            if (pos < skip || written >= total)
                continue;
            for (int c = 0; c < ch; c++)
                le16(out, (unsigned)(pcm[k * ch + c] & 0xffff));
            written++;
        }
    }
    if (written != total)
        fprintf(stderr, "warning: %lld samples decoded, %lld expected\n", (long long)written,
                (long long)total);
    else
        rc = 0;
done:                                           /* one way out: everything freed */
    if (out)
        fclose(out);
    if (d)
        mule_dec_free(d);
    free(pk);
    free(pstart);
    free(data);
    return rc;
}
