"""Figure 1 of the first blog post (docs/blog/PLAN.md): MULE's encoder and decoder, each block
coloured by the codec it comes from. Writes docs/blog/fig/fig1-pipeline.excalidraw (open it on
excalidraw.com to edit); docs/blog/tools/render.mjs turns it into an SVG.

    python docs/blog/tools/fig1_pipeline.py"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "fig", "fig1-pipeline.excalidraw")

# the codec each block comes from: (fill, legend)
ORIGIN = {
    "aac": ("#a5d8ff", "AAC"),
    "vorbis": ("#b2f2bb", "Vorbis"),
    "opus": ("#ffd8a8", "Opus (CELT)"),
    "tcq": ("#d0bfff", "JPEG 2000 (TCQ)"),
    "ans": ("#ffc9c9", "rANS (J. Duda), AV1"),
    "mule": ("#e9ecef", "MULE"),
}

rng = random.Random(7)
elements = []


def _id():
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))


def _base(kind, x, y, w, h, **kw):
    e = {"id": _id(), "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
         "strokeColor": "#1e1e1e", "backgroundColor": "transparent", "fillStyle": "solid",
         "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100,
         "groupIds": [], "frameId": None, "roundness": None, "seed": rng.randrange(1, 2**31),
         "version": 1, "versionNonce": rng.randrange(1, 2**31), "isDeleted": False,
         "boundElements": [], "updated": 1, "link": None, "locked": False}
    e.update(kw)
    elements.append(e)
    return e


def text(x, y, s, size=20, align="center", color="#1e1e1e", container=None, w=None):
    lines = s.split("\n")
    width = w or max(len(t) for t in lines) * size * 0.55
    height = len(lines) * size * 1.25
    if align == "center" and container is None:
        x -= width / 2
    return _base("text", x, y, width, height, strokeColor=color, text=s, originalText=s,
                 fontSize=size, fontFamily=1, textAlign=align, verticalAlign="middle",
                 containerId=container, lineHeight=1.25, baseline=round(size * 0.9),
                 autoResize=True)


def box(x, y, w, h, label, origin, size=18):
    r = _base("rectangle", x, y, w, h, backgroundColor=ORIGIN[origin][0], roundness={"type": 3})
    lines = label.split("\n")
    th = len(lines) * size * 1.25
    t = text(x, y + (h - th) / 2, label, size=size, container=r["id"], w=w)
    r["boundElements"].append({"type": "text", "id": t["id"]})
    return r


def arrow(a, b, side_a="right", side_b="left", label=None, dashed=False, shift=0):
    def anchor(e, side):
        cx, cy = e["x"] + e["width"] / 2 + shift, e["y"] + e["height"] / 2
        return {"right": (e["x"] + e["width"], cy), "left": (e["x"], cy),
                "top": (cx, e["y"]), "bottom": (cx, e["y"] + e["height"])}[side]
    (x0, y0), (x1, y1) = anchor(a, side_a), anchor(b, side_b)
    gap = 6
    dx, dy = x1 - x0, y1 - y0
    n = max((dx * dx + dy * dy) ** 0.5, 1)
    x0, y0 = x0 + gap * dx / n, y0 + gap * dy / n
    x1, y1 = x1 - gap * dx / n, y1 - gap * dy / n
    ar = _base("arrow", x0, y0, abs(x1 - x0), abs(y1 - y0), points=[[0, 0], [x1 - x0, y1 - y0]],
               lastCommittedPoint=None, startArrowhead=None, endArrowhead="arrow",
               strokeStyle="dashed" if dashed else "solid", roundness={"type": 2},
               startBinding={"elementId": a["id"], "focus": 0, "gap": gap},
               endBinding={"elementId": b["id"], "focus": 0, "gap": gap})
    a["boundElements"].append({"type": "arrow", "id": ar["id"]})
    b["boundElements"].append({"type": "arrow", "id": ar["id"]})
    if label:
        text((x0 + x1) / 2 + 10, (y0 + y1) / 2 - 12, label, size=16, align="left", color="#495057")
    return ar


W, H, GAP = 132, 76, 26
X0 = 40


def col(i):
    return X0 + i * (W + GAP)


text(col(4) + W / 2, 8, "MULE : le trajet d'une trame (23 ms, 1 024 échantillons)", size=28)

# encoder
YE = 230
text(X0, 100, "Encodeur — sur PC,\nen virgule flottante", size=20, align="left", color="#495057")
enc = [("PCM stéréo\n44,1 kHz", "mule", ""),
       ("Fenêtres,\nblocs courts", "vorbis", "AAC + Vorbis"),
       ("MDCT\n2048 ou 8×256", "aac", "AAC"),
       ("Stéréo\nL/R ou M/S", "aac", "AAC"),
       ("Énergies\n+ forme", "opus", "Opus"),
       ("Allocation\ndes bits", "mule", ""),
       ("TCQ\n64 états", "tcq", "JPEG 2000"),
       ("rANS\n134 modèles", "ans", "Duda, AV1"),
       ("Paquets\nOgg", "vorbis", "Vorbis, Opus")]
E = []
for i, (lab, org, small) in enumerate(enc):
    E.append(box(col(i), YE, W, H, lab, org, size=15 if "×" in lab else 18))
    if small:
        text(col(i) + W / 2 - (22 if i == 8 else 0), YE + H + 8, small, size=15, color="#868e96")
for a, b in zip(E[:-1], E[1:], strict=True):
    arrow(a, b)

# psychoacoustic model, above: from the transform, to the allocation
psy = box(col(3), 70, 2 * W + GAP, H + 4, "Modèle psychoacoustique\n(ce qui est masqué)", "aac", size=19)
arrow(E[2], psy, "top", "left")
arrow(psy, E[5], "right", "top")
text(col(5) + W / 2 + 22, 130, "le bruit de codage doit\nrester sous le masque", size=16, align="left", color="#495057")

# decoder, right to left, under the matching encoder blocks
YD = 470
text(X0, YD - 40, "Décodeur — sur le baladeur, en entiers seulement", size=20, align="left", color="#495057")
dec = [(8, "Paquets\nOgg", "vorbis"), (7, "rANS", "ans"), (6, "TCQ inverse\n+ bruit", "tcq"),
       (4, "Énergies\n× forme", "opus"), (3, "M/S inverse", "aac"), (2, "IMDCT,\nrecouvrement", "aac"),
       (0, "PCM\n16 bits", "mule")]
D = [box(col(i), YD, W, H, lab, org) for i, lab, org in dec]
for a, b in zip(D[:-1], D[1:], strict=True):
    arrow(a, b, "left", "right")
arrow(E[8], D[0], "bottom", "top", label="fichier .mule", dashed=True, shift=48)
text(col(5) + W / 2, YD + H + 10, "le bruit remplit les bandes sans bits", size=15, color="#868e96")

# legend
YL = 610
x = X0
for key in ("aac", "vorbis", "opus", "tcq", "ans", "mule"):
    fill, name = ORIGIN[key]
    _base("rectangle", x, YL, 26, 22, backgroundColor=fill, roundness={"type": 3}, strokeWidth=1)
    t = text(x + 36, YL - 2, name, size=17, align="left")
    x += 36 + t["width"] + 34

doc = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": elements,
       "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": {}}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(doc, open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"{len(elements)} elements -> {OUT}")
