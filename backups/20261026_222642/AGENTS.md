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
- `scripts/generate_loop_v4.py` — **current renderer**. Styles `flow`,
  `tunnel`, `aura`; sizes `720p`, `1080p`, experimental `4k`; streams
  raw RGB24 into x264. Supports `--seconds`, `--fps`, `--seed`, `--crf`,
  `--preset`, `--render-scale`. Flow is a bright cosmic nebula
  (violet/magenta clouds, lilac-white cores, cyan accents, twinkling
  starfield, two flared stars); stars/flare masks are cached per render
  in `flow_static()` — do not put phase terms there.
- `scripts/make_long_video.py` — repeats a *seamless* short loop to a long
  MP4 with stream copy; optional licensed audio.
- Legacy scripts `generate_loop.py`, `_v2.py`, `_v3.py`,
  `_v3_improved.py` remain for reference. Do not start new work on them.
  Known issues: v3 names every style's default output `tunnel_v2.mp4`
  (pass `--output` explicitly); v1 leaves PNG frame dirs that can leak
  into a later shorter render.
- Pre-v4 code is backed up under `backups/20261026_210538/`.

## Commands
720p Flow preview (fast):
```bash
venv/bin/python scripts/generate_loop_v4.py --style flow --size 720p \
  --seconds 10 --seed 7 --preset ultrafast --output previews/flow_preview.mp4
```

1080p production (on 4 GB, 0.5 internal scale is ~7x faster and still
outputs 1920x1080 via lanczos):
```bash
venv/bin/python scripts/generate_loop_v4.py --style flow --size 1080p \
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
# 2 s smoke render (~0.5 min at 720p)
venv/bin/python scripts/generate_loop_v4.py --style flow --seconds 2 \
  --preset ultrafast --output /tmp/flow_smoke.mp4
# Time + peak RSS
/usr/bin/time -v venv/bin/python scripts/generate_loop_v4.py ...
# Inspect output
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_type,codec_name,width,height -of default=nw=1 FILE
```

Do not render multi-hour videos during tests. Use 1–5 second renders.

## Periodicity invariants (Flow)
- Legacy v3 Flow is **not** horizontally periodic: measured edge mismatch
  was 74–79 (of 255) because its x frequencies are not integer multiples
  of π. v4 replaces that field; do not copy v3's Flow math.
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
- Foreground star flares must stay built on `sin(pi*(X - x0))` (exact
  period 2) rather than raw Gaussians in `X`; star twinkle must use
  integer phase multiples only.
- Flow glow and vignette depend on Y only. An X-dependent envelope
  breaks the seam.
- Any shader change must keep `tests/test_periodicity.py` passing
  (float32 tolerance is 1e-2 on the 0–255 scale).

## Runtime notes
- Measured 2026-10-26 (nebula palette, final v4): 720p 10 s (240 frames)
  veryfast = 4:04, 281 MB peak RSS (~1.0 s/frame; the brighter nebula
  layers cost ~0.35 s/frame more than the old amber look). 720p 2 s
  ultrafast = ~1 min. 1080p `--render-scale 0.5` ≈ 1 min / 10 s of
  footage; native 1080p ≈ 5x that. Rendering is the bottleneck at
  720p/1080p, not x264.
- Use `--render-scale 0.5` for long 1080p loops on this box. Quality loss
  is small because the artwork is smooth gradients.
- Generate a 20–60 s seamless loop, then `make_long_video.py`. The
  latter copies video and only AAC-encodes optional audio, so 2–3 h
  outputs take seconds and no extra RAM.
- Preview `--preset ultrafast`; production `veryfast`; CRF 18 default.
- 4K native is untested on 4 GB (likely slow); `--render-scale 0.5`
  produces a 3840x2160 file within the measured memory budget.

## Assets and licensing
- `audio/atlasaudio-ambient-lofi-576613.mp3` is covered by the Pixabay
  license certificate in the same directory. Only mux audio that has a
  matching license file; keep the certificate with redistributed work.
- `previews/` is large (hundreds of MB, mostly legacy `*_frames/`).
  Avoid regenerating PNG sequences; v4 streams and does not write them.

## Editing rules
- Extend v4 for new behavior; leave v1/v2/v3 untouched unless fixing a
  confirmed bug.
- Back up scripts before risky edits: copy to `backups/<timestamp>/`.
  This directory is not a git repository.
- Do not delete `audio/`, `loops/`, `output/`, or unfamiliar media
  without checking; they are user content.
- Validate visual changes with a short render plus
  `tests/test_periodicity.py`, and report measured time/RSS.
