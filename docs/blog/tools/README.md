# Figures of the blog posts

Diagrams in Excalidraw's style: a Python script per figure writes an `.excalidraw` file
(`docs/blog/fig/`, open it on excalidraw.com to edit by hand), and `render.mjs` turns it into a
standalone SVG drawn with rough.js (the library Excalidraw draws with), text in Excalidraw's
Virgil font (SIL Open Font License), embedded.

```sh
cd docs/blog/tools && npm install                    # rough.js, local (node_modules/, not in git)
mkdir -p fonts && curl -sSfL -o fonts/Virgil.woff2 \
    https://unpkg.com/@excalidraw/excalidraw@0.17.6/dist/excalidraw-assets/Virgil.woff2
cd ../../.. && .venv/bin/python docs/blog/tools/fig1_pipeline.py      # add "en" for the README's version
node docs/blog/tools/render.mjs docs/blog/fig/fig1-pipeline.excalidraw docs/blog/fig/fig1-pipeline.svg
```

Plots and data figures (2 to 10 of the first post) come from `figs.py`: matplotlib in xkcd
mode with the same Virgil font, converted to TTF once; text is drawn as paths, so the SVGs are
self-contained. It encodes EBU SQAM excerpts of the corpus (`data/corpus/`) with the C encoder,
reads its trace (band records: mask, power, allocation, stereo; `core/mule_enc.h`), decodes with
`build/mule-dec`, and reads the test-set CSVs of `eval/results/`.

```sh
.venv/bin/python -c "from fontTools.ttLib import TTFont; f = TTFont('docs/blog/tools/fonts/Virgil.woff2'); f.flavor = None; f.save('docs/blog/tools/fonts/Virgil.ttf')"
.venv/bin/python docs/blog/tools/figs.py              # all; or names: figs.py fig6 fig8
FIG_PNG=/some/dir .venv/bin/python docs/blog/tools/figs.py   # also PNG previews
```

Publishing: `to_jekyll.py` turns a post into the blog's Jekyll format (front matter, review notes
dropped, figures copied to `assets/img/mule-*`), in a clone of berettavexee.github.io:

```sh
.venv/bin/python docs/blog/tools/to_jekyll.py docs/blog/01-anatomie.md <clone> \
    --date 2026-11-19 --slug mule-anatomie-codec-audio --tags "audio codec MDCT psychoacoustique MULE ECHO-MINI"
```
