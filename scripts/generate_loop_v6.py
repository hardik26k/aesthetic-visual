#!/usr/bin/env python3
"""Generate seamless ambient loops (flow / silk / tunnel / aura) — v6.

Current working renderer with Golden Ratio (phi ≈ 1.618) harmonic
frequencies and organic fluid dynamics. Frames are streamed as raw RGB24
into ffmpeg.

Usage:
    python scripts/generate_loop_v6.py --style silk --seconds 12 --seed 7
    python scripts/generate_loop_v6.py --style phi_flow --seconds 12
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
        "tint": rng.uniform(0.94, 1.06, 3).astype(np.float32),
        # Field weights for the multi-directional currents.
        "main_amp": float(rng.uniform(0.72, 0.92)),
        "warp_amp": float(rng.uniform(0.50, 0.75)),
        "drift_amp": float(rng.uniform(0.10, 0.24)),
        # Positive bias raises warm coverage (target 75-85%).
        "bias": float(rng.uniform(0.02, 0.10)),
    }


def silk_params(seed):
    """Deterministic variation for the iridescent silk caustics style."""
    rng = np.random.default_rng(seed)
    return {
        "phase0": float(rng.uniform(0.0, 2.0 * np.pi)),
        "tint": rng.uniform(0.92, 1.08, 3).astype(np.float32),
        "warp_amp": float(rng.uniform(0.40, 0.65)),
        "drift_amp": float(rng.uniform(0.12, 0.28)),
    }


def flow_frame(X, Y, YN, phase, params):
    """Molten amber currents: broad warm fields, a few dark channels.

    Look reference: flowing molten amber / orange / burnt-red fields
    covering most of the frame, with occasional deep burgundy channels
    for contrast. Highlights are soft and tinted, never neon-white.

    Motion: multi-directional currents — theta1/theta2 are long diagonal
    wave trains drifting at different speeds, theta3/theta4 are warped
    harmonics that bend them; shapes merge, stretch and separate as the
    phase advances (``--seconds`` is the full loop period).

    Periodicity rules (do not break these):
      * every x-dependent term is a sine/cosine of an integer multiple
        of pi * X, or a function of another already-periodic field;
      * every phase-dependent term uses an integer multiple of phase,
        so the animation closes exactly at phase = 2*pi;
      * Flow has no vignette by design; no x-dependent envelope.
    """
    p0 = params["phase0"]
    warp = params["warp_amp"]
    drift = params["drift_amp"]
    main = params["main_amp"]
    bias = params["bias"]
    y = Y[:, 0]  # rows are identical; keep y-only math 1-D

    u1 = np.pi * X
    u2 = 2.0 * np.pi * X

    t_y1 = (
        0.55 * y
        + warp * np.sin(2.1 * y - phase + p0)
        + 0.34 * np.sin(3.3 * y - 2.0 * phase + p0)
        + drift * np.sin(phase + p0)
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
        main * np.sin(theta1)
        + 0.40
        * np.sin(2.0 * theta1 + 0.5 * np.sin(2.2 * y + phase + p0)[:, None])
        + 0.30 * np.cos(theta2 + phase)
        + 0.40 * np.sin(theta3 - phase)
        + 0.24 * np.sin(2.0 * theta3 + 2.0 * phase)
        + 0.16 * np.cos(theta4 + phase)
        + 0.10 * np.cos(3.0 * theta2 + phase)
    )
    n = np.tanh(0.8 * field + bias)

    # --- molten palette: broad warm body, few deep channels ---
    channel_dark = smoothstep(0.10, 0.70, -n)      # deep burgundy channels
    warm_broad = smoothstep(-0.30, 0.35, n)        # everything warm-ish
    amber_body = smoothstep(-0.10, 0.55, n)        # mid amber fields
    molten_crest = smoothstep(0.35, 0.95, n)       # hot orange crests
    soft_sheen = np.exp(-((n - 0.50) / 0.30) ** 2)  # gentle gold sheen
    filament = np.exp(                              # warm seam shading
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
    rgb[:] = (14.0, 4.0, 10.0)
    rgb += channel_dark[..., None] * np.array([80.0, 16.0, 18.0], dtype=np.float32)
    rgb += warm_broad[..., None] * np.array([96.0, 30.0, 18.0], dtype=np.float32)
    rgb += amber_body[..., None] * (
        np.array([150.0, 66.0, 22.0], dtype=np.float32) * params["tint"]
    )
    rgb += molten_crest[..., None] * np.array([120.0, 72.0, 22.0], dtype=np.float32)
    rgb += soft_sheen[..., None] * np.array([55.0, 40.0, 18.0], dtype=np.float32)
    rgb += filament[..., None] * np.array([36.0, 16.0, 10.0], dtype=np.float32)
    return rgb


PHI = 1.61803398875
PHI_INV = 0.61803398875


def silk_frame(X, Y, YN, phase, params):
    """Iridescent liquid silk waves with cyan luminous crests & golden rim refractions.

    Inspired by flowing caustic wave ribbons with fine striations, deep navy
    background folds, luminous cyan crests, and glowing golden-amber rim refractions.
    Uses Golden Ratio frequencies for harmonic distribution.
    """
    p0 = params["phase0"]
    warp = params["warp_amp"]
    y = Y[:, 0]

    u1 = np.pi * X
    u2 = 2.0 * np.pi * X

    # Golden Ratio-informed frequencies
    t_y1 = (
        0.75 * y
        + warp * np.sin(2.0 * PHI * y - phase + p0)
        + 0.30 * np.sin(3.0 * PHI * y - 2.0 * phase)
    )
    t_y2 = -0.70 * y + 0.38 * np.cos(2.0 * PHI * y + phase + p0)

    theta1 = u1 + t_y1[:, None]
    theta2 = u2 + t_y2[:, None]

    # Warped harmonics using PHI to prevent clashing
    theta3 = (
        4.0 * np.pi * X
        + 1.35 * y[:, None]
        + 0.50 * np.sin(1.5 * np.sin(theta1) + PHI * y[:, None] - phase)
        + 0.28 * np.sin(0.85 * np.sin(theta2) + 2.0 * PHI * y[:, None] + 2.0 * phase)
    )

    theta4 = (
        6.0 * np.pi * X
        - 1.10 * y[:, None]
        + 0.35 * np.sin(1.2 * np.sin(theta1) + phase)
    )

    field = (
        0.80 * np.sin(theta1)
        + 0.45 * np.sin(2.0 * theta1 + 0.4 * np.sin(2.0 * PHI * y + phase)[:, None])
        + 0.35 * np.cos(theta2 + phase)
        + 0.40 * np.sin(theta3 - phase)
        + 0.20 * np.sin(2.0 * theta3 + 2.0 * phase)
        + 0.15 * np.cos(theta4 + phase)
    )

    n = np.tanh(0.70 * field - 0.05)

    # High-frequency silky striations parallel to wave front
    ribs1 = np.sin(20.0 * np.pi * X + 15.0 * y[:, None] + 7.0 * np.sin(theta1) - 2.0 * phase)
    ribs2 = np.cos(34.0 * np.pi * X - 22.0 * y[:, None] + 5.0 * np.cos(theta2) + phase)

    rib_mask1 = smoothstep(-0.3, 0.5, n) * (0.5 + 0.5 * ribs1) ** 1.6
    rib_mask2 = smoothstep(-0.1, 0.7, n) * (0.5 + 0.5 * ribs2) ** 2.0

    dark_channels = smoothstep(0.05, 0.70, -n)
    teal_depth = smoothstep(-0.45, 0.20, n)
    cyan_body = smoothstep(-0.10, 0.55, n)
    cyan_crest = smoothstep(0.30, 0.85, n)
    white_hot_core = smoothstep(0.70, 0.98, n)

    edge_gradient = np.exp(-((n - 0.15) / 0.18) ** 2)
    gold_rim = edge_gradient * (0.55 + 0.45 * np.cos(theta3 - phase))
    warm_amber_accent = np.exp(-((n - 0.40) / 0.15) ** 2) * (0.6 + 0.4 * np.sin(theta1 + 1.2 * y[:, None]))

    rgb = np.empty((*n.shape, 3), dtype=np.float32)
    rgb[:] = (2.0, 10.0, 24.0)
    rgb += dark_channels[..., None] * np.array([4.0, 22.0, 42.0], dtype=np.float32)
    rgb += teal_depth[..., None] * np.array([0.0, 85.0, 125.0], dtype=np.float32)
    rgb += cyan_body[..., None] * np.array([0.0, 175.0, 195.0], dtype=np.float32) * params["tint"]
    rgb += cyan_crest[..., None] * np.array([0.0, 230.0, 230.0], dtype=np.float32)
    rgb += white_hot_core[..., None] * np.array([160.0, 255.0, 245.0], dtype=np.float32)
    rgb += gold_rim[..., None] * np.array([225.0, 160.0, 50.0], dtype=np.float32)
    rgb += warm_amber_accent[..., None] * np.array([190.0, 120.0, 35.0], dtype=np.float32)
    rgb += rib_mask1[..., None] * np.array([30.0, 160.0, 180.0], dtype=np.float32)
    rgb += rib_mask2[..., None] * np.array([40.0, 130.0, 150.0], dtype=np.float32)

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
    params = silk_params(seed) if style == "silk" else flow_params(seed)

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
                field = flow_frame(X, Y, YN, phase, params)
            elif style == "silk":
                field = silk_frame(X, Y, YN, phase, params)
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
        "--style", choices=["flow", "silk", "tunnel", "aura"], default="tunnel"
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
        help="output file; defaults to previews/<style>_<size>_<seconds>s_v5.mp4",
    )
    args = parser.parse_args()

    width, height = SIZES[args.size]
    if not 0.25 <= args.render_scale <= 1.0:
        parser.error("--render-scale must be between 0.25 and 1.0")
    output = Path(args.output) if args.output else Path(
        "previews", f"{args.style}_{args.size}_{args.seconds}s_v5.mp4"
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
