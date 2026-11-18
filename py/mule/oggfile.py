"""Ogg MULE files: packets out, the comment packet (MULETags, the OpusTags layout) read and
rewritten; FLAC metadata (Vorbis comments, pictures) in, for the encoder's tag copy."""
import base64
import struct

_CRC = []
for _i in range(256):
    _r = _i << 24
    for _ in range(8):
        _r = ((_r << 1) ^ 0x04C11DB7) if _r & 0x80000000 else _r << 1
    _CRC.append(_r & 0xFFFFFFFF)


def crc(b):
    c = 0
    for x in b:
        c = ((c << 8) ^ _CRC[((c >> 24) ^ x) & 0xFF]) & 0xFFFFFFFF
    return c


def pages(data):
    """(offset, header fields, lacing, body offset) of each page; stops at the first damaged one"""
    pos, out = 0, []
    while pos + 27 <= len(data) and data[pos:pos + 4] == b"OggS":
        nseg = data[pos + 26]
        lace = data[pos + 27:pos + 27 + nseg]
        body = pos + 27 + nseg
        end = body + sum(lace)
        if end > len(data):
            break
        out.append(dict(pos=pos, flags=data[pos + 5],
                        granule=struct.unpack_from("<q", data, pos + 6)[0],
                        serial=data[pos + 14:pos + 18], lace=bytes(lace), body=body, end=end))
        pos = end
    return out


def packets(data):
    """The complete packets of the stream, and for each the index of the page it ends on"""
    out, buf = [], b""
    for k, p in enumerate(pages(data)):
        o = p["body"]
        for n in p["lace"]:
            buf += data[o:o + n]
            o += n
            if n < 255:
                out.append((buf, k))
                buf = b""
    return out


def audio_bytes(path, n_headers=2):
    """Bytes of a file's audio packets (the n_headers first packets excluded), Ogg framing not
    counted: the rate measure of the evaluations, the same for every codec."""
    with open(path, "rb") as f:
        return sum(len(p) for p, _ in packets(f.read())[n_headers:])


def parse_comments(pk):
    """MULETags / OpusTags / a Vorbis comment block (no magic): (vendor, [(KEY, value)])"""
    o = 8 if pk[:8] in (b"MULETags", b"OpusTags") else 0
    n = struct.unpack_from("<I", pk, o)[0]
    vendor = pk[o + 4:o + 4 + n].decode("utf-8", "replace")
    o += 4 + n
    count = struct.unpack_from("<I", pk, o)[0]
    o += 4
    out = []
    for _ in range(count):
        n = struct.unpack_from("<I", pk, o)[0]
        k, _, v = pk[o + 4:o + 4 + n].decode("utf-8", "replace").partition("=")
        out.append((k.upper(), v))
        o += 4 + n
    return vendor, out


def build_comments(vendor, items):
    v = vendor.encode()
    out = b"MULETags" + struct.pack("<I", len(v)) + v + struct.pack("<I", len(items))
    for k, val in items:
        b = f"{k}={val}".encode()
        out += struct.pack("<I", len(b)) + b
    return out


def _page(flags, granule, serial, seq, lace, body):
    h = bytearray(b"OggS\0" + bytes([flags]) + struct.pack("<q", granule) + serial
                  + struct.pack("<I", seq) + b"\0\0\0\0" + bytes([len(lace)]) + bytes(lace))
    p = h + body
    p[22:26] = struct.pack("<I", crc(bytes(p)))
    return bytes(p)


def replace_comments(data, packet):
    """The file with its second packet (the comment header) replaced by `packet`, over as many
    pages as needed; the audio pages renumbered and their CRC recomputed"""
    pg = pages(data)
    pk = packets(data)
    if len(pk) < 2 or pk[0][1] != 0:
        raise ValueError("not an Ogg stream with two header packets")
    last = pk[1][1]                             # the page where the comment packet ends
    serial = pg[0]["serial"]
    out, seq = [data[pg[0]["pos"]:pg[0]["end"]]], 1
    off, first = 0, True
    while True:
        rest = len(packet) - off
        chunk = min(rest, 255 * 255)
        done = chunk == rest and chunk < 255 * 255
        lace = [255] * (chunk // 255) + ([chunk % 255] if done else [])
        out.append(_page(0 if first else 1, 0 if done else -1, serial, seq, lace,
                         packet[off:off + chunk]))
        seq += 1
        off += chunk
        first = False
        if done:
            break
    for p in pg[last + 1:]:
        h = bytearray(data[p["pos"]:p["end"]])
        h[18:22] = struct.pack("<I", seq)
        h[22:26] = b"\0\0\0\0"
        h[22:26] = struct.pack("<I", crc(bytes(h)))
        out.append(bytes(h))
        seq += 1
    return b"".join(out)


# ---- FLAC metadata (for the encoder's tag and picture copy, as opusenc does) ----
def flac_metadata(path):
    """(comments [(KEY, value)], pictures [raw METADATA_BLOCK_PICTURE bytes]) of a FLAC file;
    ([], []) for anything else"""
    with open(path, "rb") as f:
        head = f.read(4)
        if head != b"fLaC":
            return [], []
        comments, pictures = [], []
        while True:
            h = f.read(4)
            if len(h) < 4:
                break
            last, kind, n = h[0] >> 7, h[0] & 0x7F, int.from_bytes(h[1:4], "big")
            body = f.read(n)
            if kind == 4:
                comments = parse_comments(body)[1]
            elif kind == 6:
                pictures.append(body)
            if last:
                break
    return comments, pictures


def picture_block(path, kind=3, description=""):
    """A METADATA_BLOCK_PICTURE for an image file (JPEG or PNG; width and height read from it)"""
    data = open(path, "rb").read()
    w = h = 0
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
        w, h = struct.unpack(">II", data[16:24])
    elif data[:2] == b"\xff\xd8":
        mime = "image/jpeg"
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                break
            m = data[i + 1]
            n = struct.unpack(">H", data[i + 2:i + 4])[0]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                break
            i += 2 + n
    else:
        raise ValueError(f"{path}: not a JPEG or PNG picture")
    m, d = mime.encode(), description.encode()
    return (struct.pack(">II", kind, len(m)) + m + struct.pack(">I", len(d)) + d
            + struct.pack(">IIIII", w, h, 24, 0, len(data)) + data)


def picture_comment(block):
    return ("METADATA_BLOCK_PICTURE", base64.b64encode(block).decode())
