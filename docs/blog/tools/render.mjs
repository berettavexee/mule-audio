// Renders an .excalidraw file to a standalone SVG in Excalidraw's hand-drawn style: shapes by
// rough.js (the library Excalidraw draws with), text in the Virgil font, embedded. Handles the
// elements the figure scripts write: rectangles (rounded), arrows, text.
//   node docs/blog/tools/render.mjs in.excalidraw out.svg
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import rough from "roughjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const [, , src, dst] = process.argv;
const doc = JSON.parse(fs.readFileSync(src, "utf8"));
const els = doc.elements.filter((e) => !e.isDeleted);
const gen = rough.generator();
const font = fs.readFileSync(path.join(here, "fonts", "Virgil.woff2")).toString("base64");
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function opts(e) {
  return {
    seed: e.seed, roughness: e.roughness, stroke: e.strokeColor, strokeWidth: e.strokeWidth,
    fill: e.backgroundColor === "transparent" ? undefined : e.backgroundColor,
    fillStyle: e.fillStyle, fillWeight: e.strokeWidth / 2, hachureGap: 4 * e.strokeWidth,
    bowing: 1, preserveVertices: true,
  };
}

function paths(drawable, dash) {
  return gen.toPaths(drawable).map((p) =>
    `<path d="${p.d}" stroke="${p.stroke}" stroke-width="${p.strokeWidth}" fill="${p.fill || "none"}"` +
    (dash && p.fill === "none" ? ` stroke-dasharray="8 8"` : "") + ` stroke-linecap="round"/>`).join("\n");
}

function roundedRect(x, y, w, h) {
  const r = Math.min(w, h) * 0.25 > 32 ? 32 : Math.min(w, h) * 0.25;
  return `M ${x + r} ${y} L ${x + w - r} ${y} Q ${x + w} ${y}, ${x + w} ${y + r} L ${x + w} ${y + h - r} ` +
    `Q ${x + w} ${y + h}, ${x + w - r} ${y + h} L ${x + r} ${y + h} Q ${x} ${y + h}, ${x} ${y + h - r} ` +
    `L ${x} ${y + r} Q ${x} ${y}, ${x + r} ${y}`;
}

const byId = Object.fromEntries(els.map((e) => [e.id, e]));
const out = [];
let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
const grow = (x, y) => { minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y); };

for (const e of els) {
  if (e.type === "rectangle") {
    const d = e.roundness ? gen.path(roundedRect(e.x, e.y, e.width, e.height), opts(e))
                          : gen.rectangle(e.x, e.y, e.width, e.height, opts(e));
    out.push(paths(d));
    grow(e.x, e.y); grow(e.x + e.width, e.y + e.height);
  } else if (e.type === "arrow") {
    const pts = e.points.map(([px, py]) => [e.x + px, e.y + py]);
    const o = { ...opts(e), fill: undefined };
    out.push(paths(gen.linearPath(pts, o), e.strokeStyle === "dashed"));
    const [ax, ay] = pts[pts.length - 2], [bx, by] = pts[pts.length - 1];
    const ang = Math.atan2(by - ay, bx - ax), L = 16, s = 0.45;
    for (const sg of [1, -1]) {
      const hx = bx - L * Math.cos(ang + sg * s), hy = by - L * Math.sin(ang + sg * s);
      out.push(paths(gen.line(bx, by, hx, hy, o)));
    }
    pts.forEach(([x, y]) => grow(x, y));
  } else if (e.type === "text") {
    const lines = e.text.split("\n"), lh = e.fontSize * (e.lineHeight || 1.25);
    let x = e.x, anchor = "start";
    const box = e.containerId && byId[e.containerId];
    if (e.textAlign === "center") { x = box ? box.x + box.width / 2 : e.x + e.width / 2; anchor = "middle"; }
    const y0 = box ? box.y + (box.height - lines.length * lh) / 2 : e.y;
    const spans = lines.map((t, i) =>
      `<tspan x="${x}" y="${y0 + i * lh + e.fontSize * 0.95}">${esc(t)}</tspan>`).join("");
    out.push(`<text font-family="Virgil" font-size="${e.fontSize}" fill="${e.strokeColor}" text-anchor="${anchor}">${spans}</text>`);
    grow(e.x, e.y); grow(e.x + e.width, e.y + e.height);
  }
}

const pad = 24, W = maxX - minX + 2 * pad, H = maxY - minY + 2 * pad;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX - pad} ${minY - pad} ${W} ${H}" width="${W}" height="${H}">
<defs><style>@font-face { font-family: "Virgil"; src: url(data:font/woff2;base64,${font}) format("woff2"); }</style></defs>
<rect x="${minX - pad}" y="${minY - pad}" width="${W}" height="${H}" fill="${doc.appState?.viewBackgroundColor || "#ffffff"}"/>
${out.join("\n")}
</svg>
`;
fs.writeFileSync(dst, svg);
console.log(`${els.length} elements -> ${dst} (${Math.round(W)} x ${Math.round(H)})`);
