# MULE

*A lossy music codec that nobody asked for.*

A mule is what you get when you cross a horse and a donkey. It is sturdy, it carries its load,
it is famously stubborn, and it has no offspring. MULE is the same thing for audio: a cross
between **Opus**, **Vorbis** and **AAC**, built to run on one tiny music player, the Snowsky
Echo Mini (a Cortex-M3 without a floating-point unit). It carries the music, its refuse to go
at low bitrates, and it will not start a dynasty.

This is an **experimental, learning project**. It does not try to replace anything, and it
does not. If you want a good lossy codec, **use Opus**. If you want to see what happens when some idiot
builds one from scratch, measures everything, listens blind, and writes down every idea that did
not work, read on.

## What it is made of

| Body part | Taken from | Notes |
|---|---|---|
| MDCT 2048 / 8 × 256, block switching, grouping of short windows | AAC | the same layout, the same transient handling |
| Window shape (power-complementary "Vorbis" slopes) | Vorbis | |
| Ogg container, gapless granules, comment header | Vorbis / Opus | `MULETags` is `OpusTags` with another name |
| Band energies coded apart from a normalized shape, noise filling | Opus (CELT) | energy is always right, even when the shape is coarse |
| Pre-echo control in the psychoacoustic model | AAC | the only pre-echo idea that worked (see below) |
| Shape quantizer: trellis-coded quantization (TCQ), 64 states, one trellis running across the bands | JPEG 2000 part 2, VVC | the one original-ish part |
| Entropy coding: rANS with adaptive multi-symbol CDFs | rANS (J. Duda), CDF adaptation as in AV1 | 134 adaptive models, trained initial tables, 8-symbol alphabet for the coefficients |
| Decoder in integers only, bit-exact everywhere | necessity | the target has no FPU |

Why hasn’t anyone tried this combination before? Back when Opus was being developed, most of these techniques were tied up in software patents. For some of them, that’s no longer the case, and I couldn’t care less.

## Results

Measured on 30 tracks drawn at random from my music library and never used for tuning, at equal
real bitrate (curves interpolated). ODG is PEAQ's score: 0 = no difference *(audio transparency)*, −1 = audible but not
annoying *(good)*, −4 = very annoying (shit). ViSQOL (Virtual Speech Quality Objective Listener) scores range from 1 (the worst) to 5 (the best).

| | ODG @128 kb/s | ODG @160 kb/s | ODG (advanced) @128 / @160 | ViSQOL @128 | ODG @64 kb/s |
|---|---|---|---|---|---|
| Vorbis (libvorbis) | −0.45 | −0.16 | −0.63 / −0.34 | 4.47 | −2.32 |
| Opus (libopus) | **−0.12** | **0.00** | −0.45 / −0.24 | 4.54 | **−0.59** |
| MULE v2 | −0.22 | −0.03 | −0.39 / −0.16 | 4.60 | −1.66 |
| MULE v3 | −0.17 | −0.01 | **−0.36 / −0.14** | **4.61** | −1.29 |

In plain words:
- **at 128 kb/s and above**, MULE beats Vorbis everywhere, loses to Opus on PEAQ's basic score,
  and wins on the advanced score and ViSQOL. In blind ABX tests (16 trials per excerpt, on the six
  excerpts where PEAQ saw the biggest gap), I could tell MULE v2 at 128 kb/s neither from
  the original nor from Opus at the same rate (best score 11/16; 12 is needed). v3 closed about
  40 % of the remaining PEAQ gap; nobody listened to it, since nobody could hear the old one;
- **at 64 kb/s**, the mule sits down in the road. Opus is far better: it has a decade of tools for
  low rates (bandwidth reduction, intensity stereo, band folding) that MULE never got;
- **on the device**, MULE v2 decodes a whole album at 139 kb/s with core B at **59 MHz** on average
  (Opus: 50 to 55 MHz), in 30 KiB of code and tables (Opus: 71 KiB) and 91 KiB of RAM (Opus:
  73 KiB). Its output is the same, bit for bit, on the PC, on the firmware's emulator and on a
  Cortex-M3 under QEMU. The v3 decoder needs 8 % fewer instructions under QEMU; it has not
  been ported to the player yet.

So, officially: a codec that is worse than Opus on almost every count, and sometimes as good.
This is a surprise; outperforming Vorbis was by no means a sure thing. Coming close to Opus
was unexpected.

### Why so many machines, and so few ears

At 128 kb/s, telling two modern codecs apart is close to impossible for a normal human being,
that is, for anyone who has not spent the last twenty years training on Hydrogenaudio's ABX
threads. At 160 kb/s, forget it. I tried, honestly, with sixteen trials per excerpt, a decent 
DAC and headphone and mostly scored what a coin would. So almost every decision in this 
project was taken by automated measures instead: PEAQ (basic and advanced), ViSQOL, and an 
internal noise-to-mask ratio, at equal real bitrate, on excerpts never used for tuning, 
with confidence intervals.

Those machines have their own blind spots, and this project walked into most of them:
- **above 20 kHz**: PEAQ counts the decoded signal's bandwidth, so coding noise between 20 and
  22 kHz, which almost nobody hears, gained PEAQ points at low rates and lost them at high rates;
- **noise-filled bands**: replacing a band by noise of the same energy fools a waveform
  comparison in one direction or the other. Lowering that noise by 3 dB pleased PEAQ and
  displeased ViSQOL, and only a listener can say which one is right;
- **difficult excerpts**: a sparse pitch pipe gets −3.9 from PEAQ's basic model whatever the
  codec (Opus too, at 192 kb/s), while the advanced model calls the same file transparent;
- **the metrics disagree**: MULE is behind Opus on PEAQ's basic score and ahead on its advanced
  score, on ViSQOL and on the noise-to-mask ratio, on the same files.

The machines are good at saying that something changed, and at ranking ideas that make a real
difference. They are poor judges of differences of a few hundredths, which is exactly where a
codec at 128 kb/s lives. Hence the rule followed here: keep an idea only if several measures
agree on an independent test set, and let the ears have the last word.

## What was actually learned

**TCQ is worth it.** Replacing a scalar quantizer by an 8-state trellis (levels at half the step,
the trellis state giving the parity, a Viterbi search in the encoder) gained about +0.06 ODG at
128 kb/s and +0.04 at 160 kb/s, at equal rate, for a decoder cost of one lookup in a table of
coefficient. It was also the difference in blind listening at 160 kb/s: transparent on 6 critical
excerpts out of 6, against 5 out of 6 with the scalar quantizer. Making the Viterbi use the real
adaptive-model costs (with each survivor's contexts) added a little more.

**A bigger trellis, if it runs across the bands (format v3).** The v2 trellis restarted from
state 0 at the start of every band, and took three coefficients to open its paths: a real loss
in bands of 8. Simply carrying the state from one band to the next gained nothing; what worked
was one Viterbi search over all the coded bands of a frame, choosing where a band ends together
with where the next one starts, and then more states: 64 instead of 8. At equal rate on the test
set, +0.036 ODG at 128 kb/s and +0.015 at 160 kb/s, all metrics agreeing: the biggest encoder
gain since TCQ itself. The decoder pays with a 256-byte table, nothing else. The encoder pays
with a Viterbi eight times wider; estimating the allocation choices on a small trellis, and
computing each subset's candidates once per coefficient, brought it back to about 4 times real
time (v2: 6). A 48-state trellis was tried too, because why not: worse than 32 states, since
good trellises come from convolutional codes and those like powers of two.

The same release halved the coefficients' alphabet (8 symbols and an escape instead of 16),
for no loss of rate: the decoder updates half as many CDF entries, and uses 8 % fewer
instructions than v2 on the Cortex-M3 (`spec/FORMAT.md`, `eval/results/B-LOG.md`, `C-LOG.md`).

**The last gap to Opus, window by window.** Where does MULE still lose to Opus on PEAQ's basic
score? Everywhere a little (three windows out of four) and mostly in loud, dense, distorted
rock. MULE's coding noise there is *lower* than Opus's in every frequency region, by the
internal model; what PEAQ dislikes is the temporal envelope inside each band (its modulation
difference). More short blocks made it worse. A Haar transform inside the long frames' bands,
trading frequency resolution for time resolution where needed (CELT's `tf_change`, roughly),
did exactly what was hoped on rock (+0.026 ODG at a fixed level) and cost bits everywhere else;
choosing the level frame by frame left +0.003 on the development set, below the threshold.
Abandoned (`eval/results/D-LOG.md`, `H-LOG.md`).

**Pre-echo, a collection of dead ends.** PEAQ's diagnostic variables (MOVs) said that what was
left of the gap to Opus came from frames where the noise is concentrated: attacks in long frames,
voice, dense distorted rock. Here is what was tried, all measured at equal rate:

| Idea | Verdict |
|---|---|
| AAC's pre-echo control (a long frame's mask may not rise more than 10 dB over the previous one) | **kept**: +0.010 / +0.014 ODG |
| Temporal noise shaping (TNS, as in AAC), long frames, a format change | correct (checked bit-exact), and −0.005 ODG at best: abandoned |
| Tonality from unpredictability (MPEG psychoacoustic model 2) | strings' vibrato looks like noise: violin and trumpet lost 0.24 |
| Terhardt's level-dependent spreading | neutral |
| Masks added as a power law | −0.03 to −0.18 |
| More bits for short (transient) frames | at the noise level of the measurement |
| A lower transient-detector threshold | slightly worse |
| A 23rd band up to 22 kHz (format change) | a pure PEAQ artefact: rewarded at low rates, penalized at high rates, inaudible either way |
| A spectral tilt for the noise filling (format change) | a more faithful spectrum, and nothing gained |

The real lesson is about **measurement**: several of these "gains" were the metrics' blind spots, 
and in the end the ears said the remaining gap was not audible.

**The low-band masks.** The one psychoacoustic fix that clearly helped: below about 2 kHz a band
spans almost 2 Bark, and computing its mask from the whole band's energy let noise through around
isolated low notes. Masks computed line by line in the 12 lowest bands gained up to +0.2 ODG on
an orchestra and on triangles.

**The entropy coder: rANS, and where the cycles go.** Every symbol of the stream (block types,
energies, allocations, TCQ indices, signs) goes through a range-variant asymmetric numeral
system coder (rANS, Jarek Duda's idea): a 32-bit state, 15-bit probabilities, renormalised by
16-bit words. rANS works like a stack, so the encoder first runs through a packet forwards to
adapt its models exactly as the decoder will, then codes the symbols backwards; the decoder
reads forwards with one multiplication and no division per symbol. A side effect I liked: a
packet must end with the state back to its initial value and every word read, which gives a free
integrity check, and a damaged packet is simply dropped.
- **134 adaptive models**, 15-bit CDFs adapted after every symbol as in AV1: fast at first,
  slower once a model has seen 16 then 32 symbols, every symbol keeping a minimum frequency so
  that nothing is ever impossible;
- **contexts** for the TCQ indices: the magnitudes of the two previous coefficients, the same
  coefficient in the previous frame (rescaled by the change of energy and allocation), and the
  band's allocation class;
- **trained initial tables**, reloaded at every key packet (every 0.93 s), so that a seek can
  start decoding from there.

What I learned there: the first design had 480 coefficient contexts, of which only 96 could ever
be reached, and compacting them changed the output by exactly zero bits. Retraining the initial
tables on 200 independent tracks saved 0.1 %: they were already good. Every
attempt at smarter contexts or other adaptation speeds was measured and rejected.

How much all this is worth, on the same coding operations of 20 excerpts at the default rate
(`eval/entropy_gain.py`; 28 kb/s of it are raw bits, mostly signs, that nothing compresses):

| Entropy coding | Rate | vs MULE |
|---|---|---|
| fixed-length codes (none at all) | 231.9 kb/s | +141 % |
| adaptive, without contexts, uniform start | 110.3 kb/s | +14.5 % |
| trained tables per context, frozen (AAC-style, minus Huffman's rounding) | 100.5 kb/s | +4.3 % |
| MULE: adaptive, with contexts, trained start | 96.4 kb/s | |

rANS itself codes within 0.01 % of these ideal costs: any good arithmetic coder would do as
well. Why rANS, then? Honestly, by accident: I came across Jarek Duda's papers while looking for
anything that would explain Opus's PVQ, the pyramid vector quantizer, a piece of black magic
somewhere between a lattice and the Cthulhu mythos, which I still do not understand (a PVQ
variant of MULE was built and measured, and it lost to the trellis: see `docs/VARIANTS-BC.md`).
I left with no grasp of PVQ and a very nice entropy coder. It also happens to be fast to decode,
which mattered on the player, and the compression comes from the modelling:
the contexts are worth about 13 %, the adaptation about 4 % on top of trained tables. And on the
Cortex-M3, this part costs more than the transform: **63 % of the v2 decoder's instructions** go to
finding each symbol in its CDF and updating up to 16 entries afterwards, more than the inverse
MDCT and the synthesis together. That is where cycles would be saved, if they ever had to be.

**The last squeeze.** A round of eight measurements asked whether the format or the
encoder still had easy gains: smoother inter-frame contexts, contexts looking at the next frame,
interpolated energies, rarer key packets, a frame-wide Viterbi on the allocations, a Viterbi on
the frame decisions, the TCQ looking one frame ahead, and a CMA-ES tuning of the encoder's knobs.
None reached its threshold (2 % of the rate for a format change, +0.01 ODG for the encoder); the
best was a 0.25 % saving that would have cost 4 KiB of RAM. The mule has been squeezed. The
tuning run taught one more lesson about measurement: an "equal-rate" objective whose two
measuring points both sat above the target rate let the optimizer win by extrapolation, and it
found that bias long before any real gain (`eval/results/M-LOG.md`).

**Fuzzing pays.** Coverage-guided fuzzing of the device decoder found, within minutes, that a
damaged stream could produce a negative allocation and make the decoder write outside its model
table. The format now bounds energies and allocations, and the decoder rejects anything else.

## Repository

| Path | Content |
|---|---|
| `spec/FORMAT.md` | the stream format, normative (in French) |
| `core/` | the codec in C: `enc.c` (encoder), `dec.c` (decoder, integers only, the reference), `model.c` / `models.c` (adaptive models), `rans.c` (rANS coder) |
| `tools/` | `mule-enc`, `mule-dec`, `mule-gain`, and the generators of the tables in `core/` |
| `py/mule/` | Python bindings (cffi), settings, Ogg comment handling, ReplayGain (BS.1770-4) |
| `eval/` | the evaluation: corpus building, reference codecs, metrics (internal NMR, PEAQ, ViSQOL), equal-rate comparisons, listening kits; logs and results in `eval/results/` |
| `tests/` | unit tests, and frozen decoder test vectors |
| `bench/qemu/` | Cortex-M3 benchmark under QEMU (instruction counts, bit-exactness) |
| `docs/` | `ARTICLE.md` (how MULE works, two pages), `PORT.md` (the port to the player), `V3-IDEAS.md`, `VARIANTS-BC.md`, `history/` |

Most of the documentation and logs are in French, my language.

## Building and using

Requirements: a C99 compiler, Python 3 with numpy, scipy, soundfile, soxr and cffi
(`requirements.txt`). For the evaluation: `opusenc`, `oggenc`, `ffmpeg`, and optionally
[GstPEAQ](https://github.com/HSU-ANT/gstpeaq) and [ViSQOL](https://github.com/google/visqol).

```sh
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt
make                                    # build/libmule.so, build/mule-dec
make test

tools/mule-enc in.flac out.mule         # 128 kb/s by default (my library average: VBR)
tools/mule-enc --bitrate 160 --title "..." --picture cover.jpg in.wav out.mule
tools/mule-gain -a album/*.mule         # ReplayGain 2.0, track and album
tools/mule-dec out.mule out.wav         # 16-bit WAV, the reference decoder
```

`mule-enc` takes `opusenc`'s options (`--bitrate`, `--title`, `--artist`, `--comment tag=val`,
`--picture`, `--discard-comments`...), any input libsndfile reads (or `-` for stdin), any sample
rate (resampled to 44.1 kHz, the only one the format knows), mono or more than two channels
(made stereo), and copies the tags and pictures of a FLAC input.

The evaluation corpus is not included (it comes from the EBU SQAM disc and a private music
library); `eval/corpus.py` shows how it was cut (the library's root in `MULE_LIBRARY`).

## Limits

44.1 kHz stereo only. Tuned for 128 to 160 kb/s; poor below 96 kb/s. One encoder, one decoder,
no ecosystem: nothing else in the world plays a `.mule` file, apart from one firmware on one
player.

## License

MIT (`LICENSE`).
