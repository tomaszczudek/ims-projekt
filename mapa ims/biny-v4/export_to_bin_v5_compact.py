#!/usr/bin/env python3
"""
EXPORT DO BINÁRNÍHO SOUBORU V5 - COMPACT METADATA + ROW RANGES
===========================================================

FORMÁT:
  Header:
    uint32 width              [1 * 4B]
    uint32 height             [1 * 4B]
    uint32 num_valid_rows     [1 * 4B]
    double transform[6]       [6 * 8B]
    
  Row Ranges (pro každý VALIDNÍ řádek):
    uint32 row_id             [1 * 4B]
    uint32 col_start          [1 * 4B]
    uint32 col_end            [1 * 4B]
    
  Data (pro každý VALIDNÍ řádek):
    [height (uint16) + pollution (float32)] * (col_end - col_start)

FILTROVÁNÍ:
  - Řádky kde od col_end do konce jsou POUZE nuly = se ZAPISÍjsou jen data [col_start:col_end]
  - Pokud řádek nemá vůbec žádná data (height=0 všude) = SKIPUJ celý řádek
"""

import struct
import json
import numpy as np
from pathlib import Path
import sys
import gc

try:
    import rasterio
    from pyproj import Transformer
except ImportError as e:
    print(f"✗ Chybí balíček: {e}")
    exit(1)

# MSK BOUNDS pro filtrování
MSK_NORTH = 50.327
MSK_SOUTH = 49.39
MSK_EAST = 18.86
MSK_WEST = 17.146


def step0_load_local_plants():
    """Čti továrny"""
    print("\nKROK 0: NAČTENÍ TOVÁREN")
    print("="*70)
    
    plants_file = Path('../plants.json')
    if not plants_file.exists():
        print(f"✗ Soubor {plants_file} neexistuje!")
        return []
    
    try:
        with open(plants_file, 'r', encoding='utf-8') as f:
            root = json.load(f)
            if isinstance(root, dict) and 'data' in root:
                data = root['data']
                if isinstance(data, dict) and 'Plants' in data:
                    plants = data['Plants']
                    print(f" ✓ Počet továren: {len(plants)}")
                    return plants
        return []
    except Exception as e:
        print(f"✗ Chyba: {e}")
        return []


def step1_load_and_downsample_tiff_fast(tif_path, scale_factor=2):
    """FAST downsampling v chunkách - POUZE MS REGION S FILTROVÁNÍM"""
    print("\n" + "=" * 70)
    print("KROK 1: ČTENÍ A DOWNSAMPLING TIFF (FAST) - POUZE MS REGION")
    print("=" * 70)
    
    try:
        with rasterio.open(str(tif_path)) as src:
            original_width = src.width
            original_height = src.height
            
            print(f" Soubor: {tif_path.name}")
            print(f" Původní rozměry: {original_width}×{original_height} pixelů")
            
            # MS REGION BOUNDS - stejně jako v step1_extract_ms_region
            col_start = int(src.width * 0.74)
            col_end = int(src.width)
            row_start = int(src.height * 0.27)
            row_end = int(src.height * 0.65)
            
            region_width = col_end - col_start
            region_height = row_end - row_start
            
            print(f" MS Region: [{row_start}:{row_end}] x [{col_start}:{col_end}]")
            print(f" Region rozměry: {region_width}×{region_height} pixelů")
            print(f" Scale factor: {scale_factor}x")
            
            # Nové rozměry (po downsamplingu)
            h_new = region_height // scale_factor
            w_new = region_width // scale_factor
            
            print(f" Výsledné rozměry: {w_new}×{h_new} pixelů\n")
            
            heights_downsampled = np.zeros((h_new, w_new), dtype=np.uint16)
            
            # Affine transform pro MS region
            window_transform = src.window_transform(Window(col_start, row_start, region_width, region_height))
            transform = window_transform * rasterio.transform.Affine.scale(scale_factor, scale_factor)
            crs = src.crs
            
            # FILTROVÁNÍ - stejné jako v step1_extract_ms_region
            MIN_HEIGHT = -500      # Minimální výška (odstranit chyby)
            MAX_HEIGHT = 2500      # Maximální výška (realistická)
            
            print(f" FILTROVÁNÍ:")
            print(f"   Min: {MIN_HEIGHT}m")
            print(f"   Max: {MAX_HEIGHT}m")
            print(f"   (Odstraní: NaN, Inf, nodata, extrémní hodnoty)\n")
            
            # Čtení v chunkách - ALE JEN MS REGION
            chunk_rows = scale_factor * 500
            num_chunks = (region_height + chunk_rows - 1) // chunk_rows
            
            for chunk_idx in range(num_chunks):
                chunk_row_start = chunk_idx * chunk_rows
                chunk_row_end = min(chunk_row_start + chunk_rows, region_height)
                rows_in_chunk = chunk_row_end - chunk_row_start
                
                # Mapuj na absolutní pixely v TIFF
                abs_row_start = row_start + chunk_row_start
                abs_row_end = row_start + chunk_row_end
                
                pct = int(100 * chunk_idx / num_chunks)
                print(f" [{pct:3d}%] Chunk {chunk_idx + 1}/{num_chunks}...", end=' ', flush=True)
                
                try:
                    # Čti POUZE MS REGION chunk
                    chunk_data = src.read(
                        1, 
                        window=((abs_row_start, abs_row_end), (col_start, col_end))
                    )
                    chunk_data = chunk_data.astype(np.float32)
                    
                    # FILTROVÁNÍ - stejné jako v step1_extract_ms_region
                    # 1. Zjistit bad pixely
                    nan_mask = np.isnan(chunk_data)
                    inf_mask = np.isinf(chunk_data)
                    
                    nodata = src.nodata
                    nodata_mask = (chunk_data == nodata) if nodata is not None else np.zeros_like(chunk_data, dtype=bool)
                    
                    extreme_mask = np.abs(chunk_data) > 10000
                    
                    # 2. Zkombinovat všechny bad masky
                    bad_mask = nan_mask | inf_mask | nodata_mask | extreme_mask
                    chunk_data[bad_mask] = 0
                    
                    # 3. Vyčistit podle MIN/MAX
                    chunk_data[chunk_data < MIN_HEIGHT] = 0
                    chunk_data[chunk_data > MAX_HEIGHT] = 0
                    
                    # Downsampling - trimování na sudé rozměry
                    rows_trim = (rows_in_chunk // scale_factor) * scale_factor
                    cols_trim = (region_width // scale_factor) * scale_factor
                    chunk_data_trim = chunk_data[:rows_trim, :cols_trim]
                    
                    # Reshape pro mean pooling
                    rows_reshaped = rows_trim // scale_factor
                    cols_reshaped = cols_trim // scale_factor
                    
                    chunk_reshaped = chunk_data_trim.reshape(
                        rows_reshaped, scale_factor,
                        cols_reshaped, scale_factor
                    )
                    
                    # Mean pooling - průměrná hodnota v každém bloku
                    chunk_downsampled = chunk_reshaped.mean(axis=(1, 3)).astype(np.uint16)
                    
                    # Zapiš do output pole
                    out_row_start = chunk_row_start // scale_factor
                    out_row_end = out_row_start + rows_reshaped
                    
                    if out_row_end <= h_new:
                        heights_downsampled[out_row_start:out_row_end, :cols_reshaped] = chunk_downsampled
                    
                    # Vyčistění paměti
                    del chunk_data, chunk_data_trim, chunk_reshaped, chunk_downsampled
                    print("✓", flush=True)
                    
                except Exception as e:
                    print(f"✗ {e}", flush=True)
                    continue
            
            gc.collect()
            
            # Statistika
            nonzero_count = np.count_nonzero(heights_downsampled)
            min_h = heights_downsampled[heights_downsampled > 0].min() if nonzero_count > 0 else 0
            max_h = heights_downsampled.max()
            mean_h = heights_downsampled[heights_downsampled > 0].mean() if nonzero_count > 0 else 0
            
            print(f"\n 📊 STATISTIKA:")
            print(f"   Buňky s daty: {nonzero_count:,}")
            print(f"   Min výška: {min_h:.0f}m")
            print(f"   Max výška: {max_h:.0f}m")
            print(f"   Průměr: {mean_h:.1f}m")
            print(f"   ✓ Výšky: {min_h:.0f}-{max_h:.0f}m\n")
            
            return heights_downsampled, transform, crs, (w_new, h_new)
    
    except Exception as e:
        print(f"✗ Chyba: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None
    

def step2_filter_plants(pollution_data, tif_bounds):
    """Filtruj továrny"""
    print("\nKROK 2: FILTROVÁNÍ TOVÁREN (MSK REGION)")
    print("="*70)
    
    filtered = []
    
    for plant in pollution_data:
        try:
            lat = float(plant.get('Lat', 0))
            lon = float(plant.get('Lon', 0))
            name = 'Unknown'
            curr_year = plant.get('CurrentYear', {})
            
            if isinstance(curr_year, dict):
                name = curr_year.get('Name', 'Unknown')
            
            # FILTRUJ POUZE MSK REGION!
            if MSK_SOUTH <= lat <= MSK_NORTH and MSK_WEST <= lon <= MSK_EAST:
                filtered.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'type': curr_year.get('NACE', 'Unknown') if isinstance(curr_year, dict) else 'Unknown',
                    'plant_data': plant
                })
        except:
            pass
    
    print(f" ✓ Filtrováno: {len(filtered)} továren (v MSK)")
    return filtered


def step3_init_pollution_grid(heights):
    """Inicializuj pollution grid"""
    print("\nKROK 3: INICIALIZACE POLLUTION GRIDU")
    print("="*70)
    
    rows, cols = heights.shape
    pollution_grid = np.zeros((rows, cols), dtype=np.float32)
    
    print(f" ✓ Shape: {pollution_grid.shape}")
    
    return pollution_grid


def step4_export_bin_v5_with_row_ranges(heights, pollution_grid, transform, output_file='terrain.bin'):
    """
    Export do V5 formátu s ROW RANGES a kompaktním metadatem
    
    FILTROVÁNÍ:
    - Pro každý řádek: najdi col_start a col_end (kde končí poslední nenulová výška)
    - Zapiš jen [col_start:col_end]
    - Řádky kde všechny výšky = 0 SKIPUJ
    """
    print("\nKROK 4: EXPORT V5 - COMPACT METADATA + ROW RANGES")
    print("="*70)
    
    rows, cols = heights.shape
    
    print(f" 📊 Grid: {cols}×{rows}")
    print(f" ✓ Formát: Compact header + row ranges + raw data")
    
    # Analýza řádků - najdi row ranges
    print(f"\n 📊 Analýza řádků (filtrování nul)...")
    
    row_ranges = []
    
    for row_id in range(rows):
        row_data = heights[row_id, :]
        
        # Najdi poslední nenulový prvek
        nonzero_indices = np.where(row_data > 0)[0]
        
        if len(nonzero_indices) == 0:
            # Celý řádek je nulový - SKIPUJ!
            continue
        
        # col_start a col_end (poslední nenulováprvek + 1)
        col_start = int(nonzero_indices[0])
        col_end = int(nonzero_indices[-1]) + 1
        col_count = col_end - col_start
        
        row_ranges.append({
            'row_id': row_id,
            'col_start': col_start,
            'col_end': col_end,
            'col_count': col_count
        })
    
    valid_rows = len(row_ranges)
    
    print(f" Řádků s daty: {valid_rows}/{rows}")
    print(f" Řádků bez dat (skipped): {rows - valid_rows}")
    
    # Zápis do BIN
    print(f"\n 📝 Zapis do {output_file}...")
    
    with open(output_file, 'wb') as f:
        # ===== HEADER (COMPACT, BEZ VERZÍ) =====
        f.write(struct.pack('I', cols))           # width
        f.write(struct.pack('I', rows))           # height
        f.write(struct.pack('I', valid_rows))     # num_valid_rows
        
        # Transform (6 doubles)
        for val in [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f]:
            f.write(struct.pack('d', val))
        
        print(f" ✓ Header (40 bajtů)")
        
        # ===== ROW RANGES =====
        for rr in row_ranges:
            f.write(struct.pack('III', rr['row_id'], rr['col_start'], rr['col_end']))
        
        print(f" ✓ Row ranges ({valid_rows} řádků)")
        
        # ===== RAW DATA =====
        for rr in row_ranges:
            row_id = rr['row_id']
            col_start = rr['col_start']
            col_end = rr['col_end']
            
            # Zapis jen [col_start:col_end] pro tenhle řádek
            for col in range(col_start, col_end):
                height = heights[row_id, col]
                pollution = pollution_grid[row_id, col]
                
                f.write(struct.pack('H', height))
                f.write(struct.pack('f', pollution))
        
        print(f" ✓ Raw data")
    
    file_size = Path(output_file).stat().st_size / 1024 / 1024
    
    # Statistika
    total_cells_written = sum(rr['col_count'] for rr in row_ranges)
    
    print(f"\n ✓ Soubor: {output_file} ({file_size:.2f} MB)")
    print(f"\n 📊 STATISTIKA:")
    print(f" Řádků s daty: {valid_rows}")
    print(f" Buněk zapsáno: {total_cells_written} (bez nul)")
    print(f" Buněk preskočeno: {rows * cols - total_cells_written}")
    print(f" Komprese: ~{(rows*cols) / (total_cells_written*1.2):.1f}x")


def find_tiff_file():
    """Najdi TIFF"""
    print("\n 🔍 Hledání TIFF souboru...")
    
    candidates = [
        Path('EL-GRID.tif'),
        Path('../EL-GRID.tif'),
        Path('../macbook-data/EL-GRID.tif'),
    ]
    
    for path in candidates:
        if path.exists():
            print(f" ✓ Nalezen: {path}")
            return path
    
    el_grid_path = Path('../macbook-data')
    if el_grid_path.exists():
        tif_files = sorted(el_grid_path.glob('*EL-GRID.tif'))
        tif_files = [f for f in tif_files if 'downsampled' not in f.name]
        
        if tif_files:
            print(f" ✓ Nalezen: {tif_files[0]}")
            return tif_files[0]
    
    print("✗ Žádný TIFF soubor!")
    return None


def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "EXPORT V5 - COMPACT + ROW RANGES".center(68) + "║")
    print("║" + "Metadata bez verzí, row-based filtrování nul".center(68) + "║")
    print("║" + "Jen MSK region".center(68) + "║")
    print("╚" + "="*68 + "╝")
    
    scale_factor = 16
    if len(sys.argv) > 1:
        try:
            scale_factor = int(sys.argv[1])
            print(f"\n 📊 Scale factor: {scale_factor}x")
        except:
            pass
    
    tif_path = find_tiff_file()
    if not tif_path:
        return False
    
    pollution_data = step0_load_local_plants()
    if not pollution_data:
        return False
    
    heights, transform, crs, tif_bounds = step1_load_and_downsample_tiff_fast(tif_path, scale_factor)
    if heights is None:
        return False
    
    filtered_sources = step2_filter_plants(pollution_data, tif_bounds)
    pollution_grid = step3_init_pollution_grid(heights)
    step4_export_bin_v5_with_row_ranges(heights, pollution_grid, transform)
    
    print("\n" + "="*70)
    print("✓ EXPORT V5 - HOTOV!")
    print("="*70)
    print("\n Binární soubor:")
    print(" ✓ Compact header (bez verzí, jen praktické info)")
    print(" ✓ Row ranges (pro každý validní řádek)")
    print(" ✓ Raw data (bez nul na konci řádků)")
    print(" ✓ Jen MSK region")
    print(" ✓ Efektivní struktura")
    print("\n")
    
    return True


if __name__ == '__main__':
    main()
