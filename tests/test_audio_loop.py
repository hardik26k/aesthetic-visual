#!/usr/bin/env python3
"""Verify a generated audio bed is loop-safe and matches its spec.

Renders a short bed through the real CLI, then checks the properties that
matter for a 2-3 hour stream-copied video: exact sample count, a
continuous wrap point, request-accurate loudness and safe peak headroom.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.make_ambient_audio import note_to_hz, periodic_hz  # noqa: E402

DURATION = 6.0
RATE = 48_000
TARGET_LUFS = -20.0


def decode(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, "<f4").reshape(-1, 2).T.astype(np.float64)


def measure_lufs(path):
    text = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    values = [
        float(line.split()[1]) for line in text.splitlines()
        if line.strip().startswith("I:") and line.strip().endswith("LUFS")
    ]
    return values[-1] if values else None


def main():
    failures = []

    def check(name, condition, detail):
        print(f"  {'PASS' if condition else 'FAIL'}  {name}: {detail}")
        if not condition:
            failures.append(name)

    print("Note conversion:")
    check("note_to_hz", abs(note_to_hz("A4") - 440.0) < 1e-9, "A4 = 440 Hz")
    check("note_to_hz", abs(note_to_hz("A2") - 110.0) < 1e-9, "A2 = 110 Hz")
    check("note_to_hz", abs(note_to_hz("C#3") - 138.59) < 0.01, "C#3 = 138.59 Hz")

    print("Period snapping (frequencies must complete whole cycles):")
    for seconds in (6.0, 30.0, 180.0):
        freq, cycles = periodic_hz(66.0 / 60.0, seconds)
        error = abs(freq * seconds - round(freq * seconds))
        check(f"66 bpm over {seconds:g}s", error < 1e-9,
              f"{cycles} cycles, {freq * 60:.4f} bpm")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bed.wav"
        print("Render:")
        subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "make_ambient_audio.py"),
                "--seconds", str(DURATION), "--seed", "11",
                "--bit-depth", "16", "--output", str(path),
            ],
            check=True, capture_output=True,
        )

        data = decode(path)
        frames = data.shape[1]
        print("Loop safety:")
        check("sample count", frames == int(round(DURATION * RATE)),
              f"{frames} frames, expected {int(round(DURATION * RATE))}")

        wrap = float(np.max(np.abs(data[:, 0] - data[:, -1])))
        before = float(np.max(np.abs(data[:, -1] - data[:, -2])))
        after = float(np.max(np.abs(data[:, 1] - data[:, 0])))
        local = max(before, after)
        check("wrap continuity", wrap <= 2.0 * local,
              f"wrap {wrap:.5f} vs neighbours {before:.5f}/{after:.5f}")

        peak = float(np.max(np.abs(data)))
        check("peak headroom", peak <= 0.9, f"{20 * np.log10(peak + 1e-12):.1f} dBFS")

        measured = measure_lufs(path)
        check("loudness", measured is not None
              and abs(measured - TARGET_LUFS) <= 1.0,
              f"{measured} LUFS, target {TARGET_LUFS}")

    print()
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print("all audio loop checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
