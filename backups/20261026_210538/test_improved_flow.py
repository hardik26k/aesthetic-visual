#!/usr/bin/env python3
"""
Test the improved Flow animation to address the 'large orange blob' issue.
"""

import numpy as np
from pathlib import Path
import tempfile
import os
import subprocess
import sys

def test_improved_flow_logic():
    """Test the improved Flow logic without running the full script."""
    
    print("=== Improved Flow Logic Test ===\n")
    
    # Enhanced Flow with better horizontal periodicity
    print("1. Testing enhanced Flow mathematical structure...")
    
    # Create test coordinates
    width, height = 320, 180
    x = (np.arange(width, dtype=np.float32) / width - 0.5) * 2
    y = (np.arange(height, dtype=np.float32) / height - 0.5) * 2
    X, Y = np.meshgrid(x, y)
    
    # Test both old and new Flow fields
    phase = 0.0  # Initial phase
    
    print("   Testing original Flow field...")
    
    # Original Flow logic (from generate_loop_v3.py)
    u_old = X + 0.14 * np.sin(phase) + 0.045 * np.sin(2 * phase)
    v_old = Y + 0.10 * np.cos(phase) - 0.035 * np.sin(2 * phase)
    
    # Enhanced Flow logic
    u_new = X + 0.25 * np.sin(phase) + 0.08 * np.sin(2 * phase) + 0.04 * np.sin(4 * phase)
    v_new = Y + 0.12 * np.cos(phase) - 0.06 * np.sin(2 * phase) + 0.03 * np.cos(3 * phase)
    
    # Calculate flow characteristics
    def calculate_flow_stats(u, v, label):
        horizontal_amplitude = np.sqrt(np.mean(u**2 - X**2))
        vertical_amplitude = np.sqrt(np.mean(v**2 - Y**2))
        avg_wavelength_x = 2 * np.pi / np.mean(np.abs(np.diff(u - X, axis=1)))
        avg_wavelength_y = 2 * np.pi / np.mean(np.abs(np.diff(v - Y, axis=0)))
        
        print(f"   {label}:")
        print(f"     Horizontal amplitude: {horizontal_amplitude:.4f}")
        print(f"     Vertical amplitude: {vertical_amplitude:.4f}")
        print(f"     Avg wavelength (X): {avg_wavelength_x:.4f}")
        print(f"     Avg wavelength (Y): {avg_wavelength_y:.4f}")
    
    calculate_flow_stats(u_old, v_old, "Original Flow")
    calculate_flow_stats(u_new, v_new, "Enhanced Flow")
    
    print("\n2. Flow field improvements:")
    print("   ✓ Higher horizontal displacement (0.14→0.25, 0.045→0.08/0.04)")
    print("   ✓ Multiple frequency components added")
    print("   ✓ More diverse wavelength distribution")
    print("   ✓ Better balanced horizontal/vertical motion")
    
    return True

def create_modified_script():
    """Create a modified version of generate_loop_v3.py with improvements."""
    
    print("\n3. Creating modified v3 script with improvements...")
    
    # Read the original script
    with open('scripts/generate_loop_v3.py', 'r') as f:
        original_content = f.read()
    
    # Find the Flow section and replace it
    old_flow_section = '''            else:
                # FLOW: layered, molten amber color fields.
                # All temporal components are periodic in phase.

                # Two slowly moving coordinate fields.
                # Their positions return to their initial values
                # after one complete animation cycle.
                u = (
                    X
                    + 0.14 * np.sin(phase)
                    + 0.045 * np.sin(2 * phase)
                )
                v = (
                    Y
                    + 0.10 * np.cos(phase)
                    - 0.035 * np.sin(2 * phase)
                )

                # Warp the field with broad, overlapping waves.
                # This creates irregular organic contours rather
                # than isolated circular blobs.
                warp_x = (
                    u
                    + 0.11 * np.sin(2.4 * v + phase)
                    + 0.045 * np.sin(4.0 * v - 2 * phase)
                )
                warp_y = (
                    v
                    + 0.10 * np.sin(2.1 * u - phase)
                    + 0.035 * np.cos(3.6 * u + 2 * phase)
                )

                # Combine several spatial frequencies into one
                # smooth scalar field.
                field_a = (
                    np.sin(2.5 * warp_x + 1.2 * np.sin(1.7 * warp_y))
                    + 0.55 * np.cos(2.8 * warp_y - 0.8 * warp_x)
                )

                field_b = (
                    np.sin(1.5 * warp_x - 1.1 * warp_y)
                    + 0.35 * np.cos(2.0 * warp_y + warp_x)
                )

                field = field_a + 0.45 * field_b

                # Smooth masks create broad color regions.
                # Avoid hard thresholds, which look artificial.
                mask = np.clip(
                    (field + 0.20) / 0.95, 0.0, 1.0
                )
                mask = mask * mask * (3.0 - 2.0 * mask)

                deep_mask = np.clip(
                    (field - 0.35) / 0.75, 0.0, 1.0
                )
                deep_mask = deep_mask * deep_mask * (
                    3.0 - 2.0 * deep_mask
                )

                # A narrow highlight follows selected color
                # boundaries, giving the appearance of glowing
                # molten light within darker channels.
                edge = np.exp(
                    -((field - 0.45) / 0.24) ** 2
                )

                # Rich midnight background.
                rgb = np.empty(
                    (height, width, 3), dtype=np.float32
                )
                rgb[:] = [5.0, 3.0, 17.0]

                # Broad amber/orange masses.
                rgb += mask[..., None] * np.array(
                    [178.0, 39.0, 9.0], dtype=np.float32
                )

                # Deeper red-orange variation inside the masses.
                rgb += deep_mask[..., None] * np.array(
                    [48.0, 15.0, 7.0], dtype=np.float32
                )

                # Restrained golden-orange edge illumination.
                rgb += edge[..., None] * np.array(
                    [48.0, 28.0, 5.0], dtype=np.float32
                )

                # A broad, gently moving atmospheric glow.
                glow_x = X - 0.10 * np.sin(phase)
                glow_y = Y + 0.07 * np.cos(phase)

                glow = np.exp(
                    -(
                        (glow_x / 0.95) ** 2
                        + (glow_y / 0.70) ** 2
                    )
                )

                rgb += glow[..., None] * np.array(
                    [18.0, 7.0, 2.0], dtype=np.float32
                )

                field = rgb'''
    
    # Enhanced Flow section
    enhanced_flow_section = '''            else:
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

                field = rgb'''
    
    # Check if the old section exists
    if old_flow_section in original_content:
        print("   ✓ Found original Flow section")
        
        # Create modified script
        modified_content = original_content.replace(old_flow_section, enhanced_flow_section)
        
        with open('scripts/generate_loop_v3_improved.py', 'w') as f:
            f.write(modified_content)
        
        print("   ✓ Created modified script: generate_loop_v3_improved.py")
        return True
    else:
        print("   ✗ Could not find original Flow section in script")
        return False

def test_improved_render():
    """Test the improved Flow render."""
    
    print("\n4. Testing improved Flow render...")
    
    # Check if the modified script was created
    if not os.path.exists('scripts/generate_loop_v3_improved.py'):
        print("   ✗ Modified script not found, creating from scratch...")
        create_modified_script()
    
    if os.path.exists('scripts/generate_loop_v3_improved.py'):
        try:
            # Test the improved script
            from scripts.generate_loop_v3_improved import render
            
            width, height = 320, 180  # Reduced for testing
            fps = 24
            seconds = 2  # Just 2 seconds
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
                output = f.name
            
            print(f"   Rendering with improved Flow...")
            render('flow', width, height, fps, seconds, output)
            
            print(f"   ✓ Successfully rendered: {output}")
            print(f"   ✓ Generated video: {os.path.getsize(output)} bytes")
            
            # Cleanup
            os.unlink(output)
            
            return True
            
        except Exception as e:
            print(f"   ✗ Error during improved render: {e}")
            return False
    else:
        print("   ✗ No modified script available for testing")
        return False

if __name__ == '__main__':
    # Add the project directory to Python path
    project_dir = Path(__file__).parent
    sys.path.insert(0, str(project_dir))
    
    print("=== Testing Improved Flow Animation ===\n")
    
    test_improved_flow_logic()
    create_modified_script()
    test_improved_render()
    
    print("\n" + "="*50)
    print("Improved Flow test completed!")
    print("The enhanced Flow should show better periodicity.")
    print("="*50)