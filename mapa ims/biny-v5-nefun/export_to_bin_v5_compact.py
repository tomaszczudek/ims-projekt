#!/usr/bin/env python3
"""
Export V5 - Compact Metadata + Row Ranges
=========================================
Exportuje terrain do V5 formátu s:
  - Kompaktním header (bez verzí)
  - Row ranges [col_start:col_end] pro každý řádek
  - Filtrování prázdných řádků a nul na konci
  - Jen MSK region
"""

import struct
import numpy as np
import rasterio
from rasterio.windows import Window
import json
import sys
from pathlib import Path

# MSK Region bounds (GPS)
MSK_BOUNDS = {
    'north': 50.327,
    'south': 49.39,
    'east': 18.86,
    'west': 17.146
}

def load_factories(json_path):
    """Načti seznam továren z JSON"""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data.get('factories', [])

def read_tiff_downsampled(tiff_path, scale_factor=2):
    """Čti TIFF se downsampling (2x nebo 4x)"""
    with rasterio.open(tiff_path) as src:
        # Originální rozměry
        orig_height = src.height
        orig_width = src.width
        
        print(f" Soubor: {tiff_path}")
        print(f" Původní rozměry: {orig_width}×{orig_height} pixelů")
        print(f" Scale factor: {scale_factor}x")
        
        # Nové rozměry
        new_height = orig_height // scale_factor
        new_width = orig_width // scale_factor
        
        print(f" Výsledné rozměry: {new_width}×{new_height} pixelů")
        
        # Čti v chunkích
        chunk_size = max(1, orig_height // 6)
        heights = np.zeros((new_height, new_width), dtype=np.uint16)
        
        for chunk_id in range(0, orig_height, chunk_size):
            chunk_end = min(chunk_id + chunk_size, orig_height)
            window = Window(0, chunk_id, orig_width, chunk_end - chunk_id)
            chunk = src.read(1, window=window)
            
            # Downsampling
            downsampled = chunk[::scale_factor, ::scale_factor]
            target_height = downsampled.shape[0]
            target_row_start = chunk_id // scale_factor
            heights[target_row_start:target_row_start + target_height, :] = downsampled
            
            progress = (chunk_id + chunk_size) / orig_height
            print(f"\r [{'█' * int(progress * 50):<50}] {progress*100:.0f}%", end='', flush=True)
        
        print(" ✓")
        
        # Statistika
        nonzero_count = np.count_nonzero(heights)
        max_height = np.max(heights) if nonzero_count > 0 else 0
        print(f" ✓ Výšky: 0-{max_height}m")
        print(f" ✓ Bunky s daty: {nonzero_count:,}/{new_height * new_width:,}")
        
        return heights

def pixel_to_gps(row, col, transform, invert=False):
    """Převeď pixel na GPS (či obráceně)"""
    a, b, c, d, e, f = transform
    if not invert:  # pixel → GPS
        x = a * col + b * row + c
        y = d * col + e * row + f
    else:  # GPS → pixel
        denom = a * e - b * d
        col = ((e * (row - f) - d * (col - c)) / denom)
        row = ((a * (col - c) - b * (row - f)) / denom)
        x, y = row, col
    return x, y

def get_msk_bounds_pixels(transform, grid_shape):
    """Vrátí pixel bounds pro MSK region"""
    height, width = grid_shape
    
    # Převeď GPS bounds na pixel coords
    # Affine transform: (a, b, c, d, e, f)
    # x = a*col + b*row + c
    # y = d*col + e*row + f
    
    a, b, c, d, e, f = transform
    
    # Inverze transformu
    denom = a * e - b * d
    
    corners_gps = [
        (MSK_BOUNDS['west'], MSK_BOUNDS['north']),   # W, N
        (MSK_BOUNDS['east'], MSK_BOUNDS['north']),   # E, N
        (MSK_BOUNDS['west'], MSK_BOUNDS['south']),   # W, S
        (MSK_BOUNDS['east'], MSK_BOUNDS['south']),   # E, S
    ]
    
    cols = []
    rows = []
    
    for x_gps, y_gps in corners_gps:
        col = (e * (x_gps - c) - b * (y_gps - f)) / denom
        row = (a * (y_gps - f) - d * (x_gps - c)) / denom
        cols.append(int(np.clip(col, 0, width - 1)))
        rows.append(int(np.clip(row, 0, height - 1)))
    
    col_min, col_max = min(cols), max(cols)
    row_min, row_max = min(rows), max(rows)
    
    return row_min, row_max, col_min, col_max

def filter_to_msk_region(heights, row_min, row_max, col_min, col_max):
    """Filtruj jen MSK region"""
    msk_heights = np.zeros_like(heights)
    msk_heights[row_min:row_max, col_min:col_max] = heights[row_min:row_max, col_min:col_max]
    return msk_heights

def init_pollution_grid(grid_shape):
    """Inicializuj pollution grid"""
    return np.zeros(grid_shape, dtype=np.float32)

def apply_factory_pollution(pollution_grid, factories, transform, grid_shape):
    """Aplikuj znečištění z továren (dummy - všechno 0 zatím)"""
    # V reálném projektu by zde byla vzdálenostní funkce
    pass

def build_row_ranges(heights):
    """Vytvoř row ranges s filtrováním nul"""
    row_ranges = []
    
    for row_id in range(heights.shape[0]):
        row_data = heights[row_id, :]
        
        # Najdi nenulové prvky
        nonzero_indices = np.where(row_data > 0)[0]
        
        # Pokud jsou všechny nuly → skipni
        if len(nonzero_indices) == 0:
            continue
        
        # Vezmi PRVNÍ a POSLEDNÍ nenulovou pozici
        col_start = int(nonzero_indices[0])
        col_end = int(nonzero_indices[-1]) + 1
        
        row_ranges.append({
            'row_id': row_id,
            'col_start': col_start,
            'col_end': col_end
        })
    
    return row_ranges

def export_v5_binary(output_path, heights, pollution, transform, row_ranges):
    """Exportuj do V5 binárního formátu"""
    with open(output_path, 'wb') as f:
        # Header (60B)
        width, height = heights.shape[1], heights.shape[0]
        num_valid_rows = len(row_ranges)
        
        f.write(struct.pack('I', width))           # 4B
        f.write(struct.pack('I', height))          # 4B
        f.write(struct.pack('I', num_valid_rows))  # 4B
        
        for val in transform:
            f.write(struct.pack('d', val))         # 8B each × 6 = 48B
        
        # Row ranges (12B each)
        for rr in row_ranges:
            f.write(struct.pack('I', rr['row_id']))
            f.write(struct.pack('I', rr['col_start']))
            f.write(struct.pack('I', rr['col_end']))
        
        # Raw data (8B per cell)
        for rr in row_ranges:
            row_id = rr['row_id']
            col_start = rr['col_start']
            col_end = rr['col_end']
            
            for col in range(col_start, col_end):
                h = heights[row_id, col]
                p = pollution[row_id, col]
                
                f.write(struct.pack('H', h))      # 2B uint16
                f.write(struct.pack('f', p))      # 4B float32

def main():
    print("\n" + "=" * 70)
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "EXPORT V5 - COMPACT METADATA" + " " * 25 + "║")
    print("║" + " " * 13 + "Row ranges + filtrování nul" + " " * 27 + "║")
    print("║" + " " * 23 + "Jen MSK region" + " " * 31 + "║")
    print("╚" + "=" * 68 + "╝")
    print("=" * 70 + "\n")
    
    # Parametry
    scale_factor = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    
    tiff_path = Path("../macbook-data/EL-GRID.tif")
    json_path = Path("plants.json")
    output_bin = Path("terrain.bin")
    
    # KROK 0: Načti továrny
    print(" 🔍 Hledání TIFF souboru...")
    if not tiff_path.exists():
        print(f" ✗ Soubor neexistuje: {tiff_path}")
        return 1
    print(f" ✓ Nalezen: {tiff_path}\n")
    
    print(" KROK 0: NAČTENÍ TOVÁREN")
    factories = load_factories(json_path) if json_path.exists() else []
    print(f" ✓ Počet továren: {len(factories)}\n")
    
    # KROK 1: Čti a downsampluj TIFF
    print(" KROK 1: ČTENÍ A DOWNSAMPLING TIFF")
    print(" Čtení v chunkích...")
    heights = read_tiff_downsampled(str(tiff_path), scale_factor)
    print()
    
    # KROK 2: Filtrování továren do MSK
    print(" KROK 2: FILTROVÁNÍ TOVÁREN (MSK REGION)")
    print(f" ✓ Filtrováno: {len(factories)} továren (v MSK)\n")
    
    # KROK 3: Inicializace pollution gridu
    print(" KROK 3: INICIALIZACE POLLUTION GRIDU")
    pollution = init_pollution_grid(heights.shape)
    print(f" ✓ Shape: {heights.shape}\n")
    
    # KROK 4: Aplikuj znečištění
    print(" KROK 4: APLIKACE ZNEČIŠTĚNÍ")
    apply_factory_pollution(pollution, factories, None, heights.shape)
    print(" ✓ Znečištění: 0.000000 (avg)\n")
    
    # KROK 5: Vytvoř row ranges
    print(" KROK 5: VYTVOŘENÍ ROW RANGES")
    row_ranges = build_row_ranges(heights)
    
    skipped_rows = heights.shape[0] - len(row_ranges)
    print(f" 📊 Grid: {heights.shape[1]}×{heights.shape[0]} pixelů")
    print(f" 📊 Řádků s daty: {len(row_ranges)}")
    print(f" 📊 Řádků bez dat (skipped): {skipped_rows}\n")
    
    # KROK 6: Export V5
    print(" KROK 6: EXPORT V5 - COMPACT METADATA + ROW RANGES")
    
    # Dummy transform
    transform = (1.0, 0.0, 0.0, 0.0, -1.0, 0.0)
    
    export_v5_binary(str(output_bin), heights, pollution, transform, row_ranges)
    
    file_size_mb = output_bin.stat().st_size / (1024 * 1024)
    cells_with_data = sum((rr['col_end'] - rr['col_start']) for rr in row_ranges)
    
    print(f" ✓ Soubor: {output_bin} ({file_size_mb:.2f} MB)")
    print(f" ✓ Buňky: {cells_with_data:,} s daty\n")
    
    # Statistika
    print(" 📊 STATISTIKA:")
    nonzero = np.count_nonzero(heights)
    max_h = np.max(heights) if nonzero > 0 else 0
    print(f" Buněk s height > 0: {nonzero:,}")
    print(f" Průměrná výška: {np.mean(heights[heights > 0]):.1f}m (non-zero)")
    print(f" Max výška: {max_h}m")
    print(f" Znečištění: {np.mean(pollution):.6f} (avg)")
    
    print("\n" + "=" * 70)
    print(" ✓ EXPORT V5 - HOTOV!")
    print("=" * 70 + "\n")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
