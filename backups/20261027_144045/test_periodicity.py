#!/usr/bin/env python3
"""Verify Flow periodicity in time and across the full horizontal span."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_loop_v5 import flow_frame, flow_params  # noqa: E402
from scripts.generate_loop_v5 import silk_frame, silk_params  # noqa: E402


def main():
    params = flow_params(42)

    # Endpoint-inclusive grid: x = -1 and x = +1 must agree exactly.
    x = np.linspace(-1.0, 1.0, 257, dtype=np.float32)
    y = np.linspace(-0.5625, 0.5625, 129, dtype=np.float32)
    X, Y = np.meshgrid(x, y)
    YN = Y / 0.5625

    print("Horizontal periodicity (left vs right edge):")
    worst = 0.0
    for phase in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
        frame = flow_frame(X, Y, YN, phase, params)
        delta = float(np.abs(frame[:, 0] - frame[:, -1]).max())
        worst = max(worst, delta)
        print(f"  phase={phase:5.2f}  max|edge diff|={delta:.6f}")

    print("Temporal periodicity (phase 0 vs 2*pi):")
    start = flow_frame(X, Y, YN, 0.0, params)
    end = flow_frame(X, Y, YN, 2.0 * np.pi, params)
    temporal = float(np.abs(start - end).max())
    print(f"  max|frame(0) - frame(2*pi)|={temporal:.6f}")

    print("Silk horizontal periodicity (left vs right edge):")
    silk_p = silk_params(42)
    silk_worst = 0.0
    for phase in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
        frame = silk_frame(X, Y, YN, phase, silk_p)
        delta = float(np.abs(frame[:, 0] - frame[:, -1]).max())
        silk_worst = max(silk_worst, delta)
        print(f"  phase={phase:5.2f}  max|edge diff|={delta:.6f}")

    print("Silk temporal periodicity (phase 0 vs 2*pi):")
    silk_start = silk_frame(X, Y, YN, 0.0, silk_p)
    silk_end = silk_frame(X, Y, YN, 2.0 * np.pi, silk_p)
    silk_temporal = float(np.abs(silk_start - silk_end).max())
    print(f"  max|frame(0) - frame(2*pi)|={silk_temporal:.6f}")

    if worst > 1e-2 or temporal > 1e-2 or silk_worst > 1e-2 or silk_temporal > 1e-2:
        raise SystemExit(
            f"FAIL: flow_spatial={worst:.6f}, flow_temporal={temporal:.6f}, silk_spatial={silk_worst:.6f}, silk_temporal={silk_temporal:.6f}"
        )
    print("PASS: Flow and Silk are periodic in time and horizontal space.")


if __name__ == "__main__":
    main()
