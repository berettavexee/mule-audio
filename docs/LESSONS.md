# What MULE taught me

The long version of the README's summary: every measured idea, kept or abandoned, with its
numbers. Measurements are at equal real rate, on excerpts never used for tuning; the logs behind
them are in `eval/results/` (in French). The thresholds: 2 % of the rate for a format change,
+0.01 ODG for an encoder change; since v4, once the algorithm had settled, a small encoder change
is kept if every judge agrees and no track regresses.

## Why so many machines, and so few ears

At 128 kb/s, telling two modern codecs apart is close to impossible for a normal human being,
that is, for anyone who has not spent the last twenty years training on Hydrogenaudio's ABX
threads. At 160 kb/s, forget it. I tried, honestly, with sixteen trials per excerpt, a decent 
DAC and headphone and mostly scored what a coin would. So almost every decision in this 
project was taken by automated measures instead: PEAQ (basic and advanced), ViSQOL, and an 
internal noise-to-mask ratio, at equal real bitrate, on excerpts never used for tuning, 
with confidence intervals. Since v4, Zimtohrli (Google's psychoacoustic distance) is the first
judge and ViSQOL no longer one: its small model saturates near transparency, and its small
regressions were never heard.

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
| A lower transient-detector threshold | slightly worse (then; see v5: the detector itself was wrong) |
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
- **135 adaptive models** (134 before v5), 15-bit CDFs adapted after every symbol as in AV1: fast at first,
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

## Formats v4 and v5: the noise, the encoder, and the measurements

The format barely changed after v3: v4 and v5 only change the noise the decoder puts where the
encoder sends no bits. Most of the work moved to the encoder, and most of the lessons to the way
it is measured (`docs/V4.md`, `docs/V5.md`).

**The judge you pick moves the optimum.** Tuning the encoder's psychoacoustic knobs with
Zimtohrli as the objective (CMA-ES on half the development set) gave −12 to −13 % of Zimtohrli on
tracks the search never saw, and −0.02 on PEAQ's basic score. Listening could not tell the two
settings apart (44 right answers out of 96). Optimising one metric walks away from another; when
they disagree, the ears decide, and they rarely can.

**Look at the worst tracks, then at their worst seconds.** The two clearest gains of v4 and v5
came from one track each: Garbage's cymbals, noise-filled with the right energy but the wrong
movement, gave the envelope guard and the short blocks triggered by the highs. A diagnostic tool
that splits Zimtohrli's similarity cell by cell (`eval/zimt_diag.py`) showed that all of MULE's
remaining loss is texture, not level, in high bands either noise-filled or coded sparsely; giving
them more bits, or coding them coarsely instead of filling them, made things worse.

**An idea that fails on average can work in one precise place.** Opus-like folding (copying the
decoded spectrum below into a band without bits) was abandoned in v4: it helped percussive music
and ruined tonal music, and no per-frame criterion could tell the two apart. Restricted to short
frames, where the attacks are, it kept the whole gain, touched no tonal track, and needed no bit
at all. It is the core of v5.

**The oldest parts hide the defects.** The transient detector compared each 2.9 ms block with a
memory that decayed by 3 dB per block. Between two glottal pulses of a voice, that memory fell far
enough for the next pulse to look like an attack: a fifth of a spoken voice's frames were switched
to short blocks, and pulsed sounds (Heilung, Kompromat, Aphex Twin) suffered the same. It had been
there from the start; it took a fix that made speech worse, and the question "why?", to find it.
The defect had also biased every study of short frames: intermediate 512-point blocks seemed to
"help soft attacks" on Kompromat, when they only limited the damage of short frames that should
never have been there. With a slower memory, the detector in the highs could become far more
sensitive, the opposite of the earlier "a lower threshold is worse".

**One wrong frame can cost a lot.** On Belenos (bagpipes), the more sensitive detector switched a
single frame to short blocks, in the middle of a drone: its harmonics blurred for 23 ms and PEAQ
took 0.077 off the whole track. A veto on very tonal frames fixed it, and changed nothing else.

**A toy model ranks; it does not measure.** A toy codec in numpy, with MULE's windows and
Zimtohrli as judge, found the direction of the highs detector's gain at 60 % of its size, and
promised a gain to per-band time-frequency switching (CELT's `tf_change`) that the real codec
could not reach: MULE's entropy coding, trained on time blocks, and its noise in the zeros of
coded bands cost more than the toy's gain.

**Measurement traps, again.** A quick screen that searched each variant's quality setting by
bisection had a noise of ±2 to 3 % per track: Zimtohrli moves by steps with the setting on some
tracks. Another screen interpolated between two settings both above the target rate and rewarded
the variants that spent the most bits, the M6 lesson in a new form. Only the full evaluation, four
points interpolated, counts. And validate on both sets: the test set (mostly rock) passed a
folding criterion that the development set (with piano and glockenspiel) rejected at once.

**The entropy coder is close to what this architecture allows.** A simulator that reproduces the
stream's cost exactly found the models' adaptation already optimal (mixing a fast and a slow rate
gained nothing), 30 % of the rate in coefficient signs that nothing compresses (HEVC's sign hiding
does not mix with a trellis quantizer), and only one cheap saving: the zeros' noise level, coded
with a model instead of 3 raw bits (−0.12 % of the rate), now part of v5.

