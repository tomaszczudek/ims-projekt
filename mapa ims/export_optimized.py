#!/usr/bin/env python3
"""
╔════════════════════════════════════════════════════════════════════╗
║   OPTIMALIZOVANÝ EXPORT MS KRAJE PRO C++                           ║
║   ✓ Komprese 2D pole bez mrtvých zón (modrá plocha)               ║
║   + Znečištění v TUNÁCH za rok                                    ║
║   + Row ranges pro efektivní přístup                              ║
╚════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import struct
import json
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    from pyproj import Transformer
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError as e:
    print(f"✗ Chybí balíček: {e}")
    sys.exit(1)


# ============================================================================
# KROK 0: NAČTENÍ TOVÁREN
# ============================================================================

def step0_load_local_plants():
    """KROK 0: Čti továrny z lokálního plants.json"""
    print("\n" + "="*70)
    print("KROK 0: NAČTENÍ TOVÁREN Z LOKÁLNÍHO plants.json")
    print("="*70)

    plants_file = Path('plants.json')

    if not plants_file.exists():
        print(f"✗ Soubor {plants_file} neexistuje!")
        print(f"   Zkontroluj, zda je plants.json v aktuální složce")
        return []

    try:
        file_size = plants_file.stat().st_size / 1024 / 1024
        print(f"\n  Čtu {plants_file} ({file_size:.1f} MB)...")

        with open(plants_file, 'r', encoding='utf-8') as f:
            root = json.load(f)

        print(f"  ✓ Načteno ({file_size:.1f} MB)")

        if isinstance(root, dict):
            if 'data' in root:
                data = root['data']
                if isinstance(data, dict) and 'Plants' in data:
                    plants = data['Plants']
                    print(f"  ✓ Počet továren: {len(plants)}")
                    return plants

        return []

    except Exception as e:
        print(f"✗ Chyba: {e}")
        return []


# ============================================================================
# KROK 1-2: EXTRAKCE VÝŠEK
# ============================================================================

def step1_inspect_tif():
    """KROK 1: Inspektuj TIF soubor"""
    print("\n" + "="*70)
    print("KROK 1: INSPEKCE TIF SOUBORU")
    print("="*70)

    el_grid_path = Path('macbook-data')
    if not el_grid_path.exists():
        print("✗ EL_GRID_DATA neexistuje!")
        return None

    tif_files = sorted(el_grid_path.glob('*.tif'))
    if not tif_files:
        print("✗ Žádné TIF soubory!")
        return None

    print(f"\n  Nalezeno TIF souborů: {len(tif_files)}")

    for tif_path in tif_files:
        size_gb = tif_path.stat().st_size / 1024 / 1024 / 1024
        print(f"    📄 {tif_path.name} ({size_gb:.2f} GB)")

        try:
            with rasterio.open(str(tif_path)) as src:
                print(f"       CRS: {src.crs}")
                print(f"       Shape: {src.height} × {src.width}")
                return tif_path
        except Exception as e:
            print(f"       ✗ Chyba: {e}")

    return None


def step2_extract_ms_region(tif_path):
    """KROK 2: Extrahuj MS kraj"""
    print("\n" + "="*70)
    print("KROK 2: EXTRAKCE MORAVSKOSLEZSKÉHO KRAJE")
    print("="*70)

    try:
        with rasterio.open(str(tif_path)) as src:
            print(f"\n  Čtu soubor: {tif_path.name}")

            col_start = int(src.width * 0.74)
            col_end = int(src.width)
            row_start = int(src.height * 0.27)
            row_end = int(src.height * 0.65)

            width = col_end - col_start
            height = row_end - row_start

            print(f"  Čtu region: {width}×{height} pixelů...")
            heights = src.read(1, window=Window(col_start, row_start, width, height))

            print(f"  ✓ Data načtena: {heights.shape}")

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

            print(f"  ✓ Data očištěna: {heights.min():.0f}-{heights.max():.0f}m")

            window_transform = src.window_transform(Window(col_start, row_start, width, height))

            return heights.astype(np.float32), window_transform, src.crs

    except Exception as e:
        print(f"✗ Chyba: {e}")
        return None, None, None


# ============================================================================
# KROK 3: FILTROVÁNÍ TOVÁREN
# ============================================================================

def step3_filter_pollution_sources(pollution_data):
    """KROK 3: Filtruj továrny v MS kraji"""
    print("\n" + "="*70)
    print("KROK 3: FILTROVÁNÍ TOVÁREN PRO MS KRAJ")
    print("="*70)

    if not pollution_data:
        return []

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
                    'plant_data': plant  # Ulož originální data pro znečištění
                })
        except:
            pass

    print(f"  ✓ Nalezeno {len(filtered)} továren!")
    return filtered


# ============================================================================
# KROK 4: EXTRAKCE ZNEČIŠTĚNÍ V TUNÁCH
# ============================================================================

def extract_pollution_tons(plant_data):
    """Vyjmi znečištění v tunách za rok z JSON"""
    try:
        curr_year = plant_data.get('CurrentYear', {})
        if isinstance(curr_year, dict):
            # Zkus různé klíče
            emissions = (curr_year.get('Emissions', 0) or 
                        curr_year.get('TotalEmissions', 0) or
                        curr_year.get('Pollution', 0))
            return float(emissions) if emissions else 0.0
        return 0.0
    except:
        return 0.0


# ============================================================================
# KROK 5: GPS → PIXEL KONVERZE
# ============================================================================

def gps_to_pixel(lat, lon, transform):
    """Konvertuj GPS → UTM → pixel"""
    try:
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32633", always_xy=True)
        x_utm, y_utm = transformer.transform(lon, lat)
        inv_transform = ~transform
        px, py = inv_transform * (x_utm, y_utm)
        return int(px), int(py)
    except:
        return None, None


# ============================================================================
# KROK 6: OPTIMALIZOVANÝ BINÁRNÍ EXPORT S KOMPRESÍ
# ============================================================================

def step6_optimized_binary_export(heights, pollution_sources, transform, 
                                   output_file='terrain_data.bin'):
    """
    OPTIMALIZOVANÝ BINÁRNÍ EXPORT

    Komprimuje 2D pole tak, že ukládá pouze řádky s daty
    a pro každý řádek informaci: col_start, col_end
    """

    print("\n" + "="*70)
    print("KROK 6: OPTIMALIZOVANÝ BINÁRNÍ EXPORT")
    print("="*70)

    rows, cols = heights.shape

    # === Analýza řádků ===
    print(f"\n  📊 Analýza řádků (detekce nul)...")

    row_ranges = []
    for row_id in range(rows):
        row_data = heights[row_id, :]

        # Najdi nenulové prvky
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

    # === Zápis do binárního souboru ===
    print(f"\n  📝 Zapis binárního souboru...")

    with open(output_file, 'wb') as f:
        # HEADER (20 bytes)
        f.write(struct.pack('I', rows))
        f.write(struct.pack('I', cols))
        f.write(struct.pack('I', len(pollution_sources)))
        f.write(struct.pack('I', len(row_ranges)))
        f.write(struct.pack('I', 1))  # Format version

        print(f"    ✓ Header (20 bytes)")

        # ROW RANGES
        print(f"    ✓ Row ranges ({len(row_ranges)} záznamů)...")
        for r in row_ranges:
            f.write(struct.pack('III H', r['row_id'], r['col_start'], r['col_end'], r['col_count']))

        # HEIGHT DATA
        print(f"    ✓ Height data ({len(row_ranges)} řádků)...")
        for r in row_ranges:
            f.write(r['data'].tobytes())

        # PLANTS
        print(f"\n  🏭 Zapis {len(pollution_sources)} továren...")

        valid_plants = 0
        for i, source in enumerate(pollution_sources):
            px, py = gps_to_pixel(source['lat'], source['lon'], transform)

            if px is None or not (0 <= px < cols and 0 <= py < rows):
                continue

            # Vyhledej znečištění v tunách
            pollution_tons = extract_pollution_tons(source['plant_data'])

            # Zapis továrnu
            f.write(struct.pack('f', source['lat']))
            f.write(struct.pack('f', source['lon']))
            f.write(struct.pack('I', px))
            f.write(struct.pack('I', py))
            f.write(struct.pack('f', pollution_tons))  # TUNY!

            name = source['name'][:63].encode('utf-8')
            f.write(struct.pack('H', len(name)))
            f.write(name)

            plant_type = source['type'][:31].encode('utf-8')
            f.write(struct.pack('H', len(plant_type)))
            f.write(plant_type)

            valid_plants += 1

            if valid_plants % 50 == 0:
                print(f"    {valid_plants}/{len(pollution_sources)}...")

        print(f"    ✓ Uloženo {valid_plants} továren")

    file_size = Path(output_file).stat().st_size / 1024 / 1024
    print(f"\n  ✓ Soubor uložen: {output_file}")
    print(f"    Velikost: {file_size:.2f} MB")
    print(f"    Komprese 2D pole: {compression_ratio:.1f}x")

    return output_file, len(row_ranges), valid_plants


# ============================================================================
# KROK 7: VIZUALIZACE
# ============================================================================

def step7_visualize(heights, pollution_sources, transform):
    """KROK 7: Vizualizuj výšky a továrny"""
    print("\n" + "="*70)
    print("KROK 7: VIZUALIZACE VÝŠEK")
    print("="*70)

    try:
        heights_vis = heights[::2, ::2].copy()
        fig, ax = plt.subplots(figsize=(12, 8), dpi=100)

        im = ax.imshow(heights_vis, cmap='terrain', origin='upper', interpolation='bilinear')
        ax.set_title('Nadmořské Výšky - MS Kraj (OPTIMALIZOVANÉ)', fontweight='bold', fontsize=12)
        cbar = plt.colorbar(im, ax=ax, label='m.n.m', shrink=0.8)

        # Ploti továrny
        for source in pollution_sources[:50]:  # Prvních 50
            px, py = gps_to_pixel(source['lat'], source['lon'], transform)
            if px and 0 <= px < heights.shape[1] and 0 <= py < heights.shape[0]:
                ax.plot(px//2, py//2, 'r*', markersize=15, markeredgecolor='darkred')

        valid = heights[heights > 0]
        mean_val = valid.mean() if len(valid) > 0 else 0
        stats = f'Grid: {heights.shape}\nMin: {heights.min():.0f}m\nMax: {heights.max():.0f}m\nMean: {mean_val:.1f}m\nTovárny: {len(pollution_sources)}'
        ax.text(0.02, 0.98, stats, transform=ax.transAxes, verticalalignment='top',
                fontsize=9, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        plt.savefig('01_map_optimized.png', dpi=100, bbox_inches='tight', facecolor='white')
        print(f"  ✓ Uloženo: 01_map_optimized.png")
        plt.close('all')

    except Exception as e:
        print(f"✗ Chyba: {e}")
        plt.close('all')


# ============================================================================
# HLAVNÍ PROGRAM
# ============================================================================

def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "OPTIMALIZOVANÝ EXPORT MS KRAJE PRO C++".center(68) + "║")
    print("║" + "Komprese bez mrtvých zón + Znečištění v tunách".center(68) + "║")
    print("╚" + "="*68 + "╝")

    pollution_data = step0_load_local_plants()
    if not pollution_data:
        return False

    tif_path = step1_inspect_tif()
    if not tif_path:
        return False

    heights, transform, crs = step2_extract_ms_region(tif_path)
    if heights is None:
        return False

    filtered_sources = step3_filter_pollution_sources(pollution_data)

    # Visualizuj
    step7_visualize(heights, filtered_sources, transform)

    # Exportuj optimalizovaně
    cpp_file, num_row_ranges, num_plants = step6_optimized_binary_export(
        heights, filtered_sources, transform
    )

    print("\n" + "="*70)
    print("✓✓✓ EXPORT HOTOV! ✓✓✓")
    print("="*70)
    print(f"\n📊 VÝSLEDKY:")
    print(f"  Grid: {heights.shape[0]} × {heights.shape[1]} pixelů")
    print(f"  Řádků s daty: {num_row_ranges}")
    print(f"  Továrny: {num_plants}")
    print(f"\n📦 VÝSTUPNÍ SOUBOR:")
    print(f"  {cpp_file}")
    print(f"\n💻 C++ LOADER:")
    print(f"  #include \"terrain_optimized.hpp\"")
    print(f"  TerrainDataOptimized terrain;")
    print(f"  terrain.loadFromBinary(\"{cpp_file}\");")
    print(f"  terrain.printStatistics();")
    print("=" * 70 + "\n")

    return True


if __name__ == '__main__':
    import gc
    success = main()
    gc.collect()
    sys.exit(0 if success else 1)
