#!/usr/bin/env python3
"""Repeat a short seamless loop into a long video without re-rendering.

Rendering even a few hours of unique frames is impractically slow on a
4 GB CPU-only machine.  Render a short loop with generate_loop_v4.py
once, then stream-copy it into the final duration:

    python scripts/make_long_video.py previews/flow_v4_10s.mp4 \
        --hours 2.5 --output output/flow_2h30.mp4

    python scripts/make_long_video.py previews/flow_v4_10s.mp4 \
        --hours 2.5 --audio audio/atlasaudio-ambient-lofi-576613.mp3 \
        --output output/flow_2h30_audio.mp4

The source must already loop seamlessly; this script does not blend or
re-encode the video (only the audio is AAC-encoded).
"""

import argparse
import subprocess
from pathlib import Path


def probe_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="short seamless loop (mp4)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=float, default=2.0)
    parser.add_argument(
        "--seconds", type=float, default=None,
        help="explicit target duration (overrides --hours; useful for tests)",
    )
    parser.add_argument(
        "--audio", type=Path, default=None,
        help="optional audio file; must be covered by a license in audio/",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")
    if args.audio and not args.audio.exists():
        raise SystemExit(f"audio not found: {args.audio}")

    target = args.seconds if args.seconds is not None else args.hours * 3600.0
    if target <= 0:
        raise SystemExit("target duration must be positive")

    source_duration = probe_duration(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(args.input),
    ]
    if args.audio:
        cmd += ["-stream_loop", "-1", "-i", str(args.audio)]
        cmd += [
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
        ]
    else:
        cmd += ["-an", "-c:v", "copy"]

    cmd += [
        "-t", f"{target:.3f}",
        "-movflags", "+faststart",
        str(args.output),
    ]

    print(
        f"source {args.input} ({source_duration:.2f}s) -> "
        f"{target / 3600.0:.3f}h ({target:.1f}s)"
    )
    subprocess.run(cmd, check=True)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
