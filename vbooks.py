import io, sys, hashlib, struct
import numpy as np
import soundfile as sf

def ogg_packets(data):
    pos, buf, pkts = 0, b"", []
    while pos < len(data):
        assert data[pos:pos+4] == b"OggS"
        nseg = data[pos+26]
        segs = data[pos+27:pos+27+nseg]
        p = pos + 27 + nseg
        for s in segs:
            buf += data[p:p+s]; p += s
            if s < 255:
                pkts.append(buf); buf = b""
        pos = p
        if len(pkts) >= 3:
            break
    return pkts

class BR:
    def __init__(s, b): s.b, s.p = b, 0
    def r(s, n):
        v = 0
        for i in range(n):
            byte = s.b[s.p >> 3]
            v |= ((byte >> (s.p & 7)) & 1) << i
            s.p += 1
        return v

def ilog(x):
    n = 0
    while x: n += 1; x >>= 1
    return n

def lookup1(entries, dim):
    r = int(entries ** (1.0 / dim))
    while (r + 1) ** dim <= entries: r += 1
    while r ** dim > entries: r -= 1
    return r

def parse_setup(pkt):
    assert pkt[0] == 5 and pkt[1:7] == b"vorbis"
    br = BR(pkt[7:])
    n = br.r(8) + 1
    books = []
    for _ in range(n):
        start = br.p
        assert br.r(24) == 0x564342
        dim, entries = br.r(16), br.r(24)
        lengths = [0] * entries
        if br.r(1) == 0:
            sparse = br.r(1)
            for i in range(entries):
                if sparse and not br.r(1):
                    continue
                lengths[i] = br.r(5) + 1
        else:
            cur, L = 0, br.r(5) + 1
            while cur < entries:
                num = br.r(ilog(entries - cur))
                for i in range(cur, cur + num): lengths[i] = L
                cur += num; L += 1
        lt = br.r(4)
        lv = 0; vbits = 0; vals = ()
        mn = dl = seq = 0
        if lt in (1, 2):
            mn, dl = br.r(32), br.r(32)
            vbits = br.r(4) + 1; seq = br.r(1)
            lv = lookup1(entries, dim) if lt == 1 else entries * dim
            vals = tuple(br.r(vbits) for _ in range(lv))
        key = (dim, entries, tuple(lengths), lt, mn, dl, vbits, seq, vals)
        h = hashlib.sha1(repr(key).encode()).hexdigest()[:12]
        used = sum(1 for l in lengths if l)
        # ROM estimate
        huff = used * 4 + entries          # 32-bit codeword per used entry + 1-byte length
        vq_compact = lv * (1 if vbits <= 8 else 2)
        vq_expanded = (entries * dim * 2) if lt else 0   # int16 table, Tremor-style
        books.append(dict(h=h, dim=dim, entries=entries, used=used, lt=lt,
                          bits=br.p - start, rom_c=huff + vq_compact,
                          rom_x=huff + vq_expanded))
    return books, len(pkt)

def setup_for(sr, ch, q):
    t = np.arange(sr * 2) / sr
    x = (0.3 * np.sin(2 * np.pi * 440 * t) + 0.05 * np.random.randn(len(t)))
    x = np.tile(x[:, None], (1, ch)).astype(np.float32)
    f = io.BytesIO()
    with sf.SoundFile(f, "w", sr, ch, format="OGG", subtype="VORBIS",
                      compression_level=1 - q / 10) as w:
        w.write(x)
    return parse_setup(ogg_packets(f.getvalue())[2])

def main_files(paths):
    """Usage : python3 vbooks.py fichier1.ogg [fichier2.ogg ...]
    Affiche le nombre de codebooks, la taille du setup et un hash du jeu de codebooks."""
    for p in paths:
        data = open(p, "rb").read()
        books, size = parse_setup(ogg_packets(data)[2])
        setid = hashlib.sha1("".join(b["h"] for b in books).encode()).hexdigest()[:12]
        print(f"{p}: {len(books)} codebooks, setup {size} o, jeu={setid}, "
              f"ROM~{sum(b['rom_c'] for b in books)/1024:.1f} Kio")

if __name__ == "__main__" and len(sys.argv) > 1:
    main_files(sys.argv[1:])
elif __name__ == "__main__":
    allbooks = {}
    print(f"{'sr':>6} {'ch':>2} {'q':>3} {'books':>5} {'setup':>7}")
    groups = {}
    for sr in (44100, 48000):
        for ch in (1, 2):
            for q in range(0, 11):
                books, size = setup_for(sr, ch, q)
                print(f"{sr:>6} {ch:>2} {q:>3} {len(books):>5} {size:>7}")
                for b in books:
                    allbooks[b["h"]] = b
                    groups.setdefault((sr, ch), set()).add(b["h"])
    def tot(hs):
        bs = [allbooks[h] for h in hs]
        return len(bs), sum(b["rom_c"] for b in bs), sum(b["rom_x"] for b in bs)
    print()
    for k, hs in groups.items():
        print(k, "uniques=%d  ROM compact=%d o  ROM expanded=%d o" % tot(hs))
    st = groups[(44100, 2)] | groups[(48000, 2)]
    print("stereo 44.1+48:", "uniques=%d compact=%d expanded=%d" % tot(st))
    print("44.1/48 identiques (stéréo):", groups[(44100, 2)] == groups[(48000, 2)])
    print("TOTAL all:", "uniques=%d compact=%d expanded=%d" % tot(set(allbooks)))
    big = sorted(allbooks.values(), key=lambda b: -b["rom_x"])[:8]
    for b in big:
        print(b)
