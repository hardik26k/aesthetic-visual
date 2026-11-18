# AGENTS.md: Aesthetic Channel Loops Repository

## Project Goals
- Generate original Aura, Flow, and Tunnel ambient animations
- Run on Linux with 4 GB RAM or less, without requiring a dedicated GPU
- Stream frames directly to FFmpeg wherever practical
- Support 720p previews and 1080p output, with 4K considered only after performance testing
- Generate seamless periodic loops and 2–3-hour MP4 videos
- Support silent and properly licensed audio versions
- Automate repeatable production without making every upload visually identical

## Overview
A Python repository for generating video loops (tunnel, aura, flow styles) using numpy and ffmpeg. Contains three script versions for creating animated visual content.

## Entry Points & Primary Scripts

### Main Scripts (Scripts/)
- **`generate_loop.py`** (v1): Simple approach - generates frames in previews/ then uses ffmpeg
- **`generate_loop_v2.py`** (v2): Optimized - uses ffmpeg with raw video input stream  
- **`generate_loop_v3.py`** (v3): Most complex - layered rendering pipeline with motion effects
- **`generate_loop_v3_improved.py`** (v3-improved): Enhanced Flow animation with better horizontal periodicity and richer color fields

**Script Selection Guidance:**
- Use **v3-improved** for Flow production - fixes the 'orange blob' issue
- Use **v3** for production Tunnel/Aura - latest, most flexible
- Use **v2** for simpler use case - faster build
- Use **v1** for understanding - clearest code structure

## Basic Commands

### Generate Improved Flow Loop (v3-improved)
```bash
python scripts/generate_loop_v3_improved.py --style flow --size 720p --seconds 10 --output previews/flow_improved.mp4
```

### Generate Tunnel Loop (v3 - default)
```bash
python scripts/generate_loop_v3.py --style tunnel
# Generates: previews/tunnel_v2.mp4
```

### Generate All Styles
```bash
python scripts/generate_loop_v3_improved.py --style flow
python scripts/generate_loop_v3.py --style aura
python scripts/generate_loop_v3.py --style tunnel
```

### Generate Full-Length Loops
```bash
# For full loops, use generate_loop.py which creates loops/ directory
python scripts/generate_loop.py --style tunnel
# Generates: loops/tunnel_loop.mp4
```

### Check Progress
- `ls previews/` - check generated frames for v2
- `ls loops/` - check completed loops for v1

## Key Directories

**Scripts/** - Python source for video generation
- v1: generate_loop.py (frame-based + ffmpeg)
- v2: generate_loop_v2.py (raw video + ffmpeg) 
- v3: generate_loop_v3.py (complex rendering pipeline)

**Previews/** - Generated preview videos (from v2/v3)
- `tunnel_v2.mp4`, `aura_v2.mp4`, `flow_v2.mp4`
- `*_cinematic.mp4` - cinematic mode variants

**Loops/** - Final full-length loops (from v1)
- `tunnel_loop.mp4`, `flow_loop.mp4`

**Audio/** - Audio source files
- `atlasaudio-ambient-lofi-576613.mp3`
- `*_license.txt` - Audio licensing

**Output/** - Additional output files
- `sunset_tunnel_audio.mp4`

**Presets/**, **Thumbnails/**, **Output/** - Generated assets

## Dependencies

**Python packages:** numpy, Pillow, imageio (for some scripts)
**System tools:** ffmpeg (required)

**Ensure ffmpeg is installed:**
```bash
# Ubuntu/Debian
 sudo apt-get install ffmpeg

# macOS  
brew install ffmpeg

# CentOS/RHEL
 sudo yum install ffmpeg
```

## Performance & Constraints

**Resource Constraints:**
- Linux target with 4 GB RAM or less
- No dedicated GPU required
- Stream frames to FFmpeg wherever practical to minimize RAM usage
- 720p previews, 1080p output only (4K for post-performance testing)

**Flow Animation Issue:**
- **Fixed** in `generate_loop_v3_improved.py`
- Increased horizontal movement amplitude and frequency diversity
- Enhanced spatial frequency mixing for continuous flowing fields
- Richer color palette and more pronounced edge detection

## Testing & Development

**Flow Periodicity Testing:**
```bash
# Create minimal Flow test script
cat > test_flow_periodicity.py << 'EOF'
import numpy as np
from scripts.generate_loop_v3 import render
import tempfile
import os

# Test single frame for periodicity
width, height = 320, 180
fps = 24
seconds = 1

with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
    output = f.name

render('flow', width, height, fps, seconds, output)
os.unlink(output)

print("Flow test completed - check visual output")
EOF
python test_flow_periodicity.py
```

**Improved Flow Testing:**
```bash
# Verify the fix for the 'orange blob' issue
python test_improved_flow.py
```

**Performance Testing (4GB RAM constraint):**
```bash
# Memory usage test for v3
ulimit -v 4194304  # 4GB virtual memory limit
python scripts/generate_loop_v3_improved.py --style flow --seconds 5
```

**FFmpeg Stream Testing:**
```bash
# Verify FFmpeg frame streaming capability
python scripts/generate_loop_v2.py --style flow --seconds 2 --output test_stream.mp4
```

**Progressive Testing:**
1. Start with v1 for basic functionality
2. Test v2 for memory efficiency
3. Validate v3-improved for final production quality
4. Monitor RAM usage throughout

## Architecture Notes

**Three Evolution Path:**
- v1 (generate_loop.py): Frame-by-frame approach, clear but inefficient
- v2 (generate_loop_v2.py): Direct video encoding, better performance  
- v3 (generate_loop_v3.py): Professional rendering with cinematic effects

**Visual Styles:**
- **tunnel**: Cinematic sunset tunnel with soft rings and portal effects
- **aura**: Multiple soft radial light sources, ethereal glow
- **flow**: Molten amber color fields with organic wave distortions

**Common Techniques:**
- Normalized coordinates (x, y from -1 to 1) for resolution independence
- Phasor-based animation (2πi frames/fps progression)
- Non-destructive layering with vignette effects
- High-quality encoding (CRF 18, libx264 ultrafast preset)

## Testing & Debugging

**Frame Generation Debugging:**
- Scripts print progress every N frames
- Generated frames show in previews/{style}_frames/
- Use `ffmpeg -i previews/frame_00000.png` to inspect individual frames

**Common Issues:**
- Missing ffmpeg: Scripts fail during video encoding
- Insufficient disk space: Frame files can be large
- RGB format: Ensure proper byte ordering (field tobytes())

**Performance Tips:**
- v3 scripts consume significant RAM due to per-frame numpy arrays
- v2 generates more compact previews than v1
- Monitor disk space during frame generation (10s of frames per style)

## Generated Assets

**File Organization:**
- Frames: `previews/{style}_frames/frame_XXXX.png`
- Previews: `previews/{style}_v2.mp4` or `{style}_cinematic.mp4`
- Full loops: `loops/{style}_loop.mp4` (v1 only)

**File Formats:**
- Images: PNG (24-bit RGB)
- Videos: MP4 (H.264, 24fps, CRF 18)
- Audio: MP3 (provided in audio/)

**Cache Behavior:**
- No build artifacts stored long-term
- Generated assets managed in output directories
- Scripts overwrite previous runs by default

## Script Differences (v1 vs v2 vs v3)

**v1 generate_loop.py:**
- Simple frame generation + ffmpeg concatenation
- Uses PIL for image creation
- Creates full 10-second loops (FPS × DURATION)
- Generates frames in preview directories

**v2 generate_loop_v2.py:**  
- Direct video encoding with ffmpeg stdin
- More memory-efficient (no frame files)
- Smaller output files (previews/ directory)
- Better for quick iterations

**v3 generate_loop_v3.py:**
- Complex rendering pipeline with multiple visual layers
- Cinematic effects and atmospheric elements
- Configurable sizes (720p/1080p), durations, FPS
- Advanced motion interpolation and distortion effects

## Monorepo Structure

This is a single-purpose repository focused exclusively on:
1. Video generation scripts
2. Generated video assets
3. Audio source files

No build system, tests, or application code. Each script is a standalone tool.

## Best Practices

**For Development:**
- Always test with v1 first (simplest) before v3 (complex)
- Check ffmpeg availability before running any script
- Monitor disk space - frame generation uses significant temp storage
- v3 scripts require more RAM than v1/v2

**For Production:**
- Use v3 for final output (most refined)
- v1 generates the definitive full loops (loops/ directory)
- v2 good for quick previews and validation
- Store generated assets in version control as needed

**Common Workflows:**
1. Development: v1 → v2 → v3
2. Quick test: v2 (small files, fast iteration)
3. Final delivery: v1 (full loops in loops/)
4. Preview generation: v2/v3 (previews/ directory)

## Maintenance

**Script Updates:**
- Update all three versions consistently if changing core rendering logic
- v3 is reference implementation; propagate changes to v1/v2
- Keep visual styles synchronized across versions

**Asset Regeneration:**
- Scripts overwrite existing files by default (ffmpeg -y flag)
- Generated frames and videos are temporary artifacts
- Clean previews/ and loops/ directories between generations

**Dependencies:**
- Add new visual styles to all three scripts consistently
- ffmpeg version compatibility affects encoding parameters
- numpy version may affect floating-point precision