#!/usr/bin/env python3
"""Render a seamless, license-free ambient audio bed.

The video pipelines produce seamless loops, so the audio has to loop too.
Every oscillator, LFO, amplitude pulse and reverb tail here is built over
exactly one loop period, so sample N-1 leads back to sample 0 without a
crossfade and without a click. The result can be fed straight to
make_long_video.py, which stream-loops it for hours.

Parameters follow the relaxation research summarised in AGENTS.md:
slow instrumental texture, no transients, a 60-72 BPM amplitude breath,
quiet background loudness (~-20 LUFS).

Usage:
    venv/bin/python scripts/make_ambient_audio.py --seconds 180 \
        --output audio/generated/ambient_180s.wav

    venv/bin/python scripts/make_ambient_audio.py --seconds 30 --seed 3 \
        --chord open5 --bpm 63 --output /tmp/bed.wav

The output is your own work: no license, no attribution, no Content ID.
"""

import argparse
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 48_000

NOTE_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Interval sets in semitones from the root. Voicings are deliberately
# wide (four octaves): stacking every tone inside one octave puts all
# the energy in 160-440 Hz and sounds muddy.
CHORDS = {
    "open5": (0, 7, 12, 19, 24, 31, 36),
    "sus2": (0, 7, 12, 14, 19, 26, 31, 38),
    "minor9": (0, 7, 12, 15, 19, 26, 31, 36, 43),
    "major9": (0, 7, 12, 16, 19, 26, 31, 36, 43),
    "minor": (0, 7, 12, 15, 19, 24, 31, 36),
    "dorian": (0, 7, 10, 12, 15, 19, 31, 36),
}


def note_to_hz(name):
    """Convert a note name such as A2, D#3 or Bb4 to a frequency."""
    digits = "".join(ch for ch in name if ch.isdigit())
    letters = name[: len(name) - len(digits)] if digits else name
    if not digits or not letters:
        raise SystemExit(f"cannot parse note: {name!r} (expected e.g. A2)")
    letter = letters[0].upper()
    if letter not in NOTE_SEMITONES:
        raise SystemExit(f"unknown note letter in {name!r}")
    semitone = NOTE_SEMITONES[letter]
    for accidental in letters[1:]:
        if accidental == "#":
            semitone += 1
        elif accidental in ("b", "B"):
            semitone -= 1
        else:
            raise SystemExit(f"unknown accidental in {name!r}")
    midi = 12 * (int(digits) + 1) + semitone
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def periodic_hz(hz, seconds):
    """Snap a frequency to a whole number of cycles over the loop.

    Returns (frequency, cycles). Anything that does not complete an
    integer number of cycles per loop would break the seam.
    """
    cycles = max(1, int(round(hz * seconds)))
    return cycles / seconds, cycles


def build_pad(n, fs, root_hz, chord, rng, tilt=1.6, harmonics=5,
              brightness=0.3, seconds=None):
    """Additive pad built directly in the frequency domain.

    Building the spectrum instead of summing sines costs one rfft and
    keeps the loop exactly periodic: bin k is by definition k cycles per
    loop. Slow amplitude movement is added as sidebands at k +/- m, which
    is what a low-rate amplitude LFO physically is.
    """
    seconds = seconds if seconds is not None else n / fs
    spec = np.zeros(n // 2 + 1, dtype=np.complex128)
    max_bin = n // 2 - 2

    for semitone in chord:
        fundamental = root_hz * 2.0 ** (semitone / 12.0)
        # Lift the upper voices relative to the low ones, otherwise every
        # fundamental sits in 160-440 Hz and the bed turns to mud.
        tone_gain = (fundamental / root_hz) ** brightness
        for harmonic in range(1, harmonics + 1):
            freq = fundamental * harmonic
            if freq > fs * 0.42:
                continue
            bin_index = int(round(freq * seconds))
            if bin_index < 1 or bin_index > max_bin:
                continue
            amplitude = tone_gain * rng.uniform(0.85, 1.15) / harmonic ** tilt
            phase = rng.uniform(0.0, 2.0 * np.pi)
            spec[bin_index] += amplitude * np.exp(1j * phase)

            # Two sidebands give the partial a slow swell instead of a
            # static tone. sideband spacing is a whole number of cycles.
            drift = rng.uniform(0.02, 0.09)
            depth = rng.uniform(0.10, 0.30)
            offset = max(1, int(round(drift * seconds)))
            for direction in (-1, 1):
                side = bin_index + direction * offset
                if 1 <= side <= max_bin:
                    spec[side] += (
                        0.5 * depth * amplitude
                        * np.exp(1j * (phase + rng.uniform(0.0, 2.0 * np.pi)))
                    )
    spec[0] = 0.0
    if n % 2 == 0:
        spec[-1] = 0.0
    return spec


def spectral_rms(spec, n):
    """RMS of the real signal represented by a one-sided spectrum."""
    energy = np.sum(np.abs(spec[1:] if n % 2 == 0 else spec) ** 2)
    return float(np.sqrt(2.0 * energy) / n)


def build_air(n, fs, rng, level, pad_rms, low=150.0, high=4_200.0):
    """Filtered noise bed: breath and space without any audible hiss."""
    noise = rng.standard_normal(n)
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    shape = (freqs / (freqs + low)) ** 1.2 / (1.0 + (freqs / high) ** 3.5)
    shape[0] = 0.0
    spec *= shape
    current = spectral_rms(spec, n)
    if current > 0 and level > 0:
        spec *= (level * pad_rms) / current
    else:
        spec[:] = 0.0
    return spec


def reverb_response(n, fs, rt60, rng, wet, damp_hz=3_200.0, predelay=0.022):
    """Circular reverb impulse response.

    The tail is shorter than the loop and convolved circularly, so the
    decay of the final seconds folds into the first seconds. The loop is
    then genuinely periodic rather than crossfaded.
    """
    length = min(n, max(2, int(rt60 * fs)))
    t = np.arange(length) / fs
    tail = rng.standard_normal(length) * np.exp(-6.9078 * t / rt60)
    spec = np.fft.rfft(tail)
    freqs = np.fft.rfftfreq(length, 1.0 / fs)
    spec /= 1.0 + (freqs / damp_hz) ** 1.5
    tail = np.fft.irfft(spec, length)
    tail /= np.sqrt(np.sum(tail ** 2)) + 1e-12

    ir = np.zeros(n)
    delay = int(predelay * fs)
    take = max(0, min(n - delay, length))
    ir[delay:delay + take] = wet * tail[:take]
    ir[0] += 1.0
    return np.fft.rfft(ir)


def slow_movement(n, fs, rng, drift=0.05, bpm=None, pulse=0.06):
    """Periodic macro-dynamics: drift, plus an optional BPM breath."""
    seconds = n / fs
    t = np.arange(n, dtype=np.float64) / fs
    mod = np.ones(n, dtype=np.float64)

    for target in (0.0087, 0.0133, 0.0210):
        freq, _ = periodic_hz(target, seconds)
        depth = drift * rng.uniform(0.3, 1.0)
        mod *= 1.0 + depth * np.cos(2.0 * np.pi * freq * t + rng.uniform(0, 2 * np.pi))

    if bpm and pulse > 0:
        cycles = int(round(bpm * seconds / 60.0))
        freq = cycles / seconds
        breath = 0.5 + 0.5 * np.cos(2.0 * np.pi * freq * t)
        mod *= 1.0 - pulse + pulse * breath

    return mod


def measure_loudness(path):
    """Integrated loudness and true peak via ffmpeg's EBU R128 filter."""
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", "ebur128=peak=true", "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    text = result.stderr
    lufs = _last_number(text, r"^\s*I:\s*(-?\d+\.\d+) LUFS")
    peak = _last_number(text, r"^\s*Peak:\s*(-?\d+\.\d+) dBFS")
    return lufs, peak


def _last_number(text, pattern):
    import re

    matches = re.findall(pattern, text, flags=re.MULTILINE)
    return float(matches[-1]) if matches else None


def write_wav(path, data, fs, bit_depth=24, dither=True, seed=0):
    """Write stereo float data in [-1, 1] as interleaved PCM."""
    channels, frames = data.shape
    rng = np.random.default_rng(seed)

    if bit_depth == 16:
        scale = 32767.0
        if dither:
            data = data + rng.uniform(-0.5, 0.5, data.shape) / scale
        pcm = np.clip(data * scale, -32768, 32767).astype("<i2")
        raw = np.ascontiguousarray(pcm.T).tobytes()
    elif bit_depth == 24:
        scale = 8388607.0
        if dither:
            data = data + rng.uniform(-0.5, 0.5, data.shape) / scale
        pcm = np.clip(data * scale, -8388608, 8388607).astype("<i4")
        interleaved = np.empty((frames, channels, 3), dtype=np.uint8)
        for channel in range(channels):
            bytes32 = np.frombuffer(pcm[channel].tobytes(), dtype=np.uint8)
            interleaved[:, channel, :] = bytes32.reshape(frames, 4)[:, :3]
        raw = interleaved.tobytes()
    else:
        raise SystemExit("bit depth must be 16 or 24")

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(bit_depth // 8)
        handle.setframerate(fs)
        handle.writeframes(raw)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--seconds", type=float, default=180.0,
                        help="loop length in seconds (default 180)")
    parser.add_argument("--bpm", type=float, default=66.0,
                        help="amplitude breath rate, 60-72 is the useful band")
    parser.add_argument("--root", default="A2", help="root note, e.g. A2, D3")
    parser.add_argument("--chord", default="minor9", choices=sorted(CHORDS))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--sample-rate", type=int, default=SAMPLE_RATE)
    parser.add_argument("--lufs", type=float, default=-20.0,
                        help="target integrated loudness")
    parser.add_argument("--air", type=float, default=0.38,
                        help="noise bed level relative to the pad")
    parser.add_argument("--reverb", type=float, default=0.45)
    parser.add_argument("--rt60", type=float, default=3.2)
    parser.add_argument("--pulse", type=float, default=0.06,
                        help="amplitude breath depth, 0 disables it")
    parser.add_argument("--harmonics", type=int, default=4)
    parser.add_argument("--tilt", type=float, default=1.55,
                        help="harmonic rolloff; higher is warmer")
    parser.add_argument("--brightness", type=float, default=0.35,
                        help="lift of upper voices over the root")
    parser.add_argument("--bit-depth", type=int, default=24, choices=(16, 24))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.seconds <= 0:
        raise SystemExit("--seconds must be positive")
    if args.sample_rate < 8_000:
        raise SystemExit("--sample-rate is implausibly low")

    fs = args.sample_rate
    n = int(round(args.seconds * fs))
    seconds = n / fs
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Snap the breath rate so it completes whole cycles over the loop.
    bpm = args.bpm
    if bpm:
        cycles = max(1, int(round(bpm * seconds / 60.0)))
        snapped = cycles * 60.0 / seconds
        if abs(snapped - bpm) > 1e-6:
            print(f"tempo snapped {bpm:.3f} -> {snapped:.3f} bpm "
                  f"({cycles} cycles over the loop)")
        bpm = snapped

    root_hz = note_to_hz(args.root)
    chord = CHORDS[args.chord]
    print(f"loop {seconds:.3f} s  {n} frames  {fs} Hz  "
          f"{args.chord} on {args.root} ({root_hz:.2f} Hz)")

    data = np.empty((2, n), dtype=np.float64)
    pad_rms = None

    for channel in range(2):
        # Independent phases per channel decorrelate the pad into width.
        rng = np.random.default_rng(args.seed * 2 + channel)
        pad = build_pad(n, fs, root_hz, chord, rng,
                        tilt=args.tilt, harmonics=args.harmonics,
                        brightness=args.brightness, seconds=seconds)
        if pad_rms is None:
            pad_rms = spectral_rms(pad, n)
        air = build_air(n, fs, rng, args.air, pad_rms)
        ir = reverb_response(n, fs, args.rt60, rng, args.reverb)

        wet = np.fft.irfft((pad + air) * ir, n)
        wet *= slow_movement(n, fs, rng, bpm=bpm, pulse=args.pulse)
        data[channel] = wet
        del pad, air, ir, wet

    peak = float(np.max(np.abs(data)))
    if peak <= 0:
        raise SystemExit("render produced silence")
    data *= 0.707 / peak

    # Two-pass loudness: write, measure, apply the correction, write final.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        write_wav(temp_path, data, fs, bit_depth=24, dither=False)
        measured, _ = measure_loudness(temp_path)
        if measured is None:
            raise SystemExit("could not measure loudness (ffmpeg missing?)")
        gain_db = args.lufs - measured
        data *= 10.0 ** (gain_db / 20.0)

        # Never let the correction push the bed into clipping.
        peak = float(np.max(np.abs(data)))
        if peak > 0.891:  # -1.0 dBFS
            data *= 0.891 / peak
        write_wav(args.output, data, fs, bit_depth=args.bit_depth,
                  dither=True, seed=args.seed)
    finally:
        temp_path.unlink(missing_ok=True)

    final_lufs, final_peak = measure_loudness(args.output)

    # Seam check: the wrap step must look like the steps either side of
    # it. Comparing against the mean step is misleading on a slow bed,
    # where the mean is dominated by near-flat passages.
    wrap = float(np.max(np.abs(data[:, 0] - data[:, -1])))
    before = float(np.max(np.abs(data[:, -1] - data[:, -2])))
    after = float(np.max(np.abs(data[:, 1] - data[:, 0])))
    local = max(before, after, 1e-12)
    ratio = wrap / local
    print(f"seam  wrap {wrap:.6f}  neighbours {before:.6f}/{after:.6f}  "
          f"ratio {ratio:.2f}x")
    if ratio > 2.0:
        print("warning: wrap step is discontinuous; the loop may click")
    print(f"loudness  {final_lufs if final_lufs is not None else 'n/a'} LUFS  "
          f"peak {final_peak if final_peak is not None else 'n/a'} dBFS")
    size_mb = args.output.stat().st_size / 1e6
    print(f"wrote {args.output}  {size_mb:.1f} MB  "
          f"{args.bit_depth}-bit  {fs} Hz stereo")
    print("license: original synthesis, no attribution required")


if __name__ == "__main__":
    main()
