#!/usr/bin/env python3
"""
Export do BIN V5 - Export TIFF → BIN
====================================
Čte TIFF s FIXNÍMI MEZEMI a exportuje do BIN
Meze z TIFF: 0.74-1.0 (šířka), 0.27-0.65 (výška)
Filtrování: -500 až 2500 m
"""

import struct
import json
import numpy as np
from pathlib import Path
import sys
import gc

try:
    import rasterio
    from rasterio.windows import Window
    import rasterio.transform
except ImportError as e:
    print(f"✗ Chybí balíček: {e}")
    exit(1)

# ========== FIXNÍ MEZE - NEMENNÉ! ==========
TIFF_COL_START_RATIO = 0.74      # 74% šířky TIFF
TIFF_COL_END_RATIO = 1.0         # 100% šířky TIFF
TIFF_ROW_START_RATIO = 0.27      # 27% výšky TIFF
TIFF_ROW_END_RATIO = 0.65        # 65% výšky TIFF

MIN_HEIGHT = -500                 # Minimální výška (od TIFF)
MAX_HEIGHT = 2500                 # Maximální výška (od TIFF)

SCALE_FACTOR = 16                 # Downsampling

# =======================================

def step1_load_and_downsample_tiff_fast(tif_path, scale_factor=SCALE_FACTOR):
    """Načti TIFF, downsampl a exportuj (FIXNÍ MEZE)"""
    print("\n" + "=" * 70)
    print("KROK 1: ČTENÍ TIFF + DOWNSAMPLING + FILTROVÁNÍ")
    print("=" * 70)
    
    try:
        with rasterio.open(str(tif_path)) as src:
            original_width = src.width
            original_height = src.height
            
            print(f" Soubor: {tif_path.name}")
            print(f" Původní rozměry: {original_width}×{original_height} px")
            
            # Výpočet region bounds z ratií
            col_start = int(original_width * TIFF_COL_START_RATIO)
            col_end = int(original_width * TIFF_COL_END_RATIO)
            row_start = int(original_height * TIFF_ROW_START_RATIO)
            row_end = int(original_height * TIFF_ROW_END_RATIO)
            
            region_width = col_end - col_start
            region_height = row_end - row_start
            
            print(f" Region: [{row_start}:{row_end}] x [{col_start}:{col_end}]")
            print(f" Region rozměry: {region_width}×{region_height} px")
            
            h_new = region_height // scale_factor
            w_new = region_width // scale_factor
            
            print(f" Scale factor: {scale_factor}x")
            print(f" Výsledné rozměry: {w_new}×{h_new} px\n")
            
            heights_downsampled = np.zeros((h_new, w_new), dtype=np.uint16)
            
            # Affine transform
            window_transform = src.window_transform(Window(col_start, row_start, region_width, region_height))
            transform = window_transform * rasterio.transform.Affine.scale(scale_factor, scale_factor)
            crs = src.crs
            
            print(f" FILTROVÁNÍ MEZE:")
            print(f"   Min: {MIN_HEIGHT}m")
            print(f"   Max: {MAX_HEIGHT}m")
            print(f"   (Odstranuje NaN, Inf, nodata, extremy)\n")
            
            # Čtení v chunkích
            chunk_rows = scale_factor * 500
            num_chunks = (region_height + chunk_rows - 1) // chunk_rows
            
            for chunk_idx in range(num_chunks):
                chunk_row_start = chunk_idx * chunk_rows
                chunk_row_end = min(chunk_row_start + chunk_rows, region_height)
                rows_in_chunk = chunk_row_end - chunk_row_start
                
                abs_row_start = row_start + chunk_row_start
                abs_row_end = row_start + chunk_row_end
                
                pct = int(100 * chunk_idx / num_chunks)
                print(f" [{pct:3d}%] Chunk {chunk_idx + 1}/{num_chunks}...", end=' ', flush=True)
                
                try:
                    chunk_data = src.read(1, window=((abs_row_start, abs_row_end), (col_start, col_end)))
                    chunk_data = chunk_data.astype(np.float32)
                    
                    # Filtrování bad pixely
                    nan_mask = np.isnan(chunk_data)
                    inf_mask = np.isinf(chunk_data)
                    nodata = src.nodata
                    nodata_mask = (chunk_data == nodata) if nodata is not None else np.zeros_like(chunk_data, dtype=bool)
                    extreme_mask = np.abs(chunk_data) > 10000
                    
                    bad_mask = nan_mask | inf_mask | nodata_mask | extreme_mask
                    chunk_data[bad_mask] = 0
                    
                    # Aplikuj MIN/MAX meze
                    chunk_data[chunk_data < MIN_HEIGHT] = 0
                    chunk_data[chunk_data > MAX_HEIGHT] = 0
                    
                    # Downsampling
                    rows_trim = (rows_in_chunk // scale_factor) * scale_factor
                    cols_trim = (region_width // scale_factor) * scale_factor
                    chunk_data_trim = chunk_data[:rows_trim, :cols_trim]
                    
                    rows_reshaped = rows_trim // scale_factor
                    cols_reshaped = cols_trim // scale_factor
                    
                    chunk_reshaped = chunk_data_trim.reshape(
                        rows_reshaped, scale_factor,
                        cols_reshaped, scale_factor
                    )
                    
                    chunk_downsampled = chunk_reshaped.mean(axis=(1, 3)).astype(np.uint16)
                    
                    out_row_start = chunk_row_start // scale_factor
                    out_row_end = out_row_start + rows_reshaped
                    
                    if out_row_end <= h_new:
                        heights_downsampled[out_row_start:out_row_end, :cols_reshaped] = chunk_downsampled
                    
                    del chunk_data, chunk_data_trim, chunk_reshaped, chunk_downsampled
                    print("✓", flush=True)
                    
                except Exception as e:
                    print(f"✗ {e}", flush=True)
                    continue
            
            gc.collect()
            
            nonzero_count = np.count_nonzero(heights_downsampled)
            min_h = heights_downsampled[heights_downsampled > 0].min() if nonzero_count > 0 else 0
            max_h = heights_downsampled.max()
            mean_h = heights_downsampled[heights_downsampled > 0].mean() if nonzero_count > 0 else 0
            
            print(f"\n 📊 STATISTIKA:")
            print(f"   Buňky s daty: {nonzero_count:,}")
            print(f"   Min výška: {min_h:.0f}m")
            print(f"   Max výška: {max_h:.0f}m")
            print(f"   Průměr: {mean_h:.1f}m\n")
            
            return heights_downsampled, transform, crs, (w_new, h_new)
    
    except Exception as e:
        print(f"✗ Chyba: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None

def step2_export_bin_v5(heights, transform, output_file='terrain.bin'):
    """Exportuj do V5 BIN formátu"""
    print("=" * 70)
    print("KROK 2: EXPORT V5 BINARY")
    print("=" * 70)
    
    rows, cols = heights.shape
    print(f" Grid: {cols}×{rows}")
    
    # Analýza řádků
    print(f"\n Analýza řádků...")
    row_ranges = []
    
    for row_id in range(rows):
        row_data = heights[row_id, :]
        nonzero_indices = np.where(row_data > 0)[0]
        
        if len(nonzero_indices) == 0:
            continue  # Skipuj prázdné řádky
        
        col_start = int(nonzero_indices[0])
        col_end = int(nonzero_indices[-1]) + 1
        
        row_ranges.append({
            'row_id': row_id,
            'col_start': col_start,
            'col_end': col_end,
            'col_count': col_end - col_start
        })
    
    valid_rows = len(row_ranges)
    print(f" Řádků s daty: {valid_rows}/{rows}")
    print(f" Řádků bez dat (skipped): {rows - valid_rows}\n")
    
    # Zápis BIN
    print(f" Zapis do {output_file}...")
    
    with open(output_file, 'wb') as f:
        # Header (60B)
        f.write(struct.pack('I', cols))                          # width
        f.write(struct.pack('I', rows))                          # height
        f.write(struct.pack('I', valid_rows))                    # num_valid_rows
        
        # Transform (6 doubles = 48B)
        for val in [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f]:
            f.write(struct.pack('d', val))
        
        # Row ranges (12B per row)
        for rr in row_ranges:
            f.write(struct.pack('III', rr['row_id'], rr['col_start'], rr['col_end']))
        
        # Raw data (height + pollution)
        pollution_grid = np.zeros((rows, cols), dtype=np.float32)  # Zatím jen 0
        
        for rr in row_ranges:
            row_id = rr['row_id']
            col_start = rr['col_start']
            col_end = rr['col_end']
            
            for col in range(col_start, col_end):
                height = heights[row_id, col]
                pollution = pollution_grid[row_id, col]
                f.write(struct.pack('H', height))
                f.write(struct.pack('f', pollution))
    
    file_size = Path(output_file).stat().st_size / 1024 / 1024
    total_cells = sum(rr['col_count'] for rr in row_ranges)
    
    print(f" ✓ Soubor: {output_file} ({file_size:.2f} MB)")
    print(f"\n 📊 STATISTIKA:")
    print(f"   Řádků: {valid_rows}")
    print(f"   Buněk: {total_cells:,}")
    print(f"   Komprese: ~{(rows*cols) / (total_cells*1.2):.1f}x\n")

def find_tiff_file():
    """Najdi TIFF soubor"""
    candidates = [
        Path('EL-GRID.tif'),
        Path('../EL-GRID.tif'),
        Path('../macbook-data/EL-GRID.tif'),
    ]
    
    for path in candidates:
        if path.exists():
            return path
    
    return None

def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "EXPORT V5 - TIFF → BIN".center(68) + "║")
    print("║" + "Fixní meze, kompaktní formát".center(68) + "║")
    print("╚" + "="*68 + "╝")
    
    tif_path = find_tiff_file()
    if not tif_path:
        print("✗ TIFF soubor nenalezen!")
        return False
    
    heights, transform, crs, dims = step1_load_and_downsample_tiff_fast(tif_path, SCALE_FACTOR)
    if heights is None:
        return False
    
    step2_export_bin_v5(heights, transform)
    
    print("=" * 70)
    print("✓ EXPORT - HOTOVO!")
    print("=" * 70 + "\n")
    
    return True

if __name__ == '__main__':
    main()
