#!/usr/bin/env python3
"""
EXPORT DO BINÁRNÍHO SOUBORU
Pouze export - bez obrázků!
"""

import struct
import json
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    from pyproj import Transformer
except ImportError as e:
    print(f"✗ Chybí balíček: {e}")
    exit(1)


def step0_load_local_plants():
    """Čti továrny z lokálního plants.json"""
    print("\n" + "="*70)
    print("KROK 0: NAČTENÍ TOVÁREN")
    print("="*70)
    
    plants_file = Path('plants.json')
    if not plants_file.exists():
        print(f"✗ Soubor {plants_file} neexistuje!")
        return []
    
    try:
        file_size = plants_file.stat().st_size / 1024 / 1024
        print(f"  Čtu {plants_file} ({file_size:.1f} MB)...")
        
        with open(plants_file, 'r', encoding='utf-8') as f:
            root = json.load(f)
        
        if isinstance(root, dict) and 'data' in root:
            data = root['data']
            if isinstance(data, dict) and 'Plants' in data:
                plants = data['Plants']
                print(f"  ✓ Počet továren: {len(plants)}")
                return plants
        
        return []
    except Exception as e:
        print(f"✗ Chyba: {e}")
        return []


def step1_extract_ms_region(tif_path):
    """Extrahuj MS kraj z TIF"""
    print("\n" + "="*70)
    print("KROK 1: EXTRAKCE VÝŠEK")
    print("="*70)
    
    try:
        with rasterio.open(str(tif_path)) as src:
            print(f"  Čtu soubor: {tif_path.name}")
            
            col_start = int(src.width * 0.74)
            col_end = int(src.width)
            row_start = int(src.height * 0.27)
            row_end = int(src.height * 0.65)
            
            width = col_end - col_start
            height = row_end - row_start
            
            print(f"  Region: {width}×{height} pixelů...")
            heights = src.read(1, window=Window(col_start, row_start, width, height))
            
            # Čistění
            heights = heights.astype(np.float32)
            nan_mask = np.isnan(heights)
            inf_mask = np.isinf(heights)
            nodata = src.nodata
            nodata_mask = (heights == nodata) if nodata is not None else np.zeros_like(heights, dtype=bool)
            extreme_mask = np.abs(heights) > 10000
            
            bad_mask = nan_mask | inf_mask | nodata_mask | extreme_mask
            heights[bad_mask] = 0
            heights[heights < -500] = 0
            heights[heights > 2500] = 0
            
            print(f"  ✓ Výšky: {heights.min():.0f}-{heights.max():.0f}m")
            
            window_transform = src.window_transform(Window(col_start, row_start, width, height))
            
            return heights.astype(np.float32), window_transform, src.crs
    
    except Exception as e:
        print(f"✗ Chyba: {e}")
        return None, None, None


def step2_filter_plants(pollution_data):
    """Filtruj továrny v MS kraji"""
    print("\n" + "="*70)
    print("KROK 2: FILTROVÁNÍ TOVÁREN")
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
            
            if 49.39 <= lat <= 50.327 and 17.146 <= lon <= 18.86:
                filtered.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'type': curr_year.get('NACE', 'Unknown') if isinstance(curr_year, dict) else 'Unknown',
                    'plant_data': plant
                })
        except:
            pass
    
    print(f"  ✓ Filtrováno: {len(filtered)} továren")
    return filtered


def extract_pollution_tons(plant_data):
    """Vyjmi znečištění v tunách za rok"""
    try:
        curr_year = plant_data.get('CurrentYear', {})
        if isinstance(curr_year, dict):
            emissions = (curr_year.get('Emissions', 0) or 
                        curr_year.get('TotalEmissions', 0) or
                        curr_year.get('Pollution', 0))
            return float(emissions) if emissions else 0.0
        return 0.0
    except:
        return 0.0


def gps_to_pixel(lat, lon, transform):
    """Konvertuj GPS → pixel"""
    try:
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32633", always_xy=True)
        x_utm, y_utm = transformer.transform(lon, lat)
        inv_transform = ~transform
        px, py = inv_transform * (x_utm, y_utm)
        return int(px), int(py)
    except:
        return None, None


def step3_export_to_bin(heights, pollution_sources, transform, output_file='terrain.bin'):
    """
    EXPORT DO OPTIMALIZOVANÉHO BIN SOUBORU
    
    Formát: HEADER + ROW_RANGES + HEIGHT_DATA + PLANTS
    """
    
    print("\n" + "="*70)
    print("KROK 3: EXPORT DO BIN SOUBORU")
    print("="*70)
    
    rows, cols = heights.shape
    
    # === Analýza řádků ===
    print(f"  📊 Analýza řádků...")
    
    row_ranges = []
    for row_id in range(rows):
        row_data = heights[row_id, :]
        nonzero_indices = np.where(row_data > 0)[0]
        
        if len(nonzero_indices) > 0:
            col_start = int(nonzero_indices[0])
            col_end = int(nonzero_indices[-1]) + 1
            col_count = col_end - col_start
            
            row_ranges.append({
                'row_id': row_id,
                'col_start': col_start,
                'col_end': col_end,
                'col_count': col_count,
                'data': row_data[col_start:col_end].astype(np.uint16)
            })
    
    data_size = sum(r['col_count'] * 2 for r in row_ranges)
    original_size = rows * cols * 2
    compression_ratio = original_size / data_size if data_size > 0 else 1.0
    
    print(f"    Řádků s daty: {len(row_ranges)}/{rows}")
    print(f"    Komprese: {original_size/1024/1024:.1f}MB → {data_size/1024/1024:.1f}MB ({compression_ratio:.1f}x)")
    
    # === Zápis ===
    print(f"  📝 Zapis do {output_file}...")
    
    with open(output_file, 'wb') as f:
        # HEADER (20 bytes)
        f.write(struct.pack('I', rows))
        f.write(struct.pack('I', cols))
        f.write(struct.pack('I', len(pollution_sources)))
        f.write(struct.pack('I', len(row_ranges)))
        f.write(struct.pack('I', 2))  # version = 2
        
        # ROW RANGES
        for r in row_ranges:
            f.write(struct.pack('III H', r['row_id'], r['col_start'], r['col_end'], r['col_count']))
        
        # HEIGHT DATA
        for r in row_ranges:
            f.write(r['data'].tobytes())
        
        # PLANTS
        print(f"    Zapis {len(pollution_sources)} továren...")
        valid_plants = 0
        
        for source in pollution_sources:
            px, py = gps_to_pixel(source['lat'], source['lon'], transform)
            
            if px is None or not (0 <= px < cols and 0 <= py < rows):
                continue
            
            pollution_tons = extract_pollution_tons(source['plant_data'])
            
            # Zapis továrnu
            f.write(struct.pack('f', source['lat']))
            f.write(struct.pack('f', source['lon']))
            f.write(struct.pack('I', px))
            f.write(struct.pack('I', py))
            f.write(struct.pack('f', pollution_tons))
            
            name = source['name'][:63].encode('utf-8')
            f.write(struct.pack('H', len(name)))
            f.write(name)
            
            plant_type = source['type'][:31].encode('utf-8')
            f.write(struct.pack('H', len(plant_type)))
            f.write(plant_type)
            
            valid_plants += 1
    
    file_size = Path(output_file).stat().st_size / 1024 / 1024
    print(f"  ✓ Uloženo: {output_file} ({file_size:.2f} MB)")
    print(f"    Továrny: {valid_plants}")
    
    return output_file


def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "EXPORT DO BINÁRNÍHO SOUBORU".center(68) + "║")
    print("╚" + "="*68 + "╝")
    
    # Najdi TIF soubor
    el_grid_path = Path('macbook-data')
    tif_files = sorted(el_grid_path.glob('*.tif')) if el_grid_path.exists() else []
    
    if not tif_files:
        print("✗ Žádné TIF soubory!")
        return False
    
    tif_path = tif_files[0]
    
    # Procesy
    pollution_data = step0_load_local_plants()
    if not pollution_data:
        return False
    
    heights, transform, crs = step1_extract_ms_region(tif_path)
    if heights is None:
        return False
    
    filtered_sources = step2_filter_plants(pollution_data)
    
    step3_export_to_bin(heights, filtered_sources, transform)
    
    print("\n" + "="*70)
    print("✓ EXPORT HOTOV!")
    print("="*70 + "\n")
    
    return True


if __name__ == '__main__':
    main()
