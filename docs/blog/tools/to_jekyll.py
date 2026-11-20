"""Turns a blog post of docs/blog/ into a Jekyll post of the blog (berettavexee.github.io):
front matter (author from the blog's _config.yml), the review notes dropped (from "## Notes pour la relecture"), the H1 title moved to
the front matter, the "jet" mention dropped, figures copied to assets/img/mule-<name> and their
links rewritten (alt text on one line).

    .venv/bin/python docs/blog/tools/to_jekyll.py docs/blog/01-anatomie.md <blog repo> \\
        --date 2026-11-19 --slug mule-anatomie-codec-audio --tags "audio codec ..."
"""
import argparse
import os
import re
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("blog")
    ap.add_argument("--date", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--tags", default="audio codec MULE")
    ap.add_argument("--author", help="default: author.name of the blog's _config.yml")
    a = ap.parse_args()
    if not a.author:
        cfg = open(os.path.join(a.blog, "_config.yml"), encoding="utf-8").read()
        m = re.search(r"^author:\s*\n\s+name:\s*(.+)$", cfg, re.M)
        assert m, "no author.name in _config.yml: pass --author"
        a.author = m.group(1).strip().strip("'\"")
    s = open(a.src, encoding="utf-8").read()
    i = s.find("\n---\n\n## Notes pour la relecture")
    if i >= 0:
        s = s[:i]
    s = s.rstrip() + "\n"
    first, rest = s.split("\n", 1)
    assert first.startswith("# "), "the post must start with its H1 title"
    title = first[2:].strip()
    body = rest.lstrip("\n")
    body = re.sub(r"^(\*[^*\n]*? billet [^*]*?»\.)[^*]*\*\n", r"\1*\n", body, count=1)
    figdir = os.path.join(os.path.dirname(os.path.abspath(a.src)), "fig")
    figs = []

    def img(m):
        name = os.path.basename(m.group(2))
        figs.append(name)
        return f"![{' '.join(m.group(1).split())}](/assets/img/mule-{name})"

    body = re.sub(r"!\[(.*?)\]\(fig/([^)]+)\)", img, body, flags=re.S)
    head = (f'---\nlayout: post\ntitle: "{title}"\ndate: {a.date}\nauthor: "{a.author}"\n'
            f"language: french\ntags: {a.tags}\n---\n\n")
    out = os.path.join(a.blog, "_posts", f"{a.date}-{a.slug}.md")
    open(out, "w", encoding="utf-8").write(head + body)
    for n in figs:
        shutil.copy(os.path.join(figdir, n), os.path.join(a.blog, "assets", "img", "mule-" + n))
    print(f"{out}: {len(figs)} figures")


if __name__ == "__main__":
    main()
