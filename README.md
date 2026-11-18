```markdown
# Aesthetic Channel

Original, license-free ambient visual loops (Flow, Silk, Tunnel, Aura) for
YouTube — seamless periodic renders in 16:9 and 9:16, with synthesized
ambient audio. Built for CPU-only Linux: frames stream straight into FFmpeg,
no GPU required.

## Features

- **Four styles** — `flow`, `silk` (Golden Ratio φ harmonic caustics), `tunnel`, `aura`
- **Seamless loops** — every render is temporally *and* horizontally periodic, so a 30–90 s loop tiles forever with no visible seam
- **Seed-driven DNA** — palette and motion derive from `--seed`, so each upload looks different but is fully reproducible
- **Vibrant color pipeline** — replace-blend highlights, hue-preserving out-of-gamut recovery, gamma lift, seed-driven vibrance, BT.709 tagging
- **Vertical + landscape** — `720p`, `1080p`, `4k` (16:9) and `720p_vert`, `1080p_vert` (9:16)
- **Long videos** — 2–3 hour uploads via loop + stream copy in seconds, not hours of rendering
- **Original audio** — synthesized ambient beds with no license, no attribution, no Content ID risk

## Requirements

- Linux, 4 GB RAM, CPU only (tested on Intel i3-7100U)
- Python 3 with `numpy` and `Pillow`
- `ffmpeg` / `ffprobe` (tested with 6.1.1)

## Setup

```bash
git clone <your-repo-url>
cd aesthetic-channel

python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Usage

### Render a loop

```bash
# Fast 720p preview (~1 min)
venv/bin/python scripts/generate_loop_v7.py --style flow --size 720p \
  --seconds 10 --seed 7 --preset ultrafast --output previews/flow_preview.mp4

# 1080p production (render-scale 0.5 is ~7x faster, still outputs 1920x1080)
venv/bin/python scripts/generate_loop_v7.py --style silk --size 1080p \
  --seconds 30 --seed 7 --render-scale 0.5 --preset veryfast \
  --output output/silk_30s_1080p.mp4

# Vertical 9:16 short
venv/bin/python scripts/generate_loop_v7.py --style silk --size 1080p_vert \
  --seconds 90 --seed 17 --render-scale 0.5 --preset veryfast \
  --output output/short.mp4

# 4K (experimental on 4 GB — render at 0.5 scale)
venv/bin/python scripts/generate_loop_v7.py --style silk --size 4k \
  --seconds 90 --seed 76 --render-scale 0.5 --preset veryfast \
  --output output/silk_4k_90s.mp4
```

Key options: `--style {flow,silk,tunnel,aura}`, `--size`, `--seconds`,
`--fps`, `--seed`, `--crf`, `--preset`, `--render-scale`.

> **Note:** the 4K renderer is the slow path on this machine — budget roughly
> one hour per 90 s loop (internal 1080p → lanczos upscale to 4K).

### Build a long video

Repeat a verified seamless loop to any length (stream copy — takes seconds):

```bash
# Silent 2-hour video
venv/bin/python scripts/make_long_video.py output/silk_4k_90s.mp4 \
  --hours 2 --output output/silk_2h.mp4

# With licensed audio
venv/bin/python scripts/make_long_video.py output/flow_30s_1080p.mp4 \
  --hours 2.5 --audio audio/atlasaudio-ambient-lofi-576613.mp3 \
  --output output/flow_2h30_audio.mp4
```

### Generate ambient audio

```bash
# 3-minute original bed: 66 BPM, A minor 9
venv/bin/python scripts/make_ambient_audio.py --seconds 180 --seed 7 \
  --output audio/generated/ambient_180s_a2_minor9.wav

# Screen any candidate track against the relaxation spec
venv/bin/python scripts/analyze_track.py audio/candidates/*.mp3
```

### Mux audio into an existing video

```bash
ffmpeg -y -i video.mp4 -i audio.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k \
  -shortest -movflags +faststart output/video_audio.mp4
```

## Verification

```bash
# Periodicity gate — must pass after any shader change
venv/bin/python tests/test_periodicity.py

# Audio loop seam test
venv/bin/python tests/test_audio_loop.py

# 2 s smoke render
venv/bin/python scripts/generate_loop_v7.py --style flow --seconds 2 \
  --preset ultrafast --output /tmp/flow_smoke.mp4

# Inspect output
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_type,codec_name,width,height -of default=nw=1 FILE
```

Use 1–5 s renders for tests — never multi-hour renders.

## Periodicity rules (important)

The x grid is exactly one period: pixel x spans `[-1, 1)` with the right
edge exclusive. To keep loops seamless:

- Every x-dependent term must be `sin`/`cos` of an integer multiple of
  `pi * X`, or a function of an already-periodic field (e.g. `sin(theta1)`).
- Never feed raw `theta1`/`theta2` into `sin` with fractional multipliers —
  at the seam θ differs by 2π. Use `sin(1.3*sin(theta1))` instead.
- Every phase-dependent term must use an integer multiple of `phase`
  (which runs 0 → 2π over `fps * seconds`).
- No X-dependent spatial envelopes (vignettes, glows) — shape coverage with
  palette masks on the periodic field itself.
- Any shader change must keep `tests/test_periodicity.py` passing
  (float32 tolerance 1e-2 on the 0–255 scale).

## Audio licensing

- `audio/generated/` — original synthesis from `make_ambient_audio.py`.
  No license needed, no Content ID exposure. Keep the render command
  (seed, key, chord) alongside each file.
- `audio/atlasaudio-ambient-lofi-576613.mp3` — covered by the Pixabay
  certificate in the same directory. Only mux audio that has a matching
  license file; keep certificates with redistributed work.
- `audio/ncs/` — NoCopyrightSounds tracks; keep each track's license file
  (e.g. `LiborioContiLicense.pdf`) beside the audio.

## Repository layout

```
scripts/
  generate_loop_v7.py    # current renderer (DNA seeds, vibrant pipeline)
  generate_loop_v6.py    # previous renderer, superseded
  generate_loop_v5.py    # frozen reference — do not modify
  make_long_video.py     # loop → long MP4 via stream copy
  make_ambient_audio.py  # original seamless ambient beds
  analyze_track.py       # relaxation-spec audio screener
tests/
  test_periodicity.py    # shader periodicity gate
  test_audio_loop.py     # audio seam gate
```

## Editing rules

- Extend **v7** for new behavior; v5 and earlier are frozen, v6 is
  superseded. Back up scripts to `backups/<timestamp>/` before risky edits —
  the repository history is the only safety net.
- Validate visual changes with a short render plus
  `tests/test_periodicity.py`, and report measured time/RSS.
- Don't delete `audio/`, `loops/`, `output/`, or unfamiliar media without
  checking — those are user content.
```
