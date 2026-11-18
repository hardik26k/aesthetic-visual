#!/usr/bin/env python3
"""Generate seamless ambient loops (flow / silk / tunnel / aura) — v7.

Dynamic "DNA" renderer: The `silk` style now generates unique pattern
structures and palettes based on the input seed, using Golden Ratio
harmonic frequencies for organic non-repeating flow.
"""

import argparse
import subprocess
from pathlib import Path

import numpy as np

SIZES = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "720p_vert": (720, 1280),
    "1080p_vert": (1080, 1920),
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
    """Seed-driven DNA parameters for Flow (molten currents)."""
    rng = np.random.default_rng(seed)
    
    # Motion & Pattern DNA
    dir_x = int(rng.choice([-1, 1]))
    dir_y = int(rng.choice([-1, 1]))
    kx1 = int(rng.choice([1, 2]))
    kx2 = int(rng.choice([2, 3]))
    slope1 = float(rng.uniform(0.4, 0.8)) * dir_y
    slope2 = float(rng.uniform(-0.8, -0.4)) * dir_y
    
    # Palette choice
    palette_choice = rng.integers(0, 3)
    if palette_choice == 0:
        # Molten Amber (Classic)
        base_col = np.array([14.0, 4.0, 10.0], dtype=np.float32)
        dark_col = np.array([80.0, 16.0, 18.0], dtype=np.float32)
        warm_col = np.array([96.0, 30.0, 18.0], dtype=np.float32)
        amber_col = np.array([150.0, 66.0, 22.0], dtype=np.float32)
        crest_col = np.array([210.0, 110.0, 30.0], dtype=np.float32)
    elif palette_choice == 1:
        # Sapphire Plasma (Blue/Teal Flow)
        base_col = np.array([4.0, 10.0, 24.0], dtype=np.float32)
        dark_col = np.array([10.0, 24.0, 60.0], dtype=np.float32)
        warm_col = np.array([18.0, 60.0, 120.0], dtype=np.float32)
        amber_col = np.array([22.0, 120.0, 190.0], dtype=np.float32)
        crest_col = np.array([60.0, 220.0, 240.0], dtype=np.float32)
    else:
        # Violet Flare (Purple/Magenta Flow)
        base_col = np.array([18.0, 4.0, 20.0], dtype=np.float32)
        dark_col = np.array([50.0, 10.0, 60.0], dtype=np.float32)
        warm_col = np.array([110.0, 20.0, 110.0], dtype=np.float32)
        amber_col = np.array([180.0, 40.0, 170.0], dtype=np.float32)
        crest_col = np.array([240.0, 120.0, 230.0], dtype=np.float32)

    return {
        "phase0": float(rng.uniform(0.0, 2.0 * np.pi)),
        "tint": rng.uniform(0.92, 1.08, 3).astype(np.float32),
        "main_amp": float(rng.uniform(0.72, 0.92)),
        "warp_amp": float(rng.uniform(0.40, 0.75)),
        "bias": float(rng.uniform(0.02, 0.10)),
        "dir_x": dir_x,
        "dir_y": dir_y,
        "kx1": kx1,
        "kx2": kx2,
        "slope1": slope1,
        "slope2": slope2,
        "base_col": base_col,
        "dark_col": dark_col,
        "warm_col": warm_col,
        "amber_col": amber_col,
        "crest_col": crest_col,
    }


def silk_params(seed):
    """Dynamic DNA parameter generator for the iridescent silk caustics style."""
    rng = np.random.default_rng(seed)
    
    # Motion & Pattern DNA
    dir_x = int(rng.choice([-1, 1]))
    dir_y = int(rng.choice([-1, 1]))
    f_scale = float(rng.uniform(0.8, 1.4))
    
    # Select a distinct color palette mode based on seed
    palette_choice = rng.integers(0, 4)
    if palette_choice == 0:
        # Deep Ocean Cyan
        base_col = np.array([2.0, 10.0, 24.0], dtype=np.float32)
        deep_col = np.array([4.0, 22.0, 42.0], dtype=np.float32)
        mid_col  = np.array([0.0, 85.0, 125.0], dtype=np.float32)
        crest_col = np.array([0.0, 190.0, 205.0], dtype=np.float32)
        hot_col  = np.array([160.0, 255.0, 245.0], dtype=np.float32)
        rim_col  = np.array([225.0, 160.0, 50.0], dtype=np.float32)
    elif palette_choice == 1:
        # Amethyst Nebula
        base_col = np.array([12.0, 4.0, 24.0], dtype=np.float32)
        deep_col = np.array([28.0, 8.0, 52.0], dtype=np.float32)
        mid_col  = np.array([95.0, 20.0, 140.0], dtype=np.float32)
        crest_col = np.array([210.0, 50.0, 210.0], dtype=np.float32)
        hot_col  = np.array([255.0, 180.0, 250.0], dtype=np.float32)
        rim_col  = np.array([50.0, 210.0, 200.0], dtype=np.float32)
    elif palette_choice == 2:
        # Emerald Aurora
        base_col = np.array([2.0, 18.0, 14.0], dtype=np.float32)
        deep_col = np.array([4.0, 38.0, 28.0], dtype=np.float32)
        mid_col  = np.array([0.0, 120.0, 85.0], dtype=np.float32)
        crest_col = np.array([0.0, 220.0, 140.0], dtype=np.float32)
        hot_col  = np.array([150.0, 255.0, 210.0], dtype=np.float32)
        rim_col  = np.array([220.0, 200.0, 60.0], dtype=np.float32)
    else:
        # Crimson Sunset
        base_col = np.array([22.0, 6.0, 8.0], dtype=np.float32)
        deep_col = np.array([45.0, 12.0, 16.0], dtype=np.float32)
        mid_col  = np.array([140.0, 35.0, 40.0], dtype=np.float32)
        crest_col = np.array([230.0, 90.0, 40.0], dtype=np.float32)
        hot_col  = np.array([255.0, 210.0, 120.0], dtype=np.float32)
        rim_col  = np.array([255.0, 220.0, 180.0], dtype=np.float32)

    return {
        "phase0": float(rng.uniform(0.0, 2.0 * np.pi)),
        "tint": rng.uniform(0.90, 1.10, 3).astype(np.float32),
        "warp_amp": float(rng.uniform(0.35, 0.85)),
        "freq_scale": f_scale,
        "dir_x": dir_x,
        "dir_y": dir_y,
        "base_col": base_col,
        "deep_col": deep_col,
        "mid_col": mid_col,
        "crest_col": crest_col,
        "hot_col": hot_col,
        "rim_col": rim_col,
        # Chroma push applied per frame (drawn last so existing seeds keep
        # their palette and motion DNA unchanged).
        "vibrance": float(rng.uniform(1.30, 1.45)),
    }


def tunnel_params(seed):
    """Seed-driven DNA for the cinematic tunnel."""
    rng = np.random.default_rng(seed)
    palette_choice = rng.integers(0, 3)
    if palette_choice == 0:
        # Sunset (Classic)
        base = np.array([24.0, 5.0, 12.0], dtype=np.float32)
        atmos = np.array([95.0, 20.0, 4.0], dtype=np.float32)
        ring_base = np.array([150.0, 48.0, 5.0], dtype=np.float32)
        core = np.array([105.0, 72.0, 12.0], dtype=np.float32)
    elif palette_choice == 1:
        # Neon Blue
        base = np.array([5.0, 12.0, 30.0], dtype=np.float32)
        atmos = np.array([10.0, 40.0, 120.0], dtype=np.float32)
        ring_base = np.array([40.0, 180.0, 255.0], dtype=np.float32)
        core = np.array([180.0, 230.0, 255.0], dtype=np.float32)
    else:
        # Toxic Green
        base = np.array([8.0, 20.0, 5.0], dtype=np.float32)
        atmos = np.array([20.0, 80.0, 20.0], dtype=np.float32)
        ring_base = np.array([80.0, 255.0, 40.0], dtype=np.float32)
        core = np.array([210.0, 255.0, 120.0], dtype=np.float32)

    return {
        "dir": int(rng.choice([-1, 1])),
        "complexity": float(rng.uniform(0.8, 1.5)),
        "base_col": base,
        "atmos_col": atmos,
        "ring_col": ring_base,
        "core_col": core,
    }


def aura_params(seed):
    """Seed-driven DNA for the radial aura."""
    rng = np.random.default_rng(seed)
    palette_choice = rng.integers(0, 3)
    if palette_choice == 0:
        # Pink/Violet
        base = np.array([190.0, 28.0, 80.0], dtype=np.float32)
        outer = np.array([45.0, 18.0, 25.0], dtype=np.float32)
        core = np.array([65.0, 70.0, 75.0], dtype=np.float32)
    elif palette_choice == 1:
        # Golden Hour
        base = np.array([120.0, 60.0, 20.0], dtype=np.float32)
        outer = np.array([60.0, 30.0, 10.0], dtype=np.float32)
        core = np.array([255.0, 220.0, 150.0], dtype=np.float32)
    else:
        # Deep Sea
        base = np.array([10.0, 40.0, 100.0], dtype=np.float32)
        outer = np.array([5.0, 20.0, 60.0], dtype=np.float32)
        core = np.array([150.0, 240.0, 255.0], dtype=np.float32)

    return {
        "dir": int(rng.choice([-1, 1])),
        "base_col": base,
        "outer_col": outer,
        "core_col": core,
    }



def flow_frame(X, Y, YN, phase, params):
    """Molten amber currents: seed-driven patterns, directions, and colors."""
    p0 = params["phase0"]
    warp = params["warp_amp"]
    main = params["main_amp"]
    bias = params["bias"]
    dir_x = params["dir_x"]
    dir_y = params["dir_y"]
    kx1 = params["kx1"]
    kx2 = params["kx2"]
    slope1 = params["slope1"]
    slope2 = params["slope2"]
    y = Y[:, 0]

    u1 = kx1 * np.pi * X * dir_x
    u2 = kx2 * np.pi * X * dir_x

    t_y1 = (
        slope1 * y
        + warp * np.sin(2.1 * y - dir_y * phase + p0)
        + 0.34 * np.sin(3.3 * y - 2.0 * dir_y * phase + p0)
    )
    t_y2 = (
        slope2 * y
        + 0.35 * np.cos(3.0 * y - dir_y * phase + p0)
        + 0.20 * np.sin(1.7 * y + 2.0 * dir_y * phase)
    )
    theta1 = u1 + t_y1[:, None]
    theta2 = u2 + t_y2[:, None]

    theta3 = (
        (kx1 + kx2) * np.pi * X * dir_x
        + 1.15 * y[:, None]
        + 0.55 * np.sin(1.3 * np.sin(theta1) + 1.6 * y[:, None] - dir_y * phase)
        + 0.30 * np.sin(0.8 * np.sin(theta2) + 2.1 * y[:, None] + 2.0 * dir_y * phase)
    )
    theta4 = (
        (kx1 * 3) * np.pi * X * dir_x
        - 1.35 * y[:, None]
        + 0.32 * np.sin(1.1 * np.sin(theta1) - dir_y * phase)
    )

    field = (
        main * np.sin(theta1)
        + 0.40 * np.sin(2.0 * theta1 + 0.5 * np.sin(2.2 * y + dir_y * phase + p0)[:, None])
        + 0.30 * np.cos(theta2 + dir_y * phase)
        + 0.40 * np.sin(theta3 - dir_y * phase)
        + 0.24 * np.sin(2.0 * theta3 + 2.0 * dir_y * phase)
        + 0.16 * np.cos(theta4 + dir_y * phase)
    )
    n = np.tanh(0.8 * field + bias)

    channel_dark = smoothstep(0.10, 0.70, -n)
    warm_broad = smoothstep(-0.30, 0.35, n)
    amber_body = smoothstep(-0.10, 0.55, n)
    molten_crest = smoothstep(0.35, 0.95, n)
    soft_sheen = np.exp(-((n - 0.50) / 0.30) ** 2)
    filament = np.exp(
        -(
            (
                np.sin(theta3 + 0.4 * np.sin(1.7 * y - dir_y * phase)[:, None])
                - 0.35
            )
            / 0.25
        )
        ** 2
    )

    rgb = np.empty((*n.shape, 3), dtype=np.float32)
    rgb[:] = params["base_col"]
    rgb += channel_dark[..., None] * params["dark_col"]
    rgb += warm_broad[..., None] * params["warm_col"]
    rgb += amber_body[..., None] * (params["amber_col"] * params["tint"])
    rgb += molten_crest[..., None] * params["crest_col"]
    rgb += soft_sheen[..., None] * (params["crest_col"] * 0.4)
    rgb += filament[..., None] * (params["warm_col"] * 0.4)
    return rgb


PHI = 1.61803398875
PHI_INV = 0.61803398875


def silk_frame(X, Y, YN, phase, params):
    """Iridescent liquid silk waves with seed-driven patterns, directions, and palettes."""
    p0 = params["phase0"]
    warp = params["warp_amp"]
    f_scale = params["freq_scale"]
    dir_x = params["dir_x"]
    dir_y = params["dir_y"]
    y = Y[:, 0]

    u1 = np.pi * X * dir_x
    u2 = 2.0 * np.pi * X * dir_x

    t_y1 = (
        0.75 * y
        + warp * np.sin(2.0 * PHI * f_scale * y - dir_y * phase + p0)
        + 0.30 * np.sin(3.0 * PHI * f_scale * y - 2.0 * dir_y * phase)
    )
    t_y2 = -0.70 * y + 0.38 * np.cos(2.0 * PHI * f_scale * y + dir_y * phase + p0)

    theta1 = u1 + t_y1[:, None]
    theta2 = u2 + t_y2[:, None]

    theta3 = (
        4.0 * np.pi * X * dir_x
        + 1.35 * y[:, None]
        + 0.50 * np.sin(1.5 * np.sin(theta1) + PHI * f_scale * y[:, None] - dir_y * phase)
        + 0.28 * np.sin(0.85 * np.sin(theta2) + 2.0 * PHI * f_scale * y[:, None] + 2.0 * dir_y * phase)
    )

    theta4 = (
        6.0 * np.pi * X * dir_x
        - 1.10 * y[:, None]
        + 0.35 * np.sin(1.2 * np.sin(theta1) + dir_y * phase)
    )

    field = (
        0.80 * np.sin(theta1)
        + 0.45 * np.sin(2.0 * theta1 + 0.4 * np.sin(2.0 * PHI * f_scale * y + dir_y * phase)[:, None])
        + 0.35 * np.cos(theta2 + dir_y * phase)
        + 0.40 * np.sin(theta3 - dir_y * phase)
        + 0.20 * np.sin(2.0 * theta3 + 2.0 * dir_y * phase)
        + 0.15 * np.cos(theta4 + dir_y * phase)
    )

    n = np.tanh(0.70 * field - 0.05)

    ribs1 = np.sin(20.0 * np.pi * X * dir_x + 15.0 * y[:, None] + 7.0 * np.sin(theta1) - 2.0 * dir_y * phase)
    ribs2 = np.cos(34.0 * np.pi * X * dir_x - 22.0 * y[:, None] + 5.0 * np.cos(theta2) + dir_y * phase)

    rib_mask1 = smoothstep(-0.3, 0.5, n) * (0.5 + 0.5 * ribs1) ** 1.6
    rib_mask2 = smoothstep(-0.1, 0.7, n) * (0.5 + 0.5 * ribs2) ** 2.0

    dark_channels = smoothstep(0.05, 0.70, -n)
    teal_depth = smoothstep(-0.45, 0.20, n)
    cyan_body = smoothstep(-0.10, 0.55, n)
    cyan_crest = smoothstep(0.30, 0.85, n)
    white_hot_core = smoothstep(0.70, 0.98, n)

    edge_gradient = np.exp(-((n - 0.15) / 0.18) ** 2)
    gold_rim = edge_gradient * (0.55 + 0.45 * np.cos(theta3 - dir_y * phase))
    warm_amber_accent = np.exp(-((n - 0.40) / 0.15) ** 2) * (0.6 + 0.4 * np.sin(theta1 + 1.2 * y[:, None]))

    rgb = np.empty((*n.shape, 3), dtype=np.float32)
    rgb[:] = params["base_col"]
    rgb += dark_channels[..., None] * params["deep_col"]
    rgb += teal_depth[..., None] * params["mid_col"]
    rgb += cyan_body[..., None] * params["mid_col"] * params["tint"]

    # Crest and hot core REPLACE the accumulated colour instead of adding on
    # top: additive stacking drove crest zones far past 255 and the hard
    # clip muted their hue (the washed-out look in encoded output).
    crest_w = cyan_crest[..., None]
    rgb = rgb * (1.0 - crest_w) + params["crest_col"] * crest_w
    hot_w = white_hot_core[..., None]
    rgb = rgb * (1.0 - hot_w) + params["hot_col"] * hot_w

    # Rib shimmer only outside the hot core, so it does not re-overflow it.
    rib_w = 1.0 - white_hot_core[..., None]
    rgb += rib_mask1[..., None] * (params["crest_col"] * 0.4) * rib_w
    rgb += rib_mask2[..., None] * (params["crest_col"] * 0.3) * rib_w

    rgb += gold_rim[..., None] * params["rim_col"]
    rgb += warm_amber_accent[..., None] * (params["rim_col"] * 0.8)

    # --- Out-of-gamut recovery --------------------------------------------
    # The additive build exceeds 255 wherever masks stack (crest zones).
    # Hard-clipping one channel mutes the hue; instead scale each pixel back
    # onto the gamut so crest colours keep their saturation.
    mx = rgb.max(axis=-1)
    scale = np.where(mx > 255.0, 255.0 / np.maximum(mx, 1e-5), 1.0)
    rgb = rgb * scale[..., None]

    # --- Midtone lift -----------------------------------------------------
    # Gamut recovery dims the crest zones; a gentle per-channel gamma lift
    # restores midtone brightness while keeping chroma wide.
    rgb = 255.0 * (rgb / 255.0) ** 0.88

    # --- Vibrance stage ---------------------------------------------------
    # Push chroma away from luma so the palette reads vivid. Pointwise on an
    # already-periodic field, so the seam is unaffected. Highlights are
    # soft-protected: chroma is scaled back per-pixel only where a channel
    # would otherwise clip, preserving hue instead of hard-clipping.
    luma = (
        rgb[..., 0] * 0.2126
        + rgb[..., 1] * 0.7152
        + rgb[..., 2] * 0.0722
    )
    chroma = (rgb - luma[..., None]) * params.get("vibrance", 1.35)
    excess = np.maximum(chroma - (255.0 - luma[..., None]), 0.0)
    k = 1.0 - excess.max(axis=-1) / np.maximum(
        np.abs(chroma).max(axis=-1), 1e-5
    )
    k = np.clip(k, 0.0, 1.0)[..., None]
    rgb = luma[..., None] + chroma * k

    return rgb


def tunnel_frame(X, Y, phase, params):
    """Cinematic sunset tunnel with seed-driven palettes and motion direction."""
    dir_val = params["dir"]
    comp = params["complexity"]
    
    drift = 0.025 * np.sin(phase * dir_val)
    pulse = 0.012 * np.cos(phase * 2.0 * dir_val)

    r = np.sqrt((X - drift) ** 2 + (Y + 0.012 * np.cos(phase * dir_val)) ** 2)
    theta = np.arctan2(Y, X)
    warped_r = (
        r
        + 0.012 * comp * np.sin(3.0 * theta - phase * dir_val)
        + 0.008 * comp * np.sin(5.0 * theta + 2.0 * phase * dir_val)
    )

    field = np.empty((*r.shape, 3), dtype=np.float32)
    field[:] = params["base_col"]

    atmosphere = np.exp(-((warped_r / 0.95) ** 2))
    field += atmosphere[..., None] * params["atmos_col"]

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
        field += ring[..., None] * (params["ring_col"] * strength)
        highlight = np.exp(
            -(((warped_r - moving_radius) / (width_r * 0.32)) ** 2)
        )
        field += highlight[..., None] * (params["core_col"] * strength * 0.3)

    core = np.exp(-((warped_r / 0.18) ** 2))
    halo = np.exp(-((warped_r / 0.34) ** 2))
    field += halo[..., None] * (params["atmos_col"] * 0.9)
    field += core[..., None] * params["core_col"]

    field *= np.clip(1.0 - 0.55 * r ** 2, 0.28, 1.0)[..., None]
    return field


def aura_frame(X, Y, phase, params):
    """Soft radial light sources with seed-driven palettes and motion direction."""
    dir_val = params["dir"]
    cx = 0.08 * np.sin(phase * dir_val)
    cy = 0.035 * (1.0 - np.cos(phase * dir_val))
    r = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)

    outer = np.exp(-(((r - 0.50) / 0.36) ** 2))
    halo = np.exp(-(((r - 0.30) / 0.20) ** 2))
    core = np.exp(-((r / 0.19) ** 2))

    field = np.empty((*r.shape, 3), dtype=np.float32)
    field[:] = params["base_col"]
    field += outer[..., None] * params["outer_col"]
    field += halo[..., None] * (params["outer_col"] * 0.6)
    field += core[..., None] * params["core_col"]
    return field


def encode_stream(style, width, height, fps, seconds, output, seed,
                  crf, preset, render_scale=1.0):
    frames = fps * seconds
    rw = max(2, int(round(width * render_scale / 2.0)) * 2)
    rh = max(2, int(round(height * render_scale / 2.0)) * 2)
    X, Y = make_grid(rw, rh)
    YN = Y / (rh / rw)
    
    if style == "silk":
        params = silk_params(seed)
    elif style == "flow":
        params = flow_params(seed)
    elif style == "tunnel":
        params = tunnel_params(seed)
    else:
        params = aura_params(seed)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{rw}x{rh}",
        "-framerate", str(fps),
        "-i", "-",
    ]
    # Always route through scale so the RGB->YUV conversion uses the BT.709
    # matrix even when no resize is needed, then tag the stream as 709.
    # Without this, players guess 601 vs 709 and colours shift dull.
    cmd += [
        "-vf", f"scale={width}:{height}:flags=lanczos:out_color_matrix=bt709",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
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
                field = tunnel_frame(X, Y, phase, params)
            else:
                field = aura_frame(X, Y, phase, params)

            # Slow global brightness pulse; integer phase multiple keeps
            # the loop closed.
            field *= 0.97 + 0.03 * np.cos(phase)
            frame = np.clip(field, 0.0, 255.0).astype(np.uint8)
            proc.stdin.write(frame.tobytes())

            if (i + 1) % fps == 0:
                print(f"\rRendered {i + 1}/{frames} frames", end="", flush=True)
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
        help="output file; defaults to previews/<style>_<size>_<seconds>s_v7.mp4",
    )
    args = parser.parse_args()

    width, height = SIZES[args.size]
    if not 0.25 <= args.render_scale <= 1.0:
        parser.error("--render-scale must be between 0.25 and 1.0")
    output = Path(args.output) if args.output else Path(
        "previews", f"{args.style}_{args.size}_{args.seconds}s_v7.mp4"
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
