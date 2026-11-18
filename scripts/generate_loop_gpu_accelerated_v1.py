#!/usr/bin/env python3
"""GPU-Accelerated Seamless Ambient Loop Renderer (PyTorch / CUDA) — v1.

Translates the Golden Ratio Silk caustic generator entirely onto PyTorch / CUDA
tensors for lightning-fast GPU-accelerated 1080p and 4K rendering.
"""

import argparse
import subprocess
from pathlib import Path

import torch

SIZES = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}

PHI = 1.61803398875


def make_grid_gpu(width, height, device):
    """Pixel-centre grid on GPU spanning one full period in x."""
    x = (torch.arange(width, dtype=torch.float32, device=device) / width - 0.5) * 2.0
    y = (torch.arange(height, dtype=torch.float32, device=device) / height - 0.5) * 2.0
    X, Y = torch.meshgrid(x, y, indexing="xy")
    Y = Y * (height / width)
    return X, Y


def smoothstep_gpu(edge0, edge1, x):
    t = torch.clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def silk_params_gpu(seed, device):
    rng = torch.Generator(device=device)
    rng.manual_seed(seed)
    return {
        "phase0": float(torch.rand(1, generator=rng, device=device) * 2.0 * torch.pi),
        "tint": 0.92 + 0.16 * torch.rand(3, generator=rng, device=device),
        "warp_amp": float(0.40 + 0.25 * torch.rand(1, generator=rng, device=device)),
        "drift_amp": float(0.12 + 0.16 * torch.rand(1, generator=rng, device=device)),
    }


def silk_frame_gpu(X, Y, phase, params, device):
    p0 = params["phase0"]
    warp = params["warp_amp"]
    y = Y[:, 0]  # 1D tensor along rows

    u1 = torch.pi * X
    u2 = 2.0 * torch.pi * X

    t_y1 = (
        0.75 * y
        + warp * torch.sin(2.0 * PHI * y - phase + p0)
        + 0.30 * torch.sin(3.0 * PHI * y - 2.0 * phase)
    )
    t_y2 = -0.70 * y + 0.38 * torch.cos(2.0 * PHI * y + phase + p0)

    theta1 = u1 + t_y1.unsqueeze(1)
    theta2 = u2 + t_y2.unsqueeze(1)

    theta3 = (
        4.0 * torch.pi * X
        + 1.35 * y.unsqueeze(1)
        + 0.50 * torch.sin(1.5 * torch.sin(theta1) + PHI * y.unsqueeze(1) - phase)
        + 0.28 * torch.sin(0.85 * torch.sin(theta2) + 2.0 * PHI * y.unsqueeze(1) + 2.0 * phase)
    )

    theta4 = (
        6.0 * torch.pi * X
        - 1.10 * y.unsqueeze(1)
        + 0.35 * torch.sin(1.2 * torch.sin(theta1) + phase)
    )

    field = (
        0.80 * torch.sin(theta1)
        + 0.45 * torch.sin(2.0 * theta1 + 0.4 * torch.sin(2.0 * PHI * y + phase).unsqueeze(1))
        + 0.35 * torch.cos(theta2 + phase)
        + 0.40 * torch.sin(theta3 - phase)
        + 0.20 * torch.sin(2.0 * theta3 + 2.0 * phase)
        + 0.15 * torch.cos(theta4 + phase)
    )

    n = torch.tanh(0.70 * field - 0.05)

    ribs1 = torch.sin(20.0 * torch.pi * X + 15.0 * y.unsqueeze(1) + 7.0 * torch.sin(theta1) - 2.0 * phase)
    ribs2 = torch.cos(34.0 * torch.pi * X - 22.0 * y.unsqueeze(1) + 5.0 * torch.cos(theta2) + phase)

    rib_mask1 = smoothstep_gpu(-0.3, 0.5, n) * (0.5 + 0.5 * ribs1) ** 1.6
    rib_mask2 = smoothstep_gpu(-0.1, 0.7, n) * (0.5 + 0.5 * ribs2) ** 2.0

    dark_channels = smoothstep_gpu(0.05, 0.70, -n)
    teal_depth = smoothstep_gpu(-0.45, 0.20, n)
    cyan_body = smoothstep_gpu(-0.10, 0.55, n)
    cyan_crest = smoothstep_gpu(0.30, 0.85, n)
    white_hot_core = smoothstep_gpu(0.70, 0.98, n)

    edge_gradient = torch.exp(-((n - 0.15) / 0.18) ** 2)
    gold_rim = edge_gradient * (0.55 + 0.45 * torch.cos(theta3 - phase))
    warm_amber_accent = torch.exp(-((n - 0.40) / 0.15) ** 2) * (0.6 + 0.4 * torch.sin(theta1 + 1.2 * y.unsqueeze(1)))

    rgb = torch.zeros((*n.shape, 3), dtype=torch.float32, device=device)
    rgb[:] = torch.tensor([2.0, 10.0, 24.0], device=device)
    rgb += dark_channels.unsqueeze(-1) * torch.tensor([4.0, 22.0, 42.0], device=device)
    rgb += teal_depth.unsqueeze(-1) * torch.tensor([0.0, 85.0, 125.0], device=device)
    rgb += cyan_body.unsqueeze(-1) * torch.tensor([0.0, 175.0, 195.0], device=device) * params["tint"]
    rgb += cyan_crest.unsqueeze(-1) * torch.tensor([0.0, 230.0, 230.0], device=device)
    rgb += white_hot_core.unsqueeze(-1) * torch.tensor([160.0, 255.0, 245.0], device=device)
    rgb += gold_rim.unsqueeze(-1) * torch.tensor([225.0, 160.0, 50.0], device=device)
    rgb += warm_amber_accent.unsqueeze(-1) * torch.tensor([190.0, 120.0, 35.0], device=device)
    rgb += rib_mask1.unsqueeze(-1) * torch.tensor([30.0, 160.0, 180.0], device=device)
    rgb += rib_mask2.unsqueeze(-1) * torch.tensor([40.0, 130.0, 150.0], device=device)

    return rgb


def encode_stream_gpu(width, height, fps, seconds, output, seed, crf, preset):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Rendering on device: {device}")

    frames = fps * seconds
    X, Y = make_grid_gpu(width, height, device)
    params = silk_params_gpu(seed, device)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-i", "-",
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
        with torch.no_grad():
            for i in range(frames):
                phase = 2.0 * torch.pi * i / frames
                field = silk_frame_gpu(X, Y, phase, params, device)
                field *= (0.97 + 0.03 * torch.cos(torch.tensor(phase, device=device)))
                frame = torch.clamp(field, 0.0, 255.0).to(torch.uint8)
                # Transfer from GPU to CPU memory and write directly to FFmpeg pipe
                proc.stdin.write(frame.cpu().numpy().tobytes())

                if (i + 1) % fps == 0:
                    print(f"\r[GPU Render] Rendered {i + 1}/{frames} frames", end="", flush=True)
    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()

    if proc.wait() != 0:
        raise RuntimeError("FFmpeg failed; see the error output above.")
    print(f"\nSaved {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=sorted(SIZES), default="1080p")
    parser.add_argument("--seconds", type=int, default=12)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument(
        "--output", default=None,
        help="output file; defaults to previews/silk_gpu_<size>_<seconds>s.mp4",
    )
    args = parser.parse_args()

    width, height = SIZES[args.size]
    output = Path(args.output) if args.output else Path(
        "previews", f"silk_gpu_{args.size}_{args.seconds}s.mp4"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"silk GPU {args.size} ({width}x{height}) {args.fps}fps {args.seconds}s seed={args.seed}")
    encode_stream_gpu(
        width, height, args.fps, args.seconds, output,
        args.seed, args.crf, args.preset
    )


if __name__ == "__main__":
    main()
