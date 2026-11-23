"""mule-enc: encode audio to Ogg MULE, with options modelled on opusenc's.

Usage: mule-enc [options] input_file output_file.mule

The input can be WAV, AIFF, FLAC, Ogg (FLAC or Vorbis), MP3... (what libsndfile reads), or "-"
for stdin; the output "-" for stdout. Any sample rate (resampled to 44.1 kHz, the format's), mono
(duplicated) or more than 2 channels (downmixed to stereo). Tags and pictures are copied from a
FLAC input (as opusenc does), the basic tags from the others. ReplayGain 2.0 track gain and peak
are measured on the decoded MULE output (what the player plays) and written; album gain:
mule-gain."""
import argparse
import io
import os
import sys

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "py"))
from mule import native, oggfile, params, replaygain  # noqa: E402

VERSION = "mule-enc 1.0 (mule-audio, stream format v2)"
Q_MIN, Q_MAX = -30.0, 6.0
SOURCE_TAGS = ["title", "artist", "album", "date", "tracknumber", "genre", "comment"]


def quality_for(kbps):
    """The quality setting (q_db) whose library-average rate is kbps (params.for_bitrate's curve;
    eval/archive/abx_kit_g3.py)."""
    return params.for_bitrate(kbps).q_db


def to_stereo(x):
    """x (n, channels) as stereo: mono doubled, more than two channels downmixed (BS.775)."""
    if x.shape[1] == 1:
        return np.repeat(x, 2, axis=1)
    if x.shape[1] == 2:
        return x
    # WAV order: L R C LFE (BL BR | SL SR ...): ITU-R BS.775 downmix, LFE dropped
    c = 1 / np.sqrt(2)
    left, right = x[:, 0].copy(), x[:, 1].copy()
    if x.shape[1] > 2:
        left += c * x[:, 2]
        right += c * x[:, 2]
    if x.shape[1] > 5:
        left += c * x[:, 4]
        right += c * x[:, 5]
    y = np.stack([left, right], 1)
    peak = np.abs(y).max() if len(y) else 0
    return y / peak if peak > 1 else y


def read_input(path):
    """Audio (float64, n x channels), its rate, its tags and its pictures from path ("-": stdin)."""
    data = sys.stdin.buffer.read() if path == "-" else None
    with sf.SoundFile(io.BytesIO(data) if data is not None else path) as f:
        x = f.read(dtype="float64", always_2d=True)
        fs = f.samplerate
        tags = [(k.upper(), getattr(f, k)) for k in SOURCE_TAGS if getattr(f, k, "")]
    pictures = []
    if path != "-":
        flac_tags, pictures = oggfile.flac_metadata(path)
        if flac_tags:
            tags = flac_tags
    return x, fs, tags, pictures


def decoded(data):
    """The fixed-point decoder's output for an encoded file (the device's), float, trimmed"""
    pk = oggfile.packets(data)
    pg = oggfile.pages(data)
    d = native.Decoder(pk[0][0])
    out = [d.packet(p) for p, _ in pk[2:]]
    y = np.concatenate(out).astype(np.float64) / 32768 if out else np.zeros((0, 2))
    end = pg[-1]["granule"] if pg else len(y)
    return y[d.pre_skip:max(end, d.pre_skip)]


def picture_arg(spec):
    """opusenc's [TYPE]|[MIME]|[DESCRIPTION]|[WIDTHxHEIGHT[xDEPTH[/COLORS]]]|FILENAME, or a file"""
    parts = spec.split("|")
    kind = int(parts[0]) if len(parts) == 5 and parts[0] else 3
    desc = parts[2] if len(parts) == 5 else ""
    return oggfile.picture_block(parts[-1], kind, desc)


def main():
    """The command line (see the module's docstring and --help)."""
    ap = argparse.ArgumentParser(prog="mule-enc", usage="mule-enc [options] input_file output_file.mule",
                                 description="Encode audio using MULE.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("-V", "--version", action="version", version=VERSION)
    ap.add_argument("--quiet", action="store_true", help="enable quiet mode")
    g = ap.add_argument_group("encoding options")
    g.add_argument("--bitrate", type=float, metavar="n.nnn",
                   help="target bitrate in kbit/s (VBR, as opusenc's: each track's rate drawn toward "
                        "it; default 128: transparent in our listening tests)")
    g.add_argument("-q", "--quality", type=float, metavar="dB",
                   help="noise target relative to the masking threshold, instead of --bitrate: "
                        "pure quality VBR, the rate follows the music (on average -2.5 ~ 90 kb/s, "
                        "-6 ~ 120, -9 ~ 150, -12.5 ~ 195)")
    m = ap.add_argument_group("metadata options")
    m.add_argument("--title")
    m.add_argument("--artist", action="append", default=[], help="may be used multiple times")
    m.add_argument("--album")
    m.add_argument("--tracknumber")
    m.add_argument("--genre", action="append", default=[], help="may be used multiple times")
    m.add_argument("--date", metavar="YYYY-MM-DD")
    m.add_argument("-t", "--comment", action="append", default=[], metavar="tag=val",
                   help="add an extra comment; may be used multiple times")
    m.add_argument("--picture", action="append", default=[], metavar="file",
                   help="attach album art (a JPEG or PNG file, or opusenc's "
                        "TYPE|MIME|DESCRIPTION|SIZE|FILE); may be used multiple times")
    m.add_argument("--discard-comments", action="store_true", help="don't keep metadata when transcoding")
    m.add_argument("--discard-pictures", action="store_true", help="don't keep pictures when transcoding")
    r = ap.add_argument_group("ReplayGain")
    r.add_argument("--no-replaygain", action="store_true",
                   help="don't write REPLAYGAIN_TRACK_GAIN/PEAK (measured on the decoded output, "
                        "ReplayGain 2.0: ITU-R BS.1770-4, -18 LUFS); album gain: mule-gain")
    a = ap.parse_args()
    say = (lambda *s: None) if a.quiet else (lambda *s: print(*s, file=sys.stderr))  # noqa: E731

    x, fs, tags, pictures = read_input(a.input)
    if a.discard_comments:
        tags = []
    if a.discard_pictures:
        pictures = []
    tags = [(k, v) for k, v in tags if not k.startswith("REPLAYGAIN_") and k != "ENCODER"
            and k != "METADATA_BLOCK_PICTURE"]
    for key, vals in (("TITLE", [a.title]), ("ARTIST", a.artist), ("ALBUM", [a.album]),
                      ("TRACKNUMBER", [a.tracknumber]), ("GENRE", a.genre), ("DATE", [a.date])):
        vals = [v for v in vals if v]
        if vals:
            tags = [(k, v) for k, v in tags if k != key] + [(key, v) for v in vals]
    for c in a.comment:
        if "=" not in c:
            sys.exit(f"mule-enc: --comment {c!r}: tag=val expected")
        k, v = c.split("=", 1)
        tags.append((k.upper(), v))
    pictures += [picture_arg(p) for p in a.picture]

    if x.shape[1] > 2:
        say(f"Downmixing {x.shape[1]} channels to stereo")
    x = to_stereo(x)
    if fs != 44100:
        import soxr
        say(f"Resampling from {fs} Hz to 44100 Hz")
        x = soxr.resample(x, fs, 44100, quality="VHQ")
    if a.quality is not None:
        settings = params.Params(q_db=float(min(max(a.quality, Q_MIN), Q_MAX)))
    else:
        settings = params.for_bitrate(a.bitrate or 128.0)
    q = settings.q_db
    body = [("ENCODER", VERSION)] + tags + [oggfile.picture_comment(p) for p in pictures]

    data, nbytes = native.c_encode(x, settings, body)
    if not a.no_replaygain:
        m = replaygain.Meter(44100)
        m.add(decoded(data))
        rg = replaygain.tags(m.loudness(), m.peak)
        data = oggfile.replace_comments(
            data, oggfile.build_comments(oggfile.parse_comments(oggfile.packets(data)[1][0])[0],
                                         body + list(rg.items())))
        say(f"ReplayGain: track {rg['REPLAYGAIN_TRACK_GAIN']}, peak {rg['REPLAYGAIN_TRACK_PEAK']}")
    if a.output == "-":
        sys.stdout.buffer.write(data)
    else:
        with open(a.output, "wb") as f:
            f.write(data)
    dur = len(x) / 44100
    if dur > 0:
        say(f"{a.output}: {dur:.1f} s, quality {q:+.1f} dB, {nbytes * 8 / dur / 1000:.1f} kb/s (audio), "
            f"{len(data) * 8 / dur / 1000:.1f} kb/s (file)")


if __name__ == "__main__":
    main()
