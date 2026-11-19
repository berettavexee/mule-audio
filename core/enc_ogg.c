/* MULE encoder: the Ogg MULE file (spec 1, 2) from the coding operations: the MULEHead and
 * MULETags packets, then the audio packets, rANS-coded (core/rans.c), in Ogg pages (RFC 3533). */
#include "enc_int.h"

/* A growable byte buffer (the Ogg file, the comment packet). */
typedef struct {
    uint8_t *b;
    size_t n, cap;
} buf_t;

/* Appends n bytes; -1 if out of memory (the buffer is then left as it was). */
static int buf_put(buf_t *b, const void *p, size_t n)
{
    if (b->n + n > b->cap) {
        size_t c = b->cap ? b->cap : 1 << 16;
        while (c < b->n + n)
            c *= 2;
        uint8_t *nb = realloc(b->b, c);
        if (!nb)
            return -1;
        b->b = nb;
        b->cap = c;
    }
    memcpy(b->b + b->n, p, n);
    b->n += n;
    return 0;
}

static uint32_t crc_tab[256];

/* The Ogg CRC-32 table (polynomial 0x04C11DB7, no reflection). */
static void crc_init(void)
{
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t r = i << 24;
        for (int k = 0; k < 8; k++)
            r = r & 0x80000000u ? (r << 1) ^ 0x04C11DB7u : r << 1;
        crc_tab[i] = r;
    }
}

/* One Ogg page holding np complete packets (at most 255 lacing values in all), with its CRC.
 * -1 if out of memory. */
static int page(buf_t *out, int flags, int64_t granule, uint32_t serial, uint32_t seq,
                const uint8_t *const *pk, const int *len, int np)
{
    uint8_t h[27 + 255];
    int nl = 0;
    for (int i = 0; i < np; i++) {
        for (int k = 0; k < len[i] / 255; k++)
            h[27 + nl++] = 255;
        h[27 + nl++] = (uint8_t)(len[i] % 255);
    }
    memcpy(h, "OggS", 4);
    h[4] = 0;
    h[5] = (uint8_t)flags;
    for (int i = 0; i < 8; i++)
        h[6 + i] = (uint8_t)((uint64_t)granule >> (8 * i));
    for (int i = 0; i < 4; i++) {
        h[14 + i] = (uint8_t)(serial >> (8 * i));
        h[18 + i] = (uint8_t)(seq >> (8 * i));
        h[22 + i] = 0;
    }
    h[26] = (uint8_t)nl;
    size_t start = out->n;
    if (buf_put(out, h, (size_t)(27 + nl)))
        return -1;
    for (int i = 0; i < np; i++)
        if (buf_put(out, pk[i], (size_t)len[i]))
            return -1;
    uint32_t crc = 0;
    for (size_t i = start; i < out->n; i++)
        crc = (crc << 8) ^ crc_tab[((crc >> 24) ^ out->b[i]) & 0xff];
    for (int i = 0; i < 4; i++)
        out->b[start + 22 + i] = (uint8_t)(crc >> (8 * i));
    return 0;
}

/* One packet of any size over as many pages as needed (255 segments a page: up to 65,025
 * bytes); the pages after the first are continued (flag 1); only the last, where the packet
 * ends, carries the granule, the others -1 (no packet ends there, RFC 3533) */
static int page_big(buf_t *out, int flags, int64_t granule, uint32_t serial, uint32_t *seq,
                    const uint8_t *data, int len)
{
    int off = 0, first = 1;
    do {
        int rest = len - off, chunk = rest > 255 * 255 ? 255 * 255 : rest;
        int last = chunk == rest && chunk < 255 * 255;      /* ends here (a final lacing value < 255) */
        uint8_t h[27 + 255];
        int nl = 0;
        for (int k = 0; k < chunk / 255; k++)
            h[27 + nl++] = 255;
        if (last)
            h[27 + nl++] = (uint8_t)(chunk % 255);
        memcpy(h, "OggS", 4);
        h[4] = 0;
        h[5] = (uint8_t)((first ? flags : 0) | (first ? 0 : 1));
        int64_t g = last ? granule : -1;
        for (int i = 0; i < 8; i++)
            h[6 + i] = (uint8_t)((uint64_t)g >> (8 * i));
        for (int i = 0; i < 4; i++) {
            h[14 + i] = (uint8_t)(serial >> (8 * i));
            h[18 + i] = (uint8_t)(*seq >> (8 * i));
            h[22 + i] = 0;
        }
        h[26] = (uint8_t)nl;
        size_t start = out->n;
        if (buf_put(out, h, (size_t)(27 + nl)) || buf_put(out, data + off, (size_t)chunk))
            return -1;
        uint32_t crc = 0;
        for (size_t i = start; i < out->n; i++)
            crc = (crc << 8) ^ crc_tab[((crc >> 24) ^ out->b[i]) & 0xff];
        for (int i = 0; i < 4; i++)
            out->b[start + 22 + i] = (uint8_t)(crc >> (8 * i));
        (*seq)++;
        off += chunk;
        first = 0;
        if (last)
            return 0;
    } while (1);
}

/* v as 4 little-endian bytes. */
static void le32(uint8_t *p, uint32_t v)
{
    for (int i = 0; i < 4; i++)
        p[i] = (uint8_t)(v >> (8 * i));
}

/* ---------------------------------------------------------------- the file */

/* The whole Ogg MULE file from the coding operations o of the T frames (frame t's operations
 * from fstart[t]) of a signal of L samples: MULEHead, MULETags (the tags, over several pages if
 * needed), then packets of up to 4 frames (fewer before a key frame, or when a packet would
 * exceed MULE_PACKET_MAX), in pages of about 4 KiB, the last page's granule giving the length.
 * 0, or -1 (out of memory), -2 (a frame alone exceeds MULE_PACKET_MAX); o is left as it is. */
int ogg_write(const mule_enc_params *pr, const ops_t *o, const int64_t *fstart, int T, int64_t L,
              const char *const *tags, int ntags, uint8_t **out, size_t *out_len,
              size_t *audio_bytes)
{
    crc_init();
    buf_t file = {0};
    uint8_t head[MULE_HEAD_LEN];
    memcpy(head, "MULEHead", 8);
    head[8] = MULE_VERSION;
    head[20] = (uint8_t)(pr->tcq_states == 64 ? 6 : pr->tcq_states == 32 ? 5 : pr->tcq_states == 16 ? 4 : 3);
    head[21] = (uint8_t)((pr->tcq_chain ? MULE_TCQ_CHAIN : 0) | (pr->coef_a8 ? MULE_COEF_A8 : 0));
    head[9] = 2;
    head[10] = MULE_PRE_SKIP & 255;
    head[11] = MULE_PRE_SKIP >> 8;
    le32(head + 12, 44100);
    head[16] = NB;
    head[17] = (uint8_t)pr->keyframe;
    head[18] = 4;
    head[19] = (uint8_t)mule_init_cdf_id;
    const uint8_t *hp[1] = {head};
    int hl[1] = {MULE_HEAD_LEN};
    uint32_t serial = 0x4D554C45u, seq = 0;
    int rc = page(&file, 2, 0, serial, seq++, hp, hl, 1);
    buf_t tg = {0};
    const char *vendor = "mule-audio C encoder";
    uint8_t w4[4];
    rc |= buf_put(&tg, "MULETags", 8);
    le32(w4, (uint32_t)strlen(vendor));
    rc |= buf_put(&tg, w4, 4);
    rc |= buf_put(&tg, vendor, strlen(vendor));
    le32(w4, (uint32_t)ntags);
    rc |= buf_put(&tg, w4, 4);
    for (int i = 0; i < ntags; i++) {
        le32(w4, (uint32_t)strlen(tags[i]));
        rc |= buf_put(&tg, w4, 4);
        rc |= buf_put(&tg, tags[i], strlen(tags[i]));
    }
    if (!rc)
        rc = page_big(&file, 0, 0, serial, &seq, tg.b, (int)tg.n);   /* cover art: several pages */
    free(tg.b);

    mule_models *models = mule_models_alloc(), *snap = mule_models_alloc();
    enum { MAXP = 64 };
    uint8_t *pkt[MAXP];
    int plen[MAXP], np = 0, cur_size = 0, nlace = 0;
    int64_t frames = 0, total = MULE_PRE_SKIP + L;
    size_t abytes = 0;
    if (!models || !snap)
        rc = -1;
    for (int t = 0; t < T && !rc;) {
        int n = T - t < 4 ? T - t : 4;
        for (int k = 1; k < n; k++)
            if ((t + k) % pr->keyframe == 0) {
                n = k;
                break;
            }
        int key = t % pr->keyframe == 0;
        if (key)
            mule_models_reset_a8(models, o->esc == 7);
        uint8_t *p = malloc(MULE_PACKET_MAX);
        if (!p) {
            rc = -1;
            break;
        }
        int len;
        for (;;) {
            int hdr = 1;
            p[0] = (uint8_t)((key ? 1 : 0) | (n - 1) << 1);
            if (key) {
                le32(p + 1, (uint32_t)t);
                hdr = 5;
            }
            mule_models_copy(snap, models);
            int sz = mule_rans_encode(models, o->m + fstart[t], o->v + fstart[t], fstart[t + n] - fstart[t],
                                      p + hdr, MULE_PACKET_MAX - hdr);
            if (sz >= 0) {
                len = hdr + sz;
                break;
            }
            if (n == 1) {
                rc = -2;
                len = 0;
                break;
            }
            mule_models_copy(models, snap);
            n = n / 2 > 0 ? n / 2 : 1;
        }
        if (rc) {
            free(p);
            break;
        }
        int lace = len / 255 + 1;
        if (np && (nlace + lace > 255 || np == MAXP)) {
            rc |= page(&file, 0, frames * F, serial, seq++, (const uint8_t *const *)pkt, plen, np);
            for (int i = 0; i < np; i++)
                free(pkt[i]);
            np = cur_size = nlace = 0;
        }
        pkt[np] = p;
        plen[np++] = len;
        cur_size += len;
        nlace += lace;
        abytes += (size_t)len;
        frames += n;
        t += n;
        int last = t >= T;
        if (cur_size >= 4096 || last) {
            int64_t g = last ? total : (frames * F < total ? frames * F : total);
            rc |= page(&file, last ? 4 : 0, g, serial, seq++, (const uint8_t *const *)pkt, plen, np);
            for (int i = 0; i < np; i++)
                free(pkt[i]);
            np = cur_size = nlace = 0;
        }
    }
    for (int i = 0; i < np; i++)
        free(pkt[i]);
    mule_models_free(models);
    mule_models_free(snap);
    if (rc) {
        free(file.b);
        return rc;
    }
    *out = file.b;
    *out_len = file.n;
    if (audio_bytes)
        *audio_bytes = abytes;
    return 0;
}
