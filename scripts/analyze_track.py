#!/usr/bin/env python3
"""Screen an audio track against the relaxation spec in AGENTS.md.

There is no single "scientifically proven calming track". What the
literature supports is a parameter set: slow tempo, instrumental, low
spectral flux (no transients or drums), warm timbre, steady loudness.
This script measures those properties so a candidate can be accepted or
rejected on evidence instead of on the word "calming".

Checks (thresholds are the constants below):
    tempo       55-80 BPM, or no detectable pulse (ambient drone)
    transients  flux peaks relative to the median, i.e. drum hits
    brightness  spectral centroid, i.e. harshness
    loudness    integrated LUFS, background-bed range
    true peak   headroom for AAC/opus encoding
    dynamics    loudness range, i.e. no jump-scare swells

Usage:
    venv/bin/python scripts/analyze_track.py audio/atlasaudio-*.mp3
    venv/bin/python scripts/analyze_track.py audio/candidates/*.wav --json

Exit code is 0 when everything passes, 1 otherwise, so it can gate a
download or a render.

Uses ffmpeg for decoding and EBU R128 loudness; numpy for the rest.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ANALYSIS_RATE = 22_050
N_FFT = 1_024
HOP = 256

# Tempo outside this band loses the documented relaxation effect.
TEMPO_RANGE = (55.0, 80.0)
# Autocorrelation peak below this is treated as "no pulse", not slow music.
PULSE_CONFIDENCE = 0.10
# Below this length the tempo estimate is not trustworthy.
MIN_TEMPO_SECONDS = 20.0
# Spectral-flux crest above this means audible hits / percussion.
TRANSIENT_MAX = 6.0
# Above this the bed gets fatiguing over a two-hour listen. Warm pads land
# around 600-1100 Hz; bright, hissy or metallic material passes 1500.
CENTROID_MAX = 1_500.0
# Background bed. YouTube normalises to about -14 LUFS and never boosts.
LUFS_TARGET = -20.0
LUFS_RANGE = (-24.0, -15.0)
TRUE_PEAK_MAX = -1.0
# Large swings break the "predictable, no abrupt changes" requirement.
LRA_MAX = 9.0

AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".aiff"}


def decode_mono(path, max_seconds):
    """Decode to mono float32 at ANALYSIS_RATE through ffmpeg."""
    command = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)]
    if max_seconds:
        command += ["-t", f"{max_seconds:.3f}"]
    command += ["-ac", "1", "-ar", str(ANALYSIS_RATE), "-f", "f32le", "-"]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip().splitlines()
        raise RuntimeError(message[-1] if message else "ffmpeg failed")
    return np.frombuffer(result.stdout, dtype="<f4").astype(np.float32)


def magnitude_spectrogram(samples):
    """Hann-windowed magnitude STFT, returned as (freq, time)."""
    if len(samples) < N_FFT * 2:
        return None
    frames = 1 + (len(samples) - N_FFT) // HOP
    offsets = np.arange(N_FFT)[None, :] + HOP * np.arange(frames)[:, None]
    window = np.hanning(N_FFT).astype(np.float32)
    frames_data = samples[offsets] * window
    return np.abs(np.fft.rfft(frames_data, axis=1)).astype(np.float32).T


def spectral_flux(spec):
    """Half-wave rectified change in log magnitude, summed over bins."""
    normalised = spec / (spec.mean() + 1e-9)
    delta = np.diff(np.log1p(normalised), axis=1)
    return np.maximum(delta, 0.0).sum(axis=0)


def autocorrelation(signal):
    length = len(signal)
    padded = 1 << (2 * length - 1).bit_length()
    spectrum = np.fft.rfft(signal - signal.mean(), padded)
    return np.fft.irfft(spectrum * np.conj(spectrum), padded)[:length]


def estimate_tempo(flux):
    """Return (bpm, confidence) from the onset envelope.

    confidence is the normalised autocorrelation peak; a drone has no
    peak and should not be penalised as "wrong tempo".
    """
    acf = autocorrelation(flux.astype(np.float64))
    if acf[0] <= 0:
        return None, 0.0
    acf = acf / acf[0]
    slowest = int(round(60.0 / 180.0 * ANALYSIS_RATE / HOP))
    fastest = int(round(60.0 / 40.0 * ANALYSIS_RATE / HOP))
    slowest = max(slowest, 1)
    if fastest <= slowest + 1 or fastest >= len(acf):
        return None, 0.0
    window = acf[slowest:fastest]
    lag = slowest + int(np.argmax(window))
    confidence = float(window.max())
    bpm = 60.0 * ANALYSIS_RATE / (lag * HOP)
    return bpm, confidence


def fold_tempo(bpm):
    """Map an autocorrelation octave onto the perceived tempo."""
    candidates = [bpm * 2.0, bpm, bpm / 2.0, bpm / 4.0]
    in_band = [c for c in candidates if TEMPO_RANGE[0] <= c <= TEMPO_RANGE[1]]
    pool = in_band or candidates
    return min(pool, key=lambda c: abs(c - 70.0))


def spectral_centroid(spec):
    """Energy-weighted spectral centroid: where the power actually sits.

    Magnitude weighting over-counts the many quiet high bins, which makes
    smooth pads look brighter than they sound. Power weighting tracks
    perceived warmth better.
    """
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / ANALYSIS_RATE)[:, None]
    power = spec.astype(np.float64) ** 2
    total = power.sum(axis=0)
    valid = total > 0
    if not np.any(valid):
        return 0.0
    return float((power[:, valid] * freqs).sum(axis=0).mean()
                 / max(total[valid].mean(), 1e-9))


def loudness(path):
    """Integrated loudness, loudness range and true peak via ffmpeg."""
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", "ebur128=peak=true", "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    text = result.stderr
    return {
        "lufs": _last_number(text, r"^\s*I:\s*(-?\d+\.\d+) LUFS"),
        "lra": _last_number(text, r"^\s*LRA:\s*(-?\d+\.\d+) LU"),
        "peak": _last_number(text, r"^\s*Peak:\s*(-?\d+\.\d+) dBFS"),
    }


def _last_number(text, pattern):
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    return float(matches[-1]) if matches else None


def probe_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def analyse(path, max_seconds):
    samples = decode_mono(path, max_seconds)
    if samples.size < N_FFT * 2:
        raise RuntimeError("file too short to analyse")

    spec = magnitude_spectrogram(samples)
    flux = spectral_flux(spec)
    bpm_raw, confidence = estimate_tempo(flux)
    bpm = fold_tempo(bpm_raw) if bpm_raw else None

    median_flux = float(np.median(flux))
    transient = float(np.percentile(flux, 99) / max(median_flux, 1e-9))
    centroid = spectral_centroid(spec)
    meters = loudness(path)

    return {
        "file": str(path),
        "duration": probe_duration(path),
        "analysed_seconds": round(samples.size / ANALYSIS_RATE, 2),
        "bpm_raw": None if bpm_raw is None else round(bpm_raw, 1),
        "bpm": None if bpm is None else round(bpm, 1),
        "pulse_confidence": round(confidence, 3),
        "transient_index": round(transient, 2),
        "centroid_hz": round(centroid, 1),
        "lufs": meters["lufs"],
        "lra": meters["lra"],
        "true_peak": meters["peak"],
    }


def evaluate(result):
    """Apply the spec, returning a list of check rows."""
    rows = []

    # A handful of seconds cannot support an autocorrelation estimate:
    # noise starts looking periodic. Treat short samples as inconclusive.
    too_short = result["analysed_seconds"] < MIN_TEMPO_SECONDS
    if too_short:
        rows.append(("tempo", "sample too short", True,
                     f"needs >= {MIN_TEMPO_SECONDS:.0f} s"))
    elif result["bpm"] is None or result["pulse_confidence"] < PULSE_CONFIDENCE:
        rows.append(("tempo", "no clear pulse", True, "ok for a drone"))
    else:
        ok = TEMPO_RANGE[0] <= result["bpm"] <= TEMPO_RANGE[1]
        rows.append((
            "tempo", f"{result['bpm']} bpm", ok,
            f"{TEMPO_RANGE[0]:.0f}-{TEMPO_RANGE[1]:.0f} bpm",
        ))

    rows.append((
        "transients", f"{result['transient_index']}x median",
        result["transient_index"] < TRANSIENT_MAX,
        f"< {TRANSIENT_MAX:.1f}x",
    ))
    rows.append((
        "brightness", f"{result['centroid_hz']:.0f} Hz",
        result["centroid_hz"] < CENTROID_MAX,
        f"< {CENTROID_MAX:.0f} Hz",
    ))

    if result["lufs"] is None:
        rows.append(("loudness", "unmeasured", False, "measurable"))
    else:
        rows.append((
            "loudness", f"{result['lufs']} LUFS",
            LUFS_RANGE[0] <= result["lufs"] <= LUFS_RANGE[1],
            f"{LUFS_RANGE[0]:.0f} to {LUFS_RANGE[1]:.0f} LUFS "
            f"(target {LUFS_TARGET:.0f})",
        ))

    if result["true_peak"] is None:
        rows.append(("true peak", "unmeasured", False, "<= -1 dBFS"))
    else:
        rows.append((
            "true peak", f"{result['true_peak']} dBFS",
            result["true_peak"] <= TRUE_PEAK_MAX,
            f"<= {TRUE_PEAK_MAX:.0f} dBFS",
        ))

    if result["lra"] is None:
        rows.append(("dynamics", "unmeasured", False, f"<= {LRA_MAX:.0f} LU"))
    else:
        rows.append((
            "dynamics", f"{result['lra']} LU",
            result["lra"] <= LRA_MAX, f"<= {LRA_MAX:.0f} LU",
        ))

    return rows


def report(result, as_json):
    rows = evaluate(result)
    passed = sum(1 for row in rows if row[2])
    score = int(round(100.0 * passed / len(rows)))
    result["checks"] = [
        {"name": name, "value": value, "pass": ok, "target": target}
        for name, value, ok, target in rows
    ]
    result["score"] = score
    result["pass"] = passed == len(rows)

    if as_json:
        print(json.dumps(result, indent=2))
        return result["pass"]

    duration = result["duration"]
    duration_text = f"{duration:.1f} s" if duration else "unknown"
    name_width = max(len(row[0]) for row in rows) + 1
    value_width = max(len(row[1]) for row in rows) + 2

    print(f"\n{result['file']}")
    print(f"  {'duration':<{name_width}}{duration_text}")
    for name, value, ok, target in rows:
        status = "ok  " if ok else "FAIL"
        print(f"  {status} {name:<{name_width}}{value:<{value_width}}"
              f"target {target}")
    print(f"  score {score}/100  {'PASS' if result['pass'] else 'REJECT'}")
    if (result["bpm_raw"] and result["bpm"]
            and result["bpm_raw"] != result["bpm"]
            and result["analysed_seconds"] >= MIN_TEMPO_SECONDS):
        print(f"  note: autocorrelation gave {result['bpm_raw']} bpm, "
              f"folded to {result['bpm']} bpm")
    return result["pass"]


def collect(paths):
    files = []
    for path in paths:
        path = Path(path)
        if path.is_dir():
            files.extend(sorted(
                child for child in path.iterdir()
                if child.suffix.lower() in AUDIO_SUFFIXES
            ))
        elif path.is_file():
            files.append(path)
        else:
            print(f"skipping missing path: {path}", file=sys.stderr)
    return files


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="+", type=Path,
                        help="audio files or directories")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable output")
    parser.add_argument("--max-seconds", type=float, default=120.0,
                        help="analyse only the first N seconds (0 = all)")
    args = parser.parse_args()

    files = collect(args.paths)
    if not files:
        raise SystemExit("no audio files found")

    results = []
    for path in files:
        try:
            results.append(analyse(path, args.max_seconds))
        except RuntimeError as error:
            print(f"{path}: {error}", file=sys.stderr)

    if not results:
        raise SystemExit("nothing could be analysed")

    passes = [report(result, args.json) for result in results]

    if len(results) > 1 and not args.json:
        accepted = sum(passes)
        print(f"\n{accepted}/{len(results)} track(s) pass the spec")
        if accepted:
            print("accepted:")
            for result, ok in zip(results, passes):
                if ok:
                    print(f"  {result['file']}")
        rejected = [r["file"] for r, ok in zip(results, passes) if not ok]
        if rejected:
            print("rejected:")
            for name in rejected:
                print(f"  {name}")

    sys.exit(0 if all(passes) else 1)


if __name__ == "__main__":
    main()
