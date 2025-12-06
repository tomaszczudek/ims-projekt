#!/usr/bin/env python3
"""
bin_to_image V5 - Vizualizace BIN → PNG
=======================================
Čte V5 BIN a vytváří mapy (výšky + znečištění)
"""

import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from pathlib import Path
import sys

def read_v5_binary(bin_path):
    """Čti V5 binární soubor"""
    with open(bin_path, 'rb') as f:
        # Header (60B)
        width = struct.unpack('I', f.read(4))[0]
        height = struct.unpack('I', f.read(4))[0]
        num_valid_rows = struct.unpack('I', f.read(4))[0]
        
        transform = []
        for _ in range(6):
            transform.append(struct.unpack('d', f.read(8))[0])
        
        print(f" 🔍 Čtení {Path(bin_path).name}...")
        print(f" ✓ Metadata: {width}×{height}")
        print(f" ✓ Valid rows: {num_valid_rows}")
        
        # Row ranges
        row_ranges = []
        for _ in range(num_valid_rows):
            row_id = struct.unpack('I', f.read(4))[0]
            col_start = struct.unpack('I', f.read(4))[0]
            col_end = struct.unpack('I', f.read(4))[0]
            row_ranges.append((row_id, col_start, col_end))
        
        # Raw data
        heights = np.zeros((height, width), dtype=np.uint16)
        pollution = np.zeros((height, width), dtype=np.float32)
        
        for row_id, col_start, col_end in row_ranges:
            for col in range(col_start, col_end):
                h = struct.unpack('H', f.read(2))[0]
                p = struct.unpack('f', f.read(4))[0]
                heights[row_id, col] = h
                pollution[row_id, col] = p
        
        print(f" ✓ Načteno: {num_valid_rows} řádků\n")
        
        return heights, pollution, (width, height)

def visualize_terrain(heights, pollution, output_path, title_suffix=""):
    """Visualizuj terén (výšky + znečištění)"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    # Levá: Výšky
    im1 = ax1.imshow(heights, cmap='terrain', interpolation='bilinear')
    ax1.set_title(f'Nadmořské Výšky{title_suffix}', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Sloupec (pixel)')
    ax1.set_ylabel('Řádek (pixel)')
    cbar1 = plt.colorbar(im1, ax=ax1)
    cbar1.set_label('Výška (m)', fontsize=11)
    
    # Pravá: Znečištění (log scale)
    pollution_safe = np.where(pollution > 0, pollution, 1e-6)
    im2 = ax2.imshow(pollution_safe, cmap='RdYlGn_r', norm=LogNorm(), interpolation='bilinear')
    ax2.set_title(f'Znečištění - Log Scale{title_suffix}', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Sloupec (pixel)')
    ax2.set_ylabel('Řádek (pixel)')
    cbar2 = plt.colorbar(im2, ax=ax2)
    cbar2.set_label('Znečištění (log)', fontsize=11)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f" ✓ Uloženo: {output_path}\n")
    plt.close()

def main():
    print("\n" + "=" * 70)
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 12 + "VIZUALIZACE V5 - BIN → PNG" + " " * 30 + "║")
    print("╚" + "=" * 68 + "╝")
    print("=" * 70 + "\n")
    
    # Urči který soubor čtení
    if len(sys.argv) > 1:
        bin_path = Path(sys.argv[1])
    else:
        bin_path = Path("terrain.bin")
    
    output_path = Path(str(bin_path).replace(".bin", "") + "_visualization.png")
    
    if not bin_path.exists():
        print(f" ✗ Soubor neexistuje: {bin_path}")
        return 1
    
    # Čti V5
    heights, pollution, grid_shape = read_v5_binary(str(bin_path))
    
    # Visualizuj
    print(f" 📊 Vizualizace...")
    title_suffix = " (Modified)" if "modified" in str(bin_path).lower() else ""
    visualize_terrain(heights, pollution, str(output_path), title_suffix)
    
    print("=" * 70)
    print(" ✓ HOTOVO!")
    print("=" * 70 + "\n")
    print("Výstup:")
    print(f" ✓ {output_path}\n")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
