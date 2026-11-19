/* Coverage-guided fuzzing of the reference decoder (core/dec.c), as the player builds it
 * (MULE_NO_MALLOC: caller memory only), under AddressSanitizer and UndefinedBehaviorSanitizer,
 * with gcc alone (no libFuzzer, no AFL): the decoder is compiled with
 * -fsanitize-coverage=trace-pc and this file counts the edges each input reaches; an input
 * that reaches a new edge joins the corpus and is mutated in turn.
 *
 * Input format (tools/fuzz/mkseeds.py writes the seeds from real files):
 *   [header length: 1 byte][MULEHead: that many bytes]
 *   then packets: [op: 1 byte][length: 2 bytes LE][packet bytes]...
 *   op bit 0: mule_dec_seek() before the packet; bits 1-2: the output buffer is short by
 *   0 / 1 / 2 / 4 frames (the decoder must refuse rather than overflow).
 *
 * What a run checks: no sanitizer report, no hang (2 s per input), the return value of
 * mule_dec_packet within bounds (-2 .. its buffer), and the guard frames around the output
 * buffer untouched.
 *
 *   fuzz_dec CORPUS_DIR SECONDS SEED      fuzz (CORPUS_DIR: seeds in, new inputs out)
 *   fuzz_dec FILE...                      replay inputs (a crash's input, the corpus)
 *
 * A failing input is written to crash-<pid>-<n>.bin in the current directory before abort. */
#include <dirent.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include "mule.h"

/* ---------------------------------------------------------------- coverage */

/* gcc's -fsanitize-coverage=trace-pc calls __sanitizer_cov_trace_pc at every basic block of the
 * decoder; as AFL does, an edge is the pair (previous block, this block) hashed into a table. */
enum { MAP = 1 << 16 };
static uint8_t hit[MAP];                /* edges reached by the current input */
static uint8_t seen[MAP];               /* edges reached by any input so far */
static uint32_t prev_loc;
static const uint32_t nguards = MAP;

void __sanitizer_cov_trace_pc(void)
{
    uintptr_t pc = (uintptr_t)__builtin_return_address(0);
    uint32_t loc = (uint32_t)((pc >> 4) ^ (pc << 8)) & (MAP - 1);
    hit[loc ^ prev_loc] = 1;
    prev_loc = loc >> 1;
}

/* ---------------------------------------------------------------- one execution */

static const uint8_t *cur;              /* the input being run (dumped if it fails) */
static size_t cur_len;
static int ncrash;

static void dump_current(void)
{
    char name[64];
    snprintf(name, sizeof name, "crash-%d-%d.bin", (int)getpid(), ncrash++);
    FILE *f = fopen(name, "wb");
    if (f) {
        fwrite(cur, 1, cur_len, f);
        fclose(f);
    }
    fprintf(stderr, "failing input written to %s (%zu bytes)\n", name, cur_len);
}

void __sanitizer_set_death_callback(void (*cb)(void));

static void on_alarm(int sig)
{
    (void)sig;
    fprintf(stderr, "hang: an input ran for more than 2 s\n");
    dump_current();
    abort();
}

static void fail(const char *what)
{
    fprintf(stderr, "check failed: %s\n", what);
    dump_current();
    abort();
}

enum { GUARD = 64, MAXF = 8 };
static _Alignas(16) uint8_t decmem[1 << 17];

/* Decodes one input; returns the number of packets fed. */
static int run_one(const uint8_t *in, size_t n)
{
    cur = in;
    cur_len = n;
    if (n < 1)
        return 0;
    size_t hl = in[0];
    if (1 + hl > n)
        return 0;
    if (mule_dec_size() > sizeof decmem)
        fail("decoder state larger than the harness's buffer");
    mule_dec *d = mule_dec_init(decmem, sizeof decmem, in + 1, (int)hl);
    if (!d)
        return 0;
    int ch = mule_dec_channels(d);
    if (ch < 1 || ch > 2)
        fail("channels out of range");
    static int16_t out[GUARD + MAXF * MULE_F * 2 + GUARD];
    size_t pos = 1 + hl;
    int np = 0;
    while (pos + 3 <= n) {
        int op = in[pos];
        size_t len = in[pos + 1] | (size_t)in[pos + 2] << 8;
        pos += 3;
        if (len > n - pos)
            len = n - pos;
        if (op & 1)
            mule_dec_seek(d);
        int frames = MAXF - (int[]){0, 1, 2, 4}[op >> 1 & 3];
        int max = frames * MULE_F;
        for (int i = 0; i < GUARD; i++)
            out[i] = out[GUARD + max * ch + i] = 0x5A5A;
        /* the packet in its own heap block: a read past its end is an ASan report */
        uint8_t *p = malloc(len ? len : 1);
        memcpy(p, in + pos, len);
        int r = mule_dec_packet(d, p, (int)len, out + GUARD, max);
        free(p);
        if (r < -2 || r > max || (r > 0 && r % MULE_F))
            fail("mule_dec_packet returned an impossible count");
        for (int i = 0; i < GUARD; i++)
            if (out[i] != 0x5A5A || out[GUARD + max * ch + i] != 0x5A5A)
                fail("write outside the output buffer");
        pos += len;
        np++;
    }
    return np;
}

/* ---------------------------------------------------------------- corpus and mutations */

typedef struct {
    uint8_t *b;
    size_t n;
} blob;

static blob *corpus;
static int ncorpus, capcorpus;
static uint64_t rng_state;

static uint64_t rnd(void)
{
    uint64_t x = rng_state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    return rng_state = x;
}

static void corpus_add(const uint8_t *b, size_t n)
{
    if (ncorpus == capcorpus) {
        capcorpus = capcorpus ? 2 * capcorpus : 256;
        corpus = realloc(corpus, sizeof *corpus * (size_t)capcorpus);
    }
    corpus[ncorpus].b = malloc(n ? n : 1);
    memcpy(corpus[ncorpus].b, b, n);
    corpus[ncorpus++].n = n;
}

static uint8_t *read_file(const char *path, size_t *n)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *b = malloc(sz > 0 ? (size_t)sz : 1);
    *n = fread(b, 1, (size_t)(sz > 0 ? sz : 0), f);
    fclose(f);
    return b;
}

enum { MAXLEN = 1 << 18 };

/* A mutation of a: 1 to 8 stacked edits (bit flips, interesting bytes, runs, deletions,
 * insertions, copies inside the input, splices with another corpus entry, header bytes). */
static size_t mutate(const blob *a, uint8_t *o)
{
    size_t n = a->n < MAXLEN ? a->n : MAXLEN;
    memcpy(o, a->b, n);
    int k = 1 + (int)(rnd() % 8);
    static const uint8_t interesting[] = {0, 1, 2, 3, 6, 7, 8, 15, 16, 22, 47, 48, 64, 127, 128, 255};
    for (int e = 0; e < k && n; e++) {
        size_t i = rnd() % n;
        switch (rnd() % 10) {
        case 0: case 1:
            o[i] ^= (uint8_t)(1u << (rnd() % 8));
            break;
        case 2:
            o[i] = interesting[rnd() % sizeof interesting];
            break;
        case 3:
            o[i] = (uint8_t)rnd();
            break;
        case 4: {                                       /* a run of one value */
            size_t l = 1 + rnd() % 32;
            if (i + l > n) l = n - i;
            memset(o + i, (int)(rnd() & 1 ? 0 : rnd()), l);
            break;
        }
        case 5: {                                       /* delete */
            size_t l = 1 + rnd() % 64;
            if (i + l > n) l = n - i;
            memmove(o + i, o + i + l, n - i - l);
            n -= l;
            break;
        }
        case 6: {                                       /* insert random bytes */
            size_t l = 1 + rnd() % 64;
            if (n + l > MAXLEN) break;
            memmove(o + i + l, o + i, n - i);
            for (size_t j = 0; j < l; j++) o[i + j] = (uint8_t)rnd();
            n += l;
            break;
        }
        case 7: {                                       /* copy a chunk elsewhere */
            size_t l = 1 + rnd() % 256, j = rnd() % n;
            if (i + l > n) l = n - i;
            if (j + l > n) l = n - j;
            memmove(o + j, o + i, l);
            break;
        }
        case 8: {                                       /* splice another input's tail */
            const blob *b = &corpus[rnd() % ncorpus];
            if (!b->n) break;
            size_t j = rnd() % b->n, l = b->n - j;
            if (i + l > MAXLEN) l = MAXLEN - i;
            memcpy(o + i, b->b + j, l);
            n = i + l;
            break;
        }
        default:                                        /* the header: version, sizes, flags */
            if (n > 22) {
                size_t h = 1 + 8 + rnd() % 14;
                o[h] = interesting[rnd() % sizeof interesting];
            }
        }
    }
    return n;
}

/* Runs an input; 1 if it reached an edge never seen. */
static int run_and_score(const uint8_t *b, size_t n)
{
    memset(hit, 0, sizeof hit);
    prev_loc = 0;
    alarm(2);
    run_one(b, n);
    alarm(0);
    int fresh = 0;
    for (uint32_t i = 0; i < nguards; i++)
        if (hit[i] && !seen[i]) {
            seen[i] = 1;
            fresh = 1;
        }
    return fresh;
}

static int edges_seen(void)
{
    int c = 0;
    for (uint32_t i = 0; i < nguards; i++)
        c += seen[i];
    return c;
}

int main(int argc, char **argv)
{
    signal(SIGALRM, on_alarm);
    __sanitizer_set_death_callback(dump_current);
    if (argc >= 2 && (argc != 4 || !strchr("0123456789", argv[2][0]))) {
        for (int i = 1; i < argc; i++) {                /* replay */
            size_t n;
            uint8_t *b = read_file(argv[i], &n);
            if (!b) {
                fprintf(stderr, "%s: unreadable\n", argv[i]);
                return 2;
            }
            run_one(b, n);
            free(b);
        }
        printf("%d inputs replayed without failure\n", argc - 1);
        return 0;
    }
    if (argc != 4) {
        fprintf(stderr, "usage: fuzz_dec CORPUS_DIR SECONDS SEED | fuzz_dec FILE...\n");
        return 2;
    }
    const char *dir = argv[1];
    double seconds = atof(argv[2]);
    rng_state = strtoull(argv[3], NULL, 10) * 0x9E3779B97F4A7C15ull + 1;
    DIR *dd = opendir(dir);
    if (!dd) {
        fprintf(stderr, "%s: no such directory\n", dir);
        return 2;
    }
    struct dirent *de;
    while ((de = readdir(dd))) {
        if (de->d_name[0] == '.')
            continue;
        char path[4096];
        snprintf(path, sizeof path, "%s/%s", dir, de->d_name);
        size_t n;
        uint8_t *b = read_file(path, &n);
        if (b) {
            run_and_score(b, n);
            corpus_add(b, n);
            free(b);
        }
    }
    closedir(dd);
    if (!ncorpus) {
        fprintf(stderr, "%s: no seeds\n", dir);
        return 2;
    }
    printf("seeds %d, edges %d\n", ncorpus, edges_seen());
    fflush(stdout);
    static uint8_t buf[MAXLEN];
    struct timeval t0, t;
    gettimeofday(&t0, NULL);
    long execs = 0, last = 0;
    for (;;) {
        size_t n = mutate(&corpus[rnd() % ncorpus], buf);
        if (run_and_score(buf, n)) {
            corpus_add(buf, n);
            char path[4096];
            snprintf(path, sizeof path, "%s/new-%d-%d.bin", dir, (int)getpid(), ncorpus);
            FILE *f = fopen(path, "wb");
            if (f) {
                fwrite(buf, 1, n, f);
                fclose(f);
            }
        }
        execs++;
        gettimeofday(&t, NULL);
        double el = (double)(t.tv_sec - t0.tv_sec) + (t.tv_usec - t0.tv_usec) / 1e6;
        if (el - last >= 60 || el >= seconds) {
            last = (long)el;
            printf("%6.0f s  execs %ld (%.0f/s)  corpus %d  edges %d\n", el, execs, execs / el,
                   ncorpus, edges_seen());
            fflush(stdout);
        }
        if (el >= seconds)
            break;
    }
    return 0;
}
