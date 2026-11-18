"""mule-gain: ReplayGain 2.0 tags for Ogg MULE files, as vorbisgain or metaflac
--add-replay-gain do: each file's track gain and peak, and with -a the album's (all the files
given, measured together), written into its comment header without re-encoding (the audio
pages are kept, renumbered). Loudness by ITU-R BS.1770-4 on the decoded output (the fixed-point
decoder, the player's), -18 LUFS reference.

Usage: mule-gain [-a] [-n] [-q] file.mule ..."""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "tools")]
from mule import oggfile, replaygain  # noqa: E402
from mule_enc import decoded  # noqa: E402


def main():
    ap = argparse.ArgumentParser(prog="mule-gain", description="ReplayGain tags for Ogg MULE files.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("-a", "--album", action="store_true", help="also the album gain: the files given are one album")
    ap.add_argument("-n", "--dry-run", action="store_true", help="measure and print, change nothing")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    meters, datas = [], []
    for path in a.files:
        data = open(path, "rb").read()
        pk = oggfile.packets(data)
        if len(pk) < 2 or pk[0][0][:8] != b"MULEHead" or pk[1][0][:8] != b"MULETags":
            sys.exit(f"mule-gain: {path}: not an Ogg MULE file")
        m = replaygain.Meter(44100)
        m.add(decoded(data))
        meters.append(m)
        datas.append(data)
    album = replaygain.Meter.merge(meters) if a.album else None
    for path, data, m in zip(a.files, datas, meters):
        rg = replaygain.tags(m.loudness(), m.peak, album)
        if not a.quiet:
            print(f"{path}: track {rg['REPLAYGAIN_TRACK_GAIN']} ({m.loudness():.2f} LUFS), peak "
                  f"{rg['REPLAYGAIN_TRACK_PEAK']}"
                  + (f"; album {rg['REPLAYGAIN_ALBUM_GAIN']}, peak {rg['REPLAYGAIN_ALBUM_PEAK']}" if album else ""))
        if a.dry_run:
            continue
        vendor, items = oggfile.parse_comments(oggfile.packets(data)[1][0])
        items = [(k, v) for k, v in items if not k.startswith("REPLAYGAIN_")] + list(rg.items())
        out = oggfile.replace_comments(data, oggfile.build_comments(vendor, items))
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(out)
        os.replace(tmp, path)


if __name__ == "__main__":
    main()
