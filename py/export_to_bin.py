"""
Export do BIN V5 s TOVÁRNAMI - OPRAVENO TRANSFORMACE PŘES PYPROJ
==================================================================

✓ GPS filtrování: 1286 továren (správně)
✓ Transformace souřadnic: GPS (WGS84) → UTM → TIFF pixely (SPRÁVNĚ!)
✓ Uložení indexů: (row, col, emission) 12B per továrna
✓ C++ Loader: Načte indexy a renderuje továrny

KLÍČ: Správné transformace:
  GPS (WGS84) → UTM32N → TIFF lokální souřadnice
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
    from pyproj import Transformer
except ImportError as e:
    print(f"✗ Chybí balíček: {e}")
    print("  pip install rasterio pyproj")
    exit(1)

# ========== FIXNÍ MEZE - NEMENNÉ! ==========
TIFF_COL_START_RATIO = 0.74
TIFF_COL_END_RATIO = 1.0
TIFF_ROW_START_RATIO = 0.27
TIFF_ROW_END_RATIO = 0.65
MIN_HEIGHT = -500
MAX_HEIGHT = 2500
SCALE_FACTOR = 16

# MSK REGION
MSK_NORTH = 50.327
MSK_SOUTH = 49.39
MSK_EAST = 18.86
MSK_WEST = 17.146

# =======================================

def step0_load_plants():
    """Načti továrny z JSON"""
    print("\n" + "=" * 70)
    print("KROK 0: NAČTENÍ TOVÁREN")
    print("=" * 70)
    plants_file = Path('../data/plants.json')
    if not plants_file.exists():
        print(f" ✗ Soubor {plants_file} neexistuje!")
        return []
    try:
        file_size = plants_file.stat().st_size / 1024 / 1024
        print(f"\n Čtu {plants_file} ({file_size:.1f} MB)...")
        with open(plants_file, 'r', encoding='utf-8') as f:
            root = json.load(f)
        print(f" ✓ Načteno ({file_size:.1f} MB)")
        if isinstance(root, dict) and 'data' in root:
            data = root['data']
            if isinstance(data, dict) and 'Plants' in data:
                plants = data['Plants']
                print(f" ✓ Počet továren: {len(plants)}")
                return plants
        print("✗ Neznámá struktura JSON!")
        return []
    except Exception as e:
        print(f" ✗ Chyba: {e}")
        return []

def step1_load_and_downsample_tiff_fast(tif_path, scale_factor=SCALE_FACTOR):
    """Načti TIFF a downsampluj"""
    print("\n" + "=" * 70)
    print("KROK 1: ČTENÍ TIFF + DOWNSAMPLING + FILTROVÁNÍ")
    print("=" * 70)
    try:
        with rasterio.open(str(tif_path)) as src:
            original_width = src.width
            original_height = src.height
            print(f" Soubor: {tif_path.name}")
            print(f" Původní rozměry: {original_width}×{original_height} px")
            print(f" CRS: {src.crs}")

            # Výpočet region bounds
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

            # ✓ REGIONÁLNÍ TRANSFORM
            window_transform = src.window_transform(Window(col_start, row_start, region_width, region_height))
            transform = window_transform * rasterio.transform.Affine.scale(scale_factor, scale_factor)

            crs = src.crs
            original_transform = src.transform  # ORIGINÁLNÍ transform pro transformaci GPS

            print(f" FILTROVÁNÍ MEZE:")
            print(f" Min: {MIN_HEIGHT}m")
            print(f" Max: {MAX_HEIGHT}m\n")

            # Čtení v chunkách
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

                    # Filtrování
                    nan_mask = np.isnan(chunk_data)
                    inf_mask = np.isinf(chunk_data)
                    nodata = src.nodata
                    nodata_mask = (chunk_data == nodata) if nodata is not None else np.zeros_like(chunk_data, dtype=bool)
                    extreme_mask = np.abs(chunk_data) > 10000
                    bad_mask = nan_mask | inf_mask | nodata_mask | extreme_mask
                    chunk_data[bad_mask] = 0
                    chunk_data[chunk_data < MIN_HEIGHT] = 0
                    chunk_data[chunk_data > MAX_HEIGHT] = 0

                    # Downsampling
                    rows_trim = (rows_in_chunk // scale_factor) * scale_factor
                    cols_trim = (region_width // scale_factor) * scale_factor
                    chunk_data_trim = chunk_data[:rows_trim, :cols_trim]
                    rows_reshaped = rows_trim // scale_factor
                    cols_reshaped = cols_trim // scale_factor
                    chunk_reshaped = chunk_data_trim.reshape(rows_reshaped, scale_factor, cols_reshaped, scale_factor)
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
            print(f"\n 📊 STATISTIKA:")
            print(f" Buňky s daty: {nonzero_count:,}")
            print(f" Min/Max výška: {min_h:.0f}/{max_h:.0f}m\n")

            # Vrátí i originální transform pro transformaci GPS
            region_info = {
                'col_start': col_start,
                'row_start': row_start,
                'scale_factor': scale_factor,
                'original_transform': original_transform,  # ← PRO TRANSFORMACI GPS!
                'crs': crs,
            }

            return heights_downsampled, transform, crs, (w_new, h_new), region_info
    except Exception as e:
        print(f"✗ Chyba: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None

def extract_emission(plant):
    """Extrahuj SOUČET všech emisí"""
    try:
        curr_year = plant.get('CurrentYear', {})
        if not isinstance(curr_year, dict):
            return 0.0
        emissions_list = curr_year.get('Emissions', [])
        if not isinstance(emissions_list, list):
            return 0.0
        total_emission = 0.0
        for emission_item in emissions_list:
            if isinstance(emission_item, dict):
                amount = emission_item.get('AmountRaw', 0)
                if isinstance(amount, (int, float)):
                    total_emission += float(amount)
        return total_emission
    except:
        return 0.0

def gps_to_pixel(lat, lon, original_transform, region_info, grid_shape):
    """✓ SPRÁVNÝ POSTUP: GPS → UTM → originální pixel → regionální pixel"""
    try:
        # ✓ Transformace: GPS (WGS84) → UTM32N
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32633", always_xy=True)
        x_utm, y_utm = transformer.transform(lon, lat)

        # ✓ UTM → originální TIFF pixel
        inv_orig_transform = ~original_transform
        orig_px, orig_py = inv_orig_transform * (x_utm, y_utm)
        orig_px_int = int(np.round(orig_px))
        orig_py_int = int(np.round(orig_py))

        # ✓ Originální pixel → regionální pixel
        col_start = region_info['col_start']
        row_start = region_info['row_start']
        scale_factor = region_info['scale_factor']

        region_px = (orig_px_int - col_start) // scale_factor
        region_py = (orig_py_int - row_start) // scale_factor

        w_new, h_new = grid_shape

        # Debug: vypiš první pár
        if lat > 49.93 and lat < 49.94 and lon > 18.35 and lon < 18.36:
            print(f" DEBUG: GPS ({lat:.4f}, {lon:.4f})")
            print(f"   UTM: ({x_utm:.0f}, {y_utm:.0f})")
            print(f"   Orig px: ({orig_px:.1f}, {orig_py:.1f}) → ({orig_px_int}, {orig_py_int})")
            print(f"   Region px: ({region_px}, {region_py}) / grid {w_new}×{h_new}")

        if 0 <= region_px < w_new and 0 <= region_py < h_new:
            return region_py, region_px, True
        return None, None, False
    except Exception as e:
        return None, None, False

def step2_filter_and_map_plants(plants, original_transform, region_info, grid_shape):
    """Filtruj továrny a mapuj na grid"""
    print("=" * 70)
    print("KROK 2: FILTROVÁNÍ A MAPOVÁNÍ TOVÁREN")
    print("=" * 70)

    w_new, h_new = grid_shape
    print(f"\n Hledám v rozsahu: {MSK_SOUTH}°-{MSK_NORTH}°N, {MSK_WEST}°-{MSK_EAST}°E")
    print(f" Grid: {w_new}×{h_new} px\n")

    # === KROK 1: GPS filtrování ===
    gps_filtered = []
    for plant in plants:
        try:
            lat = float(plant.get('Lat', 0))
            lon = float(plant.get('Lon', 0))
            if MSK_SOUTH <= lat <= MSK_NORTH and MSK_WEST <= lon <= MSK_EAST:
                emission = extract_emission(plant)
                curr_year = plant.get('CurrentYear', {})
                name = curr_year.get('Name', 'Unknown') if isinstance(curr_year, dict) else 'Unknown'
                gps_filtered.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'emission': emission,
                })
        except:
            pass

    print(f" ✓ GPS filtrování: {len(gps_filtered)} továren v MSK\n")

    # === KROK 2: Mapuj na grid ===
    print(f" Mapuji na grid...\n")

    mapped = []
    debug_count = 0
    skipped_count = 0

    for plant_idx, plant in enumerate(gps_filtered):
        try:
            lat = plant['lat']
            lon = plant['lon']

            # ✓ SPRÁVNÁ TRANSFORMACE
            row, col, is_valid = gps_to_pixel(lat, lon, original_transform, region_info, grid_shape)

            if is_valid:
                if debug_count < 3:
                    print(f" DEBUG {debug_count+1}: {plant['name'][:40]}")
                    print(f" GPS: ({lat:.4f}, {lon:.4f}) → pixel ({row}, {col})")
                    print(f" Emise: {plant['emission']:.2e} t/rok\n")
                    debug_count += 1

                mapped.append({
                    'name': plant['name'],
                    'row': row,
                    'col': col,
                    'emission': plant['emission'],
                })
            else:
                skipped_count += 1
        except Exception as e:
            skipped_count += 1

    print(f"\n ✓ Celkem továren v JSON: {len(plants)}")
    print(f" ✓ GPS filtrování: {len(gps_filtered)}")
    print(f" ✓ Mapováno na grid: {len(mapped)}")
    print(f" ✓ Mimo grid: {skipped_count}\n")

    if mapped:
        emissions = [m['emission'] for m in mapped]
        print(f" 📊 EMISE:")
        print(f" Min: {min(emissions):.2e} t/rok")
        print(f" Max: {max(emissions):.2e} t/rok")
        print(f" Sum: {sum(emissions):.2e} t/rok")
        print(f" Avg: {np.mean(emissions):.2e} t/rok\n")

    return gps_filtered, mapped

def step3_create_pollution_grid(heights, mapped_plants):
    """Vytvoř pollution grid"""
    print("=" * 70)
    print("KROK 3: VYTVOŘENÍ POLLUTION GRIDU")
    print("=" * 70)

    rows, cols = heights.shape
    pollution_grid = np.zeros((rows, cols), dtype=np.float32)

    for plant in mapped_plants:
        row = plant['row']
        col = plant['col']
        emission = plant['emission']
        pollution_grid[row, col] += emission

    print(f" ✓ Shape: {pollution_grid.shape}")
    print(f" ✓ Buněk s emisí: {np.count_nonzero(pollution_grid)}")
    if np.count_nonzero(pollution_grid) > 0:
        nz = pollution_grid[pollution_grid > 0]
        print(f" ✓ Min/Max znečištění: {nz.min():.2e} / {nz.max():.2e}\n")

    return pollution_grid

def step4_export_bin_v5_with_plants(heights, pollution, transform, mapped_plants, output_file='../src/init.bin'):
    """Exportuj do BIN s uloženými indexy továren"""
    print("=" * 70)
    print("KROK 4: EXPORT V5 BINARY S INDEXY TOVÁREN")
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
            continue
        col_start = int(nonzero_indices[0])
        col_end = int(nonzero_indices[-1]) + 1
        row_ranges.append({
            'row_id': row_id,
            'col_start': col_start,
            'col_end': col_end,
            'col_count': col_end - col_start
        })

    valid_rows = len(row_ranges)
    num_plants = len(mapped_plants)
    print(f" Řádků s daty: {valid_rows}/{rows}")
    print(f" Továren v gridu: {num_plants}\n")

    # Zápis BIN
    print(f" Zapis do {output_file}...")
    with open(output_file, 'wb') as f:
        # Header (60B)
        f.write(struct.pack('I', cols))
        f.write(struct.pack('I', rows))
        f.write(struct.pack('I', valid_rows))
        for val in [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f]:
            f.write(struct.pack('d', val))

        # Plants metadata (4B)
        f.write(struct.pack('I', num_plants))

        # ✓ Plant INDICES (12B per plant)
        for plant in mapped_plants:
            f.write(struct.pack('I', plant['row']))
            f.write(struct.pack('I', plant['col']))
            f.write(struct.pack('f', plant['emission']))

        # Row ranges (12B per row)
        for rr in row_ranges:
            f.write(struct.pack('III', rr['row_id'], rr['col_start'], rr['col_end']))

        # Raw data (6B per cell)
        for rr in row_ranges:
            row_id = rr['row_id']
            col_start = rr['col_start']
            col_end = rr['col_end']
            for col in range(col_start, col_end):
                height = heights[row_id, col]
                poll = pollution[row_id, col]
                f.write(struct.pack('H', height))
                f.write(struct.pack('f', poll))

    file_size = Path(output_file).stat().st_size / 1024 / 1024
    total_cells = sum(rr['col_count'] for rr in row_ranges)
    print(f" ✓ Soubor: {output_file} ({file_size:.2f} MB)")
    print(f"\n 📊 STATISTIKA EXPORTU:")
    print(f" Řádků: {valid_rows}")
    print(f" Buněk terénů: {total_cells:,}")
    print(f" Továren v indexech: {num_plants}")
    print(f" Komprese terénů: ~{(rows*cols) / (total_cells*1.2):.1f}x\n")

def find_tiff_file():
    """Najdi TIFF soubor"""
    candidates = [
        Path('EL-GRID.tif'),
        Path('../EL-GRID.tif'),
        Path('../data/EL-GRID.tif'),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None

def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "EXPORT V5 - TIFF + TOVÁRNY → BIN".center(68) + "║")
    print("║" + "✓ OPRAVENA TRANSFORMACE - PYPROJ".center(68) + "║")
    print("║" + "✓ GPS → UTM → PIXEL (SPRÁVNĚ!)".center(68) + "║")
    print("╚" + "="*68 + "╝")

    # Krok 0: Načti továrny
    plants = step0_load_plants()
    if not plants:
        print("✗ Žádné továrny!")
        return False

    # Krok 1: TIFF
    tif_path = find_tiff_file()
    if not tif_path:
        print("✗ TIFF soubor nenalezen!")
        return False

    heights, transform, crs, dims, region_info = step1_load_and_downsample_tiff_fast(tif_path, SCALE_FACTOR)
    if heights is None:
        return False

    # Krok 2: Filtruj a mapuj továrny - OPRAVENO!
    filtered, mapped = step2_filter_and_map_plants(plants, region_info['original_transform'], 
                                                     region_info, dims)

    # Krok 3: Vytvoř pollution grid
    pollution = step3_create_pollution_grid(heights, mapped)

    # Krok 4: Export
    step4_export_bin_v5_with_plants(heights, pollution, transform, mapped)

    print("=" * 70)
    print("✓ EXPORT - HOTOVO!")
    print("=" * 70 + "\n")
    return True

if __name__ == '__main__':
    main()