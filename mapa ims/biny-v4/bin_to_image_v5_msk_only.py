#!/usr/bin/env python3
"""
VIZUALIZACE V5 BIN - POUZE MSK REGION
====================================

Čte V5 formát (compact + row ranges) a kreslí jen MSK
"""

import struct
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from mpl_toolkits.axes_grid1 import make_axes_locatable

# MSK BOUNDS
MSK_NORTH = 50.327
MSK_SOUTH = 49.39
MSK_EAST = 18.86
MSK_WEST = 17.146


def load_bin_v5(bin_file='terrain.bin'):
    """Čti V5 formát"""
    print(f"🔍 Čtení {bin_file}...")
    
    with open(bin_file, 'rb') as f:
        # Čti header
        width = struct.unpack('I', f.read(4))[0]
        height = struct.unpack('I', f.read(4))[0]
        num_valid_rows = struct.unpack('I', f.read(4))[0]
        
        transform = []
        for _ in range(6):
            transform.append(struct.unpack('d', f.read(8))[0])
        
        print(f" ✓ Header:")
        print(f"   Dimensions: {width}×{height}")
        print(f"   Valid rows: {num_valid_rows}")
        print(f"   Transform: {transform[:3]}")
        
        # Čti row ranges
        row_ranges = []
        for _ in range(num_valid_rows):
            row_id = struct.unpack('I', f.read(4))[0]
            col_start = struct.unpack('I', f.read(4))[0]
            col_end = struct.unpack('I', f.read(4))[0]
            row_ranges.append((row_id, col_start, col_end))
        
        print(f" ✓ Row ranges: {len(row_ranges)}")
        
        # Inicializuj 2D pole
        heights = np.zeros((height, width), dtype=np.uint16)
        pollution = np.zeros((height, width), dtype=np.float32)
        
        # Čti data
        print(f" 📊 Čtení dat...")
        for row_id, col_start, col_end in row_ranges:
            for col in range(col_start, col_end):
                h = struct.unpack('H', f.read(2))[0]
                p = struct.unpack('f', f.read(4))[0]
                
                heights[row_id, col] = h
                pollution[row_id, col] = p
        
        print(f" ✓ Načteno: {np.count_nonzero(heights)} buněk s daty")
        
        return heights, pollution, transform, (width, height)


def gps_to_pixel(lat, lon, transform, width, height):
    """Konvertuj GPS → pixel"""
    from pyproj import Transformer
    
    try:
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32633", always_xy=True)
        x_utm, y_utm = transformer.transform(lon, lat)
        
        a, b, c, d, e, f = transform
        
        px = (x_utm - c) / a
        py = (y_utm - f) / d
        
        return int(px), int(py)
    except:
        return None, None


def extract_msk_region(heights, pollution, transform, dims):
    """Extrahuj MSK region"""
    print(f"\n🔍 Extrakce MSK regionu...")
    
    width, height = dims
    
    # GPS → pixel conversion
    px_west, _ = gps_to_pixel(MSK_SOUTH, MSK_WEST, transform, width, height)
    px_east, _ = gps_to_pixel(MSK_SOUTH, MSK_EAST, transform, width, height)
    _, py_north = gps_to_pixel(MSK_NORTH, MSK_WEST, transform, width, height)
    _, py_south = gps_to_pixel(MSK_SOUTH, MSK_WEST, transform, width, height)
    
    px_min = min(px_west, px_east)
    px_max = max(px_west, px_east)
    py_min = min(py_north, py_south)
    py_max = max(py_north, py_south)
    
    # Bounds check
    px_min = max(0, px_min)
    px_max = min(width, px_max)
    py_min = max(0, py_min)
    py_max = min(height, py_max)
    
    print(f" GPS bounds: N={MSK_NORTH}, S={MSK_SOUTH}, E={MSK_EAST}, W={MSK_WEST}")
    print(f" Pixel bounds: x=[{px_min}, {px_max}], y=[{py_min}, {py_max}]")
    
    # Extrahuj
    heights_msk = heights[py_min:py_max, px_min:px_max]
    pollution_msk = pollution[py_min:py_max, px_min:px_max]
    
    print(f" ✓ MSK region: {heights_msk.shape}")
    print(f" ✓ Bunky s daty: {np.count_nonzero(heights_msk)}")
    
    return heights_msk, pollution_msk


def visualize_msk(heights_msk, pollution_msk):
    """Vykresli MSK ONLY"""
    print(f"\n📊 Vizualizace MSK...")
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    fig.suptitle('Nadmořské Výšky a Znečištění - MSK Region ONLY', fontsize=16, fontweight='bold')
    
    # Mapa 1: Výšky
    ax = axes[0]
    im1 = ax.imshow(heights_msk, cmap='terrain', aspect='auto', origin='upper')
    ax.set_title('Nadmořské Výšky [m]', fontsize=12, fontweight='bold')
    ax.set_xlabel('Longitude [pixel]')
    ax.set_ylabel('Latitude [pixel]')
    
    divider1 = make_axes_locatable(ax)
    cax1 = divider1.append_axes("right", size="5%", pad=0.05)
    cbar1 = plt.colorbar(im1, cax=cax1)
    cbar1.set_label('[m]', rotation=270, labelpad=15)
    
    # Mapa 2: Znečištění (log scale)
    ax = axes[1]
    
    pollution_msk_nonzero = pollution_msk.copy()
    pollution_msk_nonzero[pollution_msk_nonzero == 0] = 1e-10
    
    im2 = ax.imshow(pollution_msk_nonzero, cmap='RdYlGn_r', aspect='auto', origin='upper',
                    norm=LogNorm(vmin=1e-10, vmax=pollution_msk.max() if pollution_msk.max() > 0 else 1))
    ax.set_title('Znečištění (log scale)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Longitude [pixel]')
    ax.set_ylabel('Latitude [pixel]')
    
    divider2 = make_axes_locatable(ax)
    cax2 = divider2.append_axes("right", size="5%", pad=0.05)
    cbar2 = plt.colorbar(im2, cax=cax2)
    cbar2.set_label('[log scale]', rotation=270, labelpad=15)
    
    plt.tight_layout()
    
    output_file = 'msk_region_v5.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f" ✓ Uloženo: {output_file}")
    
    plt.close()


def main():
    print("\n" + "="*70)
    print("VIZUALIZACE V5 BIN - POUZE MSK REGION")
    print("="*70)
    
    heights, pollution, transform, dims = load_bin_v5()
    heights_msk, pollution_msk = extract_msk_region(heights, pollution, transform, dims)
    visualize_msk(heights_msk, pollution_msk)
    
    print("\n" + "="*70)
    print("✓ HOTOVO - OBRÁZKY JEN PRO MSK!")
    print("="*70)
    print("\nVýstup:")
    print(" ✓ msk_region_v5.png - Výšky + Znečištění (MSK pouze)")
    print("\n")


if __name__ == '__main__':
    main()
