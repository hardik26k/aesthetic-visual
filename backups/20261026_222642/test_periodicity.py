#!/usr/bin/env python3
"""Verify Flow periodicity in time and across the full horizontal span."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_loop_v4 import flow_frame, flow_params  # noqa: E402


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

    if worst > 1e-2 or temporal > 1e-2:
        raise SystemExit(
            f"FAIL: spatial={worst:.6f}, temporal={temporal:.6f}"
        )
    print("PASS: Flow is periodic in time and horizontal space.")


if __name__ == "__main__":
    main()
