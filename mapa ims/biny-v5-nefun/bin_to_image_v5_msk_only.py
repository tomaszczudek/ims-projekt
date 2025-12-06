#!/usr/bin/env python3
"""
Visualizace V5 - MSK Region Only
================================
Čte V5 binární soubor a kreslí mapy jen MSK regionu
"""

import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from pathlib import Path

# MSK Region bounds (pixel)
MSK_PIXEL_BOUNDS = {
    'row_min': 2500,
    'row_max': 3400,
    'col_min': 3200,
    'col_max': 4100
}

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
        
        print(f" 🔍 Čtení terrain.bin...")
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

def extract_msk_region(heights, pollution):
    """Extrahuj jen MSK region"""
    r_min = MSK_PIXEL_BOUNDS['row_min']
    r_max = MSK_PIXEL_BOUNDS['row_max']
    c_min = MSK_PIXEL_BOUNDS['col_min']
    c_max = MSK_PIXEL_BOUNDS['col_max']
    
    msk_heights = heights[r_min:r_max, c_min:c_max]
    msk_pollution = pollution[r_min:r_max, c_min:c_max]
    
    print(f" 🔍 Extrakce MSK regionu...")
    print(f" ✓ MSK region: {msk_heights.shape}")
    print(f" ✓ Bunky s daty: {np.count_nonzero(msk_heights):,}\n")
    
    return msk_heights, msk_pollution

def visualize_msk(heights, pollution, output_path):
    """Visualizuj MSK mapy"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    # Levá: Výšky
    im1 = ax1.imshow(heights, cmap='terrain', interpolation='bilinear')
    ax1.set_title('Nadmořské Výšky - MSK Region', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Sloupec (pixel)')
    ax1.set_ylabel('Řádek (pixel)')
    cbar1 = plt.colorbar(im1, ax=ax1)
    cbar1.set_label('Výška (m)', fontsize=11)
    
    # Pravá: Znečištění (log scale)
    pollution_safe = np.where(pollution > 0, pollution, 1e-6)
    im2 = ax2.imshow(pollution_safe, cmap='RdYlGn_r', norm=LogNorm(), interpolation='bilinear')
    ax2.set_title('Znečištění - MSK Region (log scale)', fontsize=14, fontweight='bold')
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
    print("║" + " " * 15 + "VISUALIZACE V5 - MSK REGION ONLY" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    print("=" * 70 + "\n")
    
    bin_path = Path("terrain.bin")
    output_path = Path("msk_region_v5.png")
    
    if not bin_path.exists():
        print(f" ✗ Soubor neexistuje: {bin_path}")
        return 1
    
    # Čti V5
    heights, pollution, grid_shape = read_v5_binary(str(bin_path))
    
    # Extrahuj MSK
    msk_heights, msk_pollution = extract_msk_region(heights, pollution)
    
    # Visualizuj
    print(f" 📊 Vizualizace MSK...")
    visualize_msk(msk_heights, msk_pollution, str(output_path))
    
    print("=" * 70)
    print(" ✓ HOTOVO - OBRÁZKY JEN PRO MSK!")
    print("=" * 70 + "\n")
    print("Výstup:")
    print(f" ✓ {output_path} - Výšky + Znečištění (MSK pouze)\n")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
