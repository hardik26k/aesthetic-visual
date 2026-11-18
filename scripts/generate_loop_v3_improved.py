
import argparse
import subprocess
import numpy as np


def render(style, width, height, fps, seconds, output):
    frames = fps * seconds

    # Coordinate grid: keep all calculations normalized.
    x = (np.arange(width, dtype=np.float32) / width - 0.5) * 2
    y = (np.arange(height, dtype=np.float32) / height - 0.5) * 2
    X, Y = np.meshgrid(x, y)
    Y *= height / width

    radius = np.sqrt(X * X + Y * Y)
    vignette = np.clip(1 - 0.65 * radius**2, 0.2, 1)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output,
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    try:
        for i in range(frames):
            phase = 2 * np.pi * i / frames
            breathing = np.sin(phase)
            breathing2 = np.cos(phase)

            if style == "tunnel":
                # Cinematic sunset tunnel:
                # layered illumination, soft rings, and
                # two periodic motion frequencies.

                drift = 0.025 * np.sin(phase)
                pulse = 0.012 * np.cos(phase * 2)

                r = np.sqrt(
                    (X - drift) ** 2
                    + (Y + 0.012 * np.cos(phase)) ** 2
                )

                theta = np.arctan2(Y, X)

                # Subtle periodic distortion prevents the
                # tunnel from looking like a static target.
                warped_r = (
                    r
                    + 0.012 * np.sin(3 * theta - phase)
                    + 0.008 * np.sin(5 * theta + 2 * phase)
                )

                # Warm dark background.
                field = np.zeros(
                    (height, width, 3), dtype=np.float32
                )
                field[:] = [24, 5, 12]

                # Broad atmospheric glow.
                atmosphere = np.exp(
                    -(warped_r / 0.95) ** 2
                )
                field += atmosphere[..., None] * np.array(
                    [95, 20, 4], dtype=np.float32
                )

                # Several soft luminous rings. Each ring
                # has a different width and intensity.
                rings = [
                    (0.16, 0.030, 0.75),
                    (0.29, 0.035, 0.62),
                    (0.43, 0.040, 0.80),
                    (0.59, 0.048, 0.58),
                    (0.77, 0.060, 0.40),
                    (0.98, 0.075, 0.25),
                ]

                for index, (ring_r, width_r, strength) in enumerate(rings):
                    moving_radius = (
                        ring_r
                        + pulse * (1 + index * 0.12)
                    )

                    ring = np.exp(
                        -(
                            (warped_r - moving_radius)
                            / width_r
                        ) ** 2
                    )

                    # Orange outer light with a restrained
                    # golden highlight.
                    field += ring[..., None] * np.array(
                        [
                            150 * strength,
                            48 * strength,
                            5 * strength,
                        ],
                        dtype=np.float32,
                    )

                    highlight = np.exp(
                        -(
                            (warped_r - moving_radius)
                            / (width_r * 0.32)
                        ) ** 2
                    )

                    field += highlight[..., None] * np.array(
                        [
                            35 * strength,
                            30 * strength,
                            5 * strength,
                        ],
                        dtype=np.float32,
                    )

                # Central luminous portal, with a soft halo.
                core = np.exp(
                    -(warped_r / 0.18) ** 2
                )
                halo = np.exp(
                    -(warped_r / 0.34) ** 2
                )

                field += halo[..., None] * np.array(
                    [90, 35, 3], dtype=np.float32
                )
                field += core[..., None] * np.array(
                    [105, 72, 12], dtype=np.float32
                )

                # Slightly darken the outer edges to focus
                # attention toward the illuminated center.
                vignette = np.clip(
                    1 - 0.55 * r**2, 0.28, 1
                )
                field *= vignette[..., None]


            elif style == "aura":
                # Multiple soft radial light sources.
                cx = 0.08 * np.sin(phase)
                cy = 0.035 * (1 - np.cos(phase))
                r = np.sqrt((X - cx)**2 + (Y - cy)**2)

                outer = np.exp(-((r - 0.50) / 0.36) ** 2)
                halo = np.exp(-((r - 0.30) / 0.20) ** 2)
                core = np.exp(-(r / 0.19) ** 2)

                field = np.zeros((height, width, 3), dtype=np.float32)
                field[:] = [190, 28, 80]
                field += outer[..., None] * [45, 18, 25]
                field += halo[..., None] * [25, 0, 30]
                field += core[..., None] * [65, 70, 75]
                
            else:
                # FLOW: layered, molten amber color fields.
                # All temporal components are periodic in phase.

                # Enhanced horizontal movement with stronger, more diverse frequencies
                # Original: u = X + 0.14*sin(phase) + 0.045*sin(2*phase)
                # Improved: Increase amplitude and add multiple frequency components
                u = (
                    X
                    + 0.25 * np.sin(phase)
                    + 0.08 * np.sin(2 * phase)
                    + 0.04 * np.sin(4 * phase)
                )
                v = (
                    Y
                    + 0.12 * np.cos(phase)
                    - 0.06 * np.sin(2 * phase)
                    + 0.03 * np.cos(3 * phase)
                )

                # Warp the field with broader, more overlapping waves
                # Create more irregular organic contours
                warp_x = (
                    u
                    + 0.18 * np.sin(2.5 * v + phase)
                    + 0.06 * np.sin(4.5 * v - 2 * phase)
                )
                warp_y = (
                    v
                    + 0.15 * np.sin(2.2 * u - phase)
                    + 0.05 * np.cos(3.8 * u + 2 * phase)
                )

                # Combine several spatial frequencies more aggressively
                # Enhanced mixing ratio for richer texture
                field_a = (
                    np.sin(3.0 * warp_x + 1.5 * np.sin(1.8 * warp_y))
                    + 0.65 * np.cos(3.2 * warp_y - 0.9 * warp_x)
                )

                field_b = (
                    np.sin(1.8 * warp_x - 1.2 * warp_y)
                    + 0.4 * np.cos(2.2 * warp_y + 0.8 * warp_x)
                )

                # More aggressive field mixing (0.6 vs 0.45)
                field = field_a + 0.6 * field_b

                # Enhanced smooth masks with broader color regions
                # Avoid hard thresholds, which look artificial
                mask = np.clip(
                    (field + 0.25) / 1.0, 0.0, 1.0
                )
                mask = mask * mask * (3.0 - 2.0 * mask)

                deep_mask = np.clip(
                    (field - 0.4) / 0.8, 0.0, 1.0
                )
                deep_mask = deep_mask * deep_mask * (
                    3.0 - 2.0 * deep_mask
                )

                # Enhanced edge detection with broader boundaries
                # Gives appearance of glowing molten light within darker channels
                edge = np.exp(
                    -((field - 0.5) / 0.18) ** 2
                )

                # Deeper midnight background
                rgb = np.empty(
                    (height, width, 3), dtype=np.float32
                )
                rgb[:] = [8.0, 5.0, 20.0]

                # More dramatic amber/orange masses
                rgb += mask[..., None] * np.array(
                    [220.0, 60.0, 15.0], dtype=np.float32
                )

                # Deeper red-orange variation inside the masses
                rgb += deep_mask[..., None] * np.array(
                    [65.0, 25.0, 10.0], dtype=np.float32
                )

                # Restrained golden-orange edge illumination with warmer tones
                rgb += edge[..., None] * np.array(
                    [60.0, 40.0, 20.0], dtype=np.float32
                )

                # Enhanced atmospheric glow with stronger movement
                glow_x = X - 0.12 * np.sin(phase)
                glow_y = Y + 0.08 * np.cos(phase)

                glow = np.exp(
                    -(
                        (glow_x / 0.95) ** 2
                        + (glow_y / 0.70) ** 2
                    )
                )

                rgb += glow[..., None] * np.array(
                    [20.0, 10.0, 5.0], dtype=np.float32
                )

                field = rgb


            # Subtle vignette for a more cinematic composition.
            field *= vignette[..., None]

            # Small, slow overall brightness pulse.
            field *= 0.97 + 0.03 * breathing2

            frame = np.clip(field, 0, 255).astype(np.uint8)
            proc.stdin.write(frame.tobytes())

            if (i + 1) % fps == 0:
                print(f"\rRendered {i + 1}/{frames} frames", end="")

    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()

    if proc.wait() != 0:
        raise RuntimeError("FFmpeg failed. Check its error output.")

    print(f"\nSaved {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--style",
        choices=["aura", "flow", "tunnel"],
        default="tunnel",
    )
    parser.add_argument("--size", choices=["720p", "1080p"], default="720p")
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--output", default="previews/tunnel_v2.mp4")
    args = parser.parse_args()

    width, height = (
        (1280, 720) if args.size == "720p"
        else (1920, 1080)
    )

    render(
        args.style, width, height,
        args.fps, args.seconds, args.output
    )
