
import argparse
from pathlib import Path

import numpy as np
from PIL import Image


WIDTH = 1280
HEIGHT = 720
FPS = 24
DURATION = 10

PALETTES = {
    "aura": [
        (225, 48, 117),
        (203, 8, 52),
        (247, 104, 154),
        (110, 0, 76),
    ],
    "flow": [
        (255, 104, 22),
        (221, 48, 13),
        (8, 5, 25),
        (255, 160, 50),
    ],
    "tunnel": [
        (255, 65, 0),
        (255, 139, 0),
        (255, 205, 12),
        (184, 34, 0),
    ],
}


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


def mix_colors(colors, weights):
    result = np.zeros((*weights.shape[:2], 3), dtype=np.float32)
    for color, weight in zip(colors, weights.transpose(2, 0, 1)):
        result += weight[..., None] * np.asarray(
            color, dtype=np.float32
        )
    return result


def generate_frame(style, phase, x, y, grain):
    # phase runs through one complete cycle, so motion
    # repeats naturally at the loop boundary.
    if style == "tunnel":
        radius = np.sqrt(x * x + (y * 1.05) ** 2)

        rings = 0.5 + 0.5 * np.cos(
            2 * np.pi * (radius * 5.5 - 0.35 * np.sin(phase))
        )

        glow = np.exp(-radius * 5.5)
        halo = np.exp(-((radius - 0.38) / 0.12) ** 2)

        base = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
        base += np.array([225, 39, 0]) * (
            0.48 + 0.26 * rings
        )[..., None]
        base += np.array([255, 155, 0]) * (
            0.34 * halo
        )[..., None]
        base += np.array([255, 220, 40]) * (
            0.40 * glow
        )[..., None]

    elif style == "aura":
        cx = 0.09 * np.sin(phase)
        cy = 0.06 * np.cos(phase)
        radius = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

        center = np.exp(-(radius / 0.22) ** 2)
        halo = np.exp(-((radius - 0.36) / 0.19) ** 2)
        outer = np.exp(-((radius - 0.64) / 0.35) ** 2)

        base = (
            np.array([218, 38, 93])[None, None, :]
            * (0.45 + 0.28 * outer)[..., None]
        )
        base += np.array([225, 5, 52]) * (
            0.48 * halo
        )[..., None]
        base += np.array([255, 130, 170]) * (
            0.65 * center
        )[..., None]

    else:  # flowing organic color fields
        wave1 = np.sin(
            2 * np.pi * (x * 0.65 + 0.18 * np.sin(phase))
            + 2.2 * np.sin(y * 3.2)
        )
        wave2 = np.cos(
            2 * np.pi * (y * 0.8 - 0.14 * np.cos(phase))
            + 1.6 * np.sin(x * 2.5)
        )

        field = 0.5 + 0.25 * wave1 + 0.25 * wave2
        orange = smoothstep(0.05, 0.75, field)

        base = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
        base += np.array([7, 5, 22])
        base += orange[..., None] * np.array([247, 79, 16])

        highlight = np.clip((field - 0.65) / 0.35, 0, 1)
        base += highlight[..., None] * np.array([45, 55, 18])

    # A fixed grain pattern avoids flickering noise.
    base += grain[..., None] * 3.0

    return Image.fromarray(
        np.clip(base, 0, 255).astype(np.uint8), "RGB"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--style",
        choices=["aura", "flow", "tunnel"],
        default="tunnel",
    )
    parser.add_argument(
        "--output",
        default="loops",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames_dir = Path("previews") / f"{args.style}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Coordinates centered at zero.
    xx = (np.arange(WIDTH, dtype=np.float32) / WIDTH - 0.5) * 2
    yy = (np.arange(HEIGHT, dtype=np.float32) / HEIGHT - 0.5) * 2
    x, y = np.meshgrid(xx, yy)

    rng = np.random.default_rng(42)
    grain = rng.normal(0, 1, (HEIGHT, WIDTH)).astype(np.float32)

    total_frames = FPS * DURATION

    print(f"Generating {args.style}: {total_frames} frames")

    for i in range(total_frames):
        phase = 2 * np.pi * i / total_frames

        frame = generate_frame(
            args.style, phase, x, y, grain
        )

        frame.save(frames_dir / f"frame_{i:05d}.png")

        if (i + 1) % 24 == 0:
            print(f"Rendered {i + 1}/{total_frames}")

    output_file = output_dir / f"{args.style}_loop.mp4"

    import subprocess

    command = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_file),
    ]

    subprocess.run(command, check=True)
    print(f"Created: {output_file}")


if __name__ == "__main__":
    main()
