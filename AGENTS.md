# AGENTS.md — Aesthetic Channel

## Project goals
- Original Aura / Flow / Tunnel ambient animations.
- Linux, CPU-only, 4 GB RAM or less; no dedicated GPU.
- Stream frames directly to FFmpeg; 720p previews, 1080p production. 4K only
  after a measured 1 s test.
- Seamless periodic loops; 2–3 hour videos via loop + stream copy, not a
  multi-hour unique render.
- Silent and properly licensed audio versions.
- Repeatable production that still varies between uploads (`--seed`).

## Environment
- Use `venv/bin/python`. Dependencies: `requirements.txt` (numpy 2.5.4,
  Pillow 13.0.0). There is no package/build system.
- Rebuild the environment with:
  `python3 -m venv venv && venv/bin/pip install -r requirements.txt`.
- `ffmpeg` and `ffprobe` (6.1.1 here) are required.
- This is a 4 GB CPU-only machine; rendering is single-threaded numpy.
  Measured: ~0.65 s/frame at 720p, ~1.8 s/frame at 1080p native. Do not
  assume realtime.

## Production entry points
- `scripts/generate_loop_v7.py` — **current renderer**. Styles `flow`,
  `silk` (Golden Ratio $\phi$ harmonic fluid caustics), `tunnel`, `aura`;
  sizes `720p`, `1080p`, experimental `4k`; streams raw RGB24 into
  x264. Supports `--seconds`, `--fps`, `--seed`, `--crf`, `--preset`,
  `--render-scale`. v7 is the "DNA" renderer: every style derives palette
  and motion from the seed, so the same style looks different per upload.
  Flow picks Molten Amber / Sapphire Plasma / Violet Flare and randomises
  current direction and x-frequency; Silk picks Deep Ocean Cyan /
  Amethyst Nebula / Emerald Aurora / Crimson Sunset plus a frequency
  scale. Golden Ratio wave frequencies ($\phi \approx 1.618$) are
  unchanged from v6.
- `scripts/generate_loop_v6.py` — previous renderer, superseded by v7.
  Same chemistry without the per-seed palette and motion variation; keep
  for comparing against pre-DNA output.
- `scripts/generate_loop_v5.py` — **frozen** reference after the molten
  Flow and Silk release; do not modify.
- `scripts/make_long_video.py` — repeats a *seamless* short loop to a long
  MP4 with stream copy; optional licensed audio.
- `scripts/make_ambient_audio.py` — synthesises a seamless, license-free
  ambient bed as a 48 kHz stereo WAV. Every oscillator, LFO and reverb
  tail is built over exactly one loop period, so `make_long_video.py` can
  stream-loop it with no crossfade and no click.
- `scripts/analyze_track.py` — screens an audio file against the
  relaxation spec (tempo, transients, brightness, LUFS, true peak, LRA)
  and exits non-zero on rejection.
- Legacy scripts `generate_loop.py`, `_v2.py`, `_v3.py`,
  `_v3_improved.py` remain for reference. Do not start new work on them.
  Known issues: v3 names every style's default output `tunnel_v2.mp4`
  (pass `--output` explicitly); v1 leaves PNG frame dirs that can leak
  into a later shorter render.
- Backups: `backups/20261026_210538/` (pre-v4 code),
  `backups/20261026_222642/` (final v4 nebula + AGENTS.md), and
  `backups/20261026_223401/` (v5 nebula state before the molten
  Flow rewrite).

## Commands
720p Flow preview (fast):
```bash
venv/bin/python scripts/generate_loop_v7.py --style flow --size 720p \
  --seconds 10 --seed 7 --preset ultrafast --output previews/flow_preview.mp4
```

1080p production (on 4 GB, 0.5 internal scale is ~7x faster and still
outputs 1920x1080 via lanczos):
```bash
venv/bin/python scripts/generate_loop_v7.py --style flow --size 1080p \
  --seconds 30 --seed 7 --render-scale 0.5 --preset veryfast \
  --output output/flow_30s_1080p.mp4
```

Long video (silent, then with licensed audio):
```bash
venv/bin/python scripts/make_long_video.py output/flow_30s_1080p.mp4 \
  --hours 2.5 --output output/flow_2h30.mp4

venv/bin/python scripts/make_long_video.py output/flow_30s_1080p.mp4 \
  --hours 2.5 --audio audio/atlasaudio-ambient-lofi-576613.mp3 \
  --output output/flow_2h30_audio.mp4
```

Focused verification:
```bash
venv/bin/python tests/test_periodicity.py
# 2 s smoke render (~1 min at 720p)
venv/bin/python scripts/generate_loop_v7.py --style flow --seconds 2 \
  --preset ultrafast --output /tmp/flow_smoke.mp4
# Time + peak RSS
/usr/bin/time -v venv/bin/python scripts/generate_loop_v7.py ...
# Inspect output
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_type,codec_name,width,height -of default=nw=1 FILE
```

Do not render multi-hour videos during tests. Use 1–5 second renders.

## Periodicity invariants (Flow)
- Legacy v3 Flow is **not** horizontally periodic: measured edge mismatch
  was 74–79 (of 255) because its x frequencies are not integer multiples
  of π. v4 replaces that field; do not copy v3's Flow math.
- v7 randomises motion direction and x-frequency scale per seed and swaps
  palettes. That variation does not relax the rules below: every seed must
  still pass `tests/test_periodicity.py` for Flow and Silk.
- The x grid is exactly one period: pixel x spans `[-1, 1)` (right edge
  exclusive), so tiling/repeating is seamless. `tests/test_periodicity.py`
  checks an endpoint-inclusive grid at x = -1 and x = +1.
- Every x-dependent term must be `sin`/`cos` of an integer multiple of
  `pi * X`, or a function of an already-periodic field (e.g.
  `sin(theta1)`).
  - Do **not** feed raw `theta1`/`theta2` into `sin` with fractional
    multipliers: at the seam `theta1` differs by `2*pi`, so
    `sin(1.3*theta1)` is not periodic. Use `sin(1.3*sin(theta1))` or an
    integer multiplier.
- Every phase-dependent term must use an integer multiple of `phase`.
  `phase` runs 0 → 2π over `fps * seconds`, so the last frame leads
  correctly back to the first.
- Foreground star flares (legacy v4 Flow only) must be built on
  `sin(pi*(X - x0))` (exact period 2), never raw Gaussians in `X`.
- Flow has no vignette or glow (spec requirement). Coverage shaping
  must come from palette masks on the already-periodic field `n`
  itself; an X-dependent spatial envelope breaks the seam.
- Any shader change must keep `tests/test_periodicity.py` passing
  (float32 tolerance is 1e-2 on the 0–255 scale).

## Runtime notes
- Measured 2026-10-26 (molten v5 Flow): 720p 12 s (288 frames)
  veryfast = 3:13, 186 MB peak RSS (~0.67 s/frame). Warm coverage
  measured 78–82% (deep-dark channels 12–15%) on the encoded file.
  Adjacent-frame mean |diff| ≈ 1.7/255 (slow, no jitter); loop-wrap
  diff is equal to or below interior diffs. Rendering is the
  bottleneck at 720p/1080p, not x264.
- Use `--render-scale 0.5` for long 1080p loops on this box. Quality loss
  is small because the artwork is smooth gradients.
- Generate a 20–60 s seamless loop, then `make_long_video.py`. The
  latter copies video and only AAC-encodes optional audio, so 2–3 h
  outputs take seconds and no extra RAM.
- Preview `--preset ultrafast`; production `veryfast`; CRF 18 default.
- Measured 2026-10-29 (v7 Flow, seed 7, 720p 2 s smoke = 48 frames):
  19.1 s at ultrafast, 137 MB peak RSS (~0.40 s/frame). v7 has **not**
  been re-measured at 1080p; use the v5 figure (~1.8 s/frame, or ~0.5x
  with `--render-scale 0.5`) as the planning number.
- 4K native is untested on 4 GB (likely slow); `--render-scale 0.5`
  produces a 3840x2160 file within the measured memory budget.

## Audio beds
- `scripts/make_ambient_audio.py` builds the pad directly as an FFT
  spectrum (additive partials plus sidebands), adds a shaped noise bed,
  and convolves it with a circular reverb. Output is original work: no
  license, no attribution, no Content ID exposure.
- Every frequency, LFO and amplitude pulse is snapped to a whole number of
  cycles per loop, and the reverb tail wraps rather than crossfades. Do
  **not** add a time-domain fade, crossfade or delay afterwards - any of
  them reopens the seam. Verify with `tests/test_audio_loop.py`.
- Pitch classes default to `minor9` / `open5` / `sus2`. Voicings are
  intentionally wide (four octaves); stacking every tone inside one
  octave dumps 60%+ of the power into 160-440 Hz and sounds muddy.
- `scripts/analyze_track.py` holds the relaxation spec in constants at the
  top of the file: tempo 55-80 BPM (no pulse passes, as a drone),
  transient index < 6x median, energy centroid < 1500 Hz, -24..-15 LUFS,
  true peak <= -1 dBFS, LRA <= 9 LU.
- Evidence behind that spec, for descriptions - do not overclaim:
  meta-analyses find the largest stress effects at 60-90 BPM (de Witte et
  al. 2020/2022); slow tempo raises salivary oxytocin and lowers cortisol
  and HR (Ooishi et al. 2017). "Weightless cuts anxiety 65%" is a
  commissioned Mindlab study, not peer reviewed. Binaural-beat evidence is
  mixed and the effect disappears on mono phone speakers, so do not claim
  it.
- Measured 2026-10-29 (180 s, seed 7, A2 minor9): 27 s render, 591 MB peak
  RSS, wrap step 0.0286 against neighbours 0.0339/0.0263 (0.84x), -20.0
  LUFS, -8.6 dBFS peak. `analyze_track.py` scores it 100/100. The loop join
  survives AAC muxing twice inside a 400 s file with no step above the
  normal sample-difference distribution.
- The licensed `atlasaudio` track measures -10.2 LUFS with an 8.7x
  transient index, so the spec rejects it as a background bed. It is fine
  as foreground audio, but needs about -10 dB to sit under visuals.

```bash
# 3-minute bed: 66 BPM, A minor 9
venv/bin/python scripts/make_ambient_audio.py --seconds 180 --seed 7 \
  --output audio/generated/ambient_180s_a2_minor9.wav

# screen candidates before trusting the word "calming"
venv/bin/python scripts/analyze_track.py audio/candidates/*.mp3

venv/bin/python tests/test_audio_loop.py
```

## Assets and licensing
- `audio/atlasaudio-ambient-lofi-576613.mp3` is covered by the Pixabay
  license certificate in the same directory. Only mux audio that has a
  matching license file; keep the certificate with redistributed work.
- `audio/generated/` holds beds from `make_ambient_audio.py`. They are
  original synthesis, so no license file is needed; keep the render command
  (seed, key, chord) alongside them so an upload can be reproduced.
- `previews/` is large (hundreds of MB, mostly legacy `*_frames/`).
  Avoid regenerating PNG sequences; v4/v5 stream and do not write them.

## Editing rules
- Extend v7 for new behavior. v5 and earlier are frozen (v4 sits alongside
  v1/v2/v3); v6 is superseded. Touch older versions only to fix a confirmed
  bug, and keep v7 the reference implementation.
- Back up scripts before risky edits: copy to `backups/<timestamp>/`.
  The repository has no commits yet, so git is not protecting anything.
  See `.gitignore` for what is deliberately untracked.
- Do not delete `audio/`, `loops/`, `output/`, or unfamiliar media
  without checking; they are user content.
- Validate visual changes with a short render plus
  `tests/test_periodicity.py`, and report measured time/RSS.
