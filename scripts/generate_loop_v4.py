#!/usr/bin/env python3
"""Generate seamless ambient loops (flow / tunnel / aura).

Frames are streamed as raw RGB24 into ffmpeg, so no PNG sequence is
written to disk.  All styles complete exactly one animation cycle over
``fps * seconds`` frames; the Flow style is additionally periodic across
the full horizontal span by construction.

Usage:
    python scripts/generate_loop_v4.py --style flow --seconds 10 --seed 7
    python scripts/generate_loop_v4.py --style tunnel --size 1080p \
        --output output/tunnel_1080p.mp4
"""

import argparse
import subprocess
from pathlib import Path

import numpy as np

SIZES = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    # Experimental: measure RAM/time before using in production.
    "4k": (3840, 2160),
}


def make_grid(width, height):
    """Pixel-centre grid spanning one full period in x.

    x runs from -1 (inclusive) to 1 (exclusive) so that tiling the
    rendered frame horizontally is seamless: the next sample after the
    right edge is the left edge.
    """
    x = (np.arange(width, dtype=np.float32) / width - 0.5) * 2.0
    y = (np.arange(height, dtype=np.float32) / height - 0.5) * 2.0
    X, Y = np.meshgrid(x, y)
    Y *= height / width
    return X, Y


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def flow_params(seed):
    """Deterministic per-video variation; constants keep the loop periodic."""
    rng = np.random.default_rng(seed)
    return {
        "phase0": float(rng.uniform(0.0, 2.0 * np.pi)),
        "tint": rng.uniform(0.88, 1.12, 3).astype(np.float32),
        # Two bright foreground stars with diffraction spikes.
        "flare_x": rng.uniform(-0.35, 0.35, 2),
        "flare_y": rng.uniform(-0.20, 0.20, 2),
        "flare_sigma": np.array([0.095, 0.070], dtype=np.float32),
        "flare_amp": np.array([1.30, 1.05], dtype=np.float32),
        "flare_off": rng.uniform(0.0, 2.0 * np.pi, 2),
    }


def flow_static(X, Y, params):
    """Phase-independent Flow layers, computed once per render.

    Everything here is exactly periodic across the x seam (every x term
    is a sine/cosine of an integer multiple of pi * X) and carries no
    time dependence, so it can be cached while the animation runs.
    """
    y = Y[:, 0]

    # Pinprick star field: products of high-frequency harmonics pick
    # sparse, tiny dots out of the noise (integer multiples of pi * X).
    p1 = np.sin(23.0 * np.pi * X + 17.0 * y[:, None])
    p2 = np.cos(37.0 * np.pi * X - 29.0 * y[:, None])
    p3 = np.sin(53.0 * np.pi * X + 41.0 * y[:, None])
    p4 = np.cos(71.0 * np.pi * X - 59.0 * y[:, None])
    fine = smoothstep(0.86, 0.985, p1 * p2 * p3 * p4) ** 2

    q1 = np.sin(11.0 * np.pi * X + 9.0 * y[:, None])
    q2 = np.cos(19.0 * np.pi * X - 13.0 * y[:, None])
    q3 = np.sin(29.0 * np.pi * X + 23.0 * y[:, None])
    medium = smoothstep(0.93, 0.995, q1 * q2 * q3) ** 2

    layers = {
        "fine": fine,
        "fine_tw": (4.0 * p1 * p2).astype(np.float32),
        "medium": medium,
    }

    # Foreground stars: a beam cross + soft halo built from sin(pi*(X-x0)),
    # which is exactly periodic in x for any star position x0.
    flares = []
    for x0, y0, sigma in zip(
        params["flare_x"], params["flare_y"], params["flare_sigma"]
    ):
        sx = np.sin(np.pi * (X - x0))
        sy = y[:, None] - y0
        spread = np.exp(-((sx / (np.pi * sigma)) ** 2))
        beam = np.exp(-((sy / 0.006) ** 2)) * spread
        vbeam = np.exp(-((sx / 0.006) ** 2)) * np.exp(-((sy / 0.10) ** 2))
        halo = np.exp(-((sx / (np.pi * 0.025)) ** 2 + (sy / 0.018) ** 2))
        flares.append((beam, vbeam, halo))
    layers["flares"] = flares
    return layers


def flow_frame(X, Y, YN, phase, params, static=None):
    """Bright cosmic nebula flow (violet/magenta palette, star field).

    Look reference: glowing purple/magenta nebula clouds over deep
    violet space, lilac-white hot cores, cyan gaseous accents, and a
    dense field of twinkling stars with a few flared foreground stars.

    Periodicity rules (do not break these):
      * every x-dependent term is a sine/cosine of an integer multiple
        of pi * X, or a function of another already-periodic field;
      * every phase-dependent term uses an integer multiple of phase,
        so the animation closes exactly at phase = 2*pi;
      * glow and vignette depend on Y (or YN) only, never on X.
    """
    p0 = params["phase0"]
    if static is None:
        static = flow_static(X, Y, params)
    y = Y[:, 0]  # rows are identical; keep y-only math 1-D
    yn = YN[:, 0]

    u1 = np.pi * X
    u2 = 2.0 * np.pi * X

    t_y1 = (
        0.55 * y
        + 0.62 * np.sin(2.1 * y - phase + p0)
        + 0.34 * np.sin(3.3 * y - 2.0 * phase + p0)
        + 0.18 * np.sin(phase + p0)
    )
    t_y2 = (
        -0.75 * y
        + 0.35 * np.cos(3.0 * y - phase + p0)
        + 0.20 * np.sin(1.7 * y + 2.0 * phase)
    )
    theta1 = u1 + t_y1[:, None]
    theta2 = u2 + t_y2[:, None]

    # Domain-warped higher harmonics: functions of theta1/theta2 remain
    # exactly periodic in x, while adding organic lateral structure.
    theta3 = (
        4.0 * np.pi * X
        + 1.15 * y[:, None]
        + 0.55 * np.sin(1.3 * np.sin(theta1) + 1.6 * y[:, None] - phase)
        + 0.30 * np.sin(0.8 * np.sin(theta2) + 2.1 * y[:, None] + 2.0 * phase)
        + 0.12 * np.sin(phase + p0)
    )
    theta4 = (
        7.0 * np.pi * X
        - 1.35 * y[:, None]
        + 0.32 * np.sin(1.1 * np.sin(theta1) - phase)
        + 0.20 * np.cos(0.9 * np.cos(theta2) + 1.8 * y[:, None] + phase)
    )

    field = (
        0.85 * np.sin(theta1)
        + 0.40
        * np.sin(2.0 * theta1 + 0.5 * np.sin(2.2 * y + phase + p0)[:, None])
        + 0.30 * np.cos(theta2 + phase)
        + 0.40 * np.sin(theta3 - phase)
        + 0.24 * np.sin(2.0 * theta3 + 2.0 * phase)
        + 0.16 * np.cos(theta4 + phase)
        + 0.10 * np.cos(3.0 * theta2 + phase)
    )
    n = np.tanh(0.8 * field)

    deep_indigo = smoothstep(0.40, 0.95, -n)
    purple_body = smoothstep(-0.40, 0.35, n)
    violet_rich = smoothstep(-0.05, 0.55, n)
    magenta_hot = smoothstep(0.15, 0.70, n)
    lilac_core = smoothstep(0.45, 0.80, n)
    white_top = smoothstep(0.70, 0.92, n)
    cyan_wisp = np.exp(-((n + 0.05) / 0.13) ** 2)
    # Narrow ribbon highlights + fine dust gate on the warped harmonic.
    pink_filament = np.exp(-((n - 0.40) / 0.14) ** 2)
    gas_dust = np.exp(
        -(
            (
                np.sin(theta3 + 0.4 * np.sin(1.7 * y - phase)[:, None])
                - 0.35
            )
            / 0.25
        )
        ** 2
    )

    rgb = np.empty((*n.shape, 3), dtype=np.float32)
    rgb[:] = (22.0, 10.0, 46.0)
    rgb += deep_indigo[..., None] * np.array([24.0, 16.0, 66.0], dtype=np.float32)
    rgb += purple_body[..., None] * np.array([72.0, 22.0, 132.0], dtype=np.float32)
    rgb += violet_rich[..., None] * (
        np.array([120.0, 30.0, 185.0], dtype=np.float32) * params["tint"]
    )
    rgb += magenta_hot[..., None] * np.array([200.0, 45.0, 200.0], dtype=np.float32)
    rgb += lilac_core[..., None] * np.array([235.0, 150.0, 235.0], dtype=np.float32)
    rgb += white_top[..., None] * np.array([255.0, 235.0, 250.0], dtype=np.float32)
    rgb += cyan_wisp[..., None] * np.array([28.0, 85.0, 185.0], dtype=np.float32)
    rgb += pink_filament[..., None] * np.array([150.0, 40.0, 150.0], dtype=np.float32)
    rgb += gas_dust[..., None] * np.array([70.0, 45.0, 110.0], dtype=np.float32)

    # Twinkling pinprick stars (phase-periodic twinkle).
    twinkle = 0.60 + 0.40 * np.sin(2.0 * phase + static["fine_tw"])
    rgb += (static["fine"] * twinkle)[..., None] * np.array(
        [205.0, 195.0, 250.0], dtype=np.float32
    )
    rgb += static["medium"][..., None] * np.array(
        [255.0, 215.0, 250.0], dtype=np.float32
    )

    # Foreground flared stars with a gentle pulse.
    for (beam, vbeam, halo), amp, off in zip(
        static["flares"], params["flare_amp"], params["flare_off"]
    ):
        pulse = amp * (0.85 + 0.15 * np.sin(2.0 * phase + off))
        rgb += ((halo + beam * 0.9 + vbeam * 0.4) * pulse)[..., None] * np.array(
            [255.0, 235.0, 250.0], dtype=np.float32
        )

    # Vertical atmospheric glow: no x dependence, so the seam stays exact.
    glow = np.exp(-((yn - 0.10 * np.sin(phase + p0)) / 0.90) ** 2)[:, None]
    rgb += glow[..., None] * np.array([30.0, 12.0, 55.0], dtype=np.float32) * (
        0.80 + 0.20 * np.cos(phase)
    )

    # Vertical-only vignette (x-independent).
    vignette = (
        0.78
        + 0.22 * np.cos(0.5 * np.pi * np.clip(yn, -1.0, 1.0))
    )[:, None]
    rgb *= vignette[..., None]
    return rgb


def tunnel_frame(X, Y, phase):
    """Cinematic sunset tunnel (legacy v3 look)."""
    drift = 0.025 * np.sin(phase)
    pulse = 0.012 * np.cos(phase * 2.0)

    r = np.sqrt((X - drift) ** 2 + (Y + 0.012 * np.cos(phase)) ** 2)
    theta = np.arctan2(Y, X)
    warped_r = (
        r
        + 0.012 * np.sin(3.0 * theta - phase)
        + 0.008 * np.sin(5.0 * theta + 2.0 * phase)
    )

    field = np.empty((*r.shape, 3), dtype=np.float32)
    field[:] = (24.0, 5.0, 12.0)

    atmosphere = np.exp(-((warped_r / 0.95) ** 2))
    field += atmosphere[..., None] * np.array([95.0, 20.0, 4.0], dtype=np.float32)

    rings = [
        (0.16, 0.030, 0.75),
        (0.29, 0.035, 0.62),
        (0.43, 0.040, 0.80),
        (0.59, 0.048, 0.58),
        (0.77, 0.060, 0.40),
        (0.98, 0.075, 0.25),
    ]
    for index, (ring_r, width_r, strength) in enumerate(rings):
        moving_radius = ring_r + pulse * (1.0 + index * 0.12)
        ring = np.exp(-(((warped_r - moving_radius) / width_r) ** 2))
        field += ring[..., None] * np.array(
            [150.0 * strength, 48.0 * strength, 5.0 * strength],
            dtype=np.float32,
        )
        highlight = np.exp(
            -(((warped_r - moving_radius) / (width_r * 0.32)) ** 2)
        )
        field += highlight[..., None] * np.array(
            [35.0 * strength, 30.0 * strength, 5.0 * strength],
            dtype=np.float32,
        )

    core = np.exp(-((warped_r / 0.18) ** 2))
    halo = np.exp(-((warped_r / 0.34) ** 2))
    field += halo[..., None] * np.array([90.0, 35.0, 3.0], dtype=np.float32)
    field += core[..., None] * np.array([105.0, 72.0, 12.0], dtype=np.float32)

    field *= np.clip(1.0 - 0.55 * r ** 2, 0.28, 1.0)[..., None]
    return field


def aura_frame(X, Y, phase):
    """Soft radial light sources (legacy v3 look)."""
    cx = 0.08 * np.sin(phase)
    cy = 0.035 * (1.0 - np.cos(phase))
    r = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)

    outer = np.exp(-(((r - 0.50) / 0.36) ** 2))
    halo = np.exp(-(((r - 0.30) / 0.20) ** 2))
    core = np.exp(-((r / 0.19) ** 2))

    field = np.empty((*r.shape, 3), dtype=np.float32)
    field[:] = (190.0, 28.0, 80.0)
    field += outer[..., None] * np.array([45.0, 18.0, 25.0], dtype=np.float32)
    field += halo[..., None] * np.array([25.0, 0.0, 30.0], dtype=np.float32)
    field += core[..., None] * np.array([65.0, 70.0, 75.0], dtype=np.float32)
    return field


def encode_stream(style, width, height, fps, seconds, output, seed,
                  crf, preset, render_scale=1.0):
    frames = fps * seconds
    rw = max(2, int(round(width * render_scale / 2.0)) * 2)
    rh = max(2, int(round(height * render_scale / 2.0)) * 2)
    X, Y = make_grid(rw, rh)
    YN = Y / (rh / rw)
    params = flow_params(seed)
    static = flow_static(X, Y, params) if style == "flow" else None

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{rw}x{rh}",
        "-framerate", str(fps),
        "-i", "-",
    ]
    if (rw, rh) != (width, height):
        cmd += ["-vf", f"scale={width}:{height}:flags=lanczos"]
    cmd += [
        "-an",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    try:
        for i in range(frames):
            phase = 2.0 * np.pi * i / frames
            if style == "flow":
                field = flow_frame(X, Y, YN, phase, params, static)
            elif style == "tunnel":
                field = tunnel_frame(X, Y, phase)
            else:
                field = aura_frame(X, Y, phase)

            # Slow global brightness pulse; integer phase multiple keeps
            # the loop closed.
            field *= 0.97 + 0.03 * np.cos(phase)
            frame = np.clip(field, 0.0, 255.0).astype(np.uint8)
            proc.stdin.write(frame.tobytes())

            if (i + 1) % fps == 0:
                print(f"\rRendered {i + 1}/{frames} frames", end="")
    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()

    if proc.wait() != 0:
        raise RuntimeError("FFmpeg failed; see the error output above.")
    print(f"\nSaved {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--style", choices=["flow", "tunnel", "aura"], default="tunnel"
    )
    parser.add_argument(
        "--size", choices=sorted(SIZES), default="720p",
        help="4k is experimental on a 4 GB machine",
    )
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument(
        "--preset", default="veryfast",
        help="x264 preset (use ultrafast for quick previews)",
    )
    parser.add_argument(
        "--render-scale", type=float, default=1.0,
        help="internal render scale before upscaling (e.g. 0.5); "
             "lower is faster but softer",
    )
    parser.add_argument(
        "--output", default=None,
        help="output file; defaults to previews/<style>_<size>_<seconds>s_v4.mp4",
    )
    args = parser.parse_args()

    width, height = SIZES[args.size]
    if not 0.25 <= args.render_scale <= 1.0:
        parser.error("--render-scale must be between 0.25 and 1.0")
    output = Path(args.output) if args.output else Path(
        "previews", f"{args.style}_{args.size}_{args.seconds}s_v4.mp4"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"{args.style} {args.size} ({width}x{height}) "
        f"{args.fps}fps {args.seconds}s seed={args.seed} "
        f"render-scale={args.render_scale:g}"
    )
    encode_stream(
        args.style, width, height, args.fps, args.seconds, output,
        args.seed, args.crf, args.preset, args.render_scale,
    )


if __name__ == "__main__":
    main()
