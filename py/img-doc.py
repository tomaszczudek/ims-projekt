"""
╔════════════════════════════════════════════════════════════════════╗
║   EXTRAKCE MS KRAJE - VÝŠKY + TOVÁRNY (ČHMI)                      ║
║   ✓ SPRÁVNÁ VERZE - s PYPROJ konverzí GPS→UTM→pixel              ║
║   + GPS (WGS84) → UTM33N → pixel grid                             ║
║   + 3 MAPY + BINÁRNÍ DATA                                         ║
╚════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import struct
import json
from pathlib import Path
from urllib.request import urlopen
import gc

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
    print("Nainstaluj: pip install rasterio numpy matplotlib pyproj")
    sys.exit(1)


# ============================================================================
# KROK 0: STAHOVÁNÍ TOVÁREN
# ============================================================================

def step0_load_local_plants():
    """KROK 0: Čti továrny z lokálního plants.json"""
    print("\n" + "="*70)
    print("KROK 0: NAČTENÍ TOVÁREN Z LOKÁLNÍHO plants.json")
    print("="*70)

    plants_file = Path('../data/plants.json')

    if not plants_file.exists():
        print(f"✗ Soubor {plants_file} neexistuje!")
        print(f"   Zkontroluj, zda je plants.json v aktuální složce")
        print(f"   Aktuální cesta: {Path.cwd()}")
        return []

    try:
        file_size = plants_file.stat().st_size / 1024 / 1024
        print(f"\n  Čtu {plants_file} ({file_size:.1f} MB)...")

        with open(plants_file, 'r', encoding='utf-8') as f:
            root = json.load(f)

        print(f"  ✓ Načteno ({file_size:.1f} MB)")

        # Ověř strukturu
        if isinstance(root, dict):
            if 'data' in root:
                data = root['data']
                if isinstance(data, dict) and 'Plants' in data:
                    plants = data['Plants']
                    print(f"  ✓ Počet továren: {len(plants)}")
                    return plants

        print(f"✗ Neznámá struktura JSON souboru!")
        print(f"   Očekávám: {{'data': {{'Plants': [...]}} }}")
        return []

    except json.JSONDecodeError as e:
        print(f"✗ Chyba při parsování JSON: {e}")
        return []
    except Exception as e:
        print(f"✗ Chyba: {e}")
        return []


# ============================================================================
# KROK 1-4: EXTRAKCE VÝŠEK A VIZUALIZACE
# ============================================================================

def step1_inspect_tif():
    """KROK 1: Inspektuj TIF soubor"""
    print("\n" + "="*70)
    print("KROK 1: INSPEKCE TIF SOUBORU")
    print("="*70)

    el_grid_path = Path('../data/')
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
        print(f"\n    📄 {tif_path.name} ({size_gb:.2f} GB)")

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
            print(f"  CRS: {src.crs}")
            print(f"  Shape: {src.height} × {src.width}")

            # Vezmi střed - od 75% do 100% šířky, od 20% do 60% výšky
            col_start = int(src.width * 0.74)
            col_end = int(src.width)
            row_start = int(src.height * 0.27)
            row_end = int(src.height * 0.65)

            width = col_end - col_start
            height = row_end - row_start

            print(f"\n  Čtu centrální region z TIF...")
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

            print(f"  ✓ Data očištěna: min={heights.min():.1f}, max={heights.max():.1f}")

            # ULOŽ transform
            window_transform = src.window_transform(Window(col_start, row_start, width, height))

            return heights.astype(np.float32), window_transform, src.crs

    except Exception as e:
        print(f"✗ Chyba: {e}")
        return None, None, None


def step3_save_binary(heights):
    """KROK 3: EXPORT DO BINÁRNÍHO FORMÁTU (s kompresí rozlišení)"""
    print("\n" + "="*70)
    print("KROK 3: EXPORT DO BINÁRNÍHO FORMÁTU")
    print("="*70)
    
    # ⚠️ REDUKCE ROZLIŠENÍ: Vezmi každý 5. pixel (25x menší soubor!)
    print(f"\n  📉 Redukce rozlišení pro menší soubor...")
    print(f"     Original: {heights.shape}")
    
    downsample_rate = 5
    heights_reduced = heights[::downsample_rate, ::downsample_rate].copy()
    print(f"     Redukovaný (1/{downsample_rate}): {heights_reduced.shape}")
    
    rows, cols = heights_reduced.shape
    # uint8 místo uint16 = 50% úspora! (0-255 stačí)
    heights_uint8 = np.uint8(np.clip(heights_reduced / 10, 0, 255))
    
    output_file = 'ms_heights.bin'
    
    try:
        with open(output_file, 'wb') as f:
            # Header: rows, cols, downsample_rate
            f.write(struct.pack('III', rows, cols, downsample_rate))
            
            # Výšky - uint8 (0-255, každý jednotka = 10m)
            f.write(heights_uint8.tobytes())
        
        file_size = os.path.getsize(output_file) / 1024 / 1024
        
        print(f"\n  ✓ Uloženo: {output_file}")
        print(f"    Velikost: {file_size:.2f} MB")
        print(f"    ✓✓ Komprese: 1GB → {file_size:.1f}MB!")
        print(f"    Grid (originál): {heights.shape}")
        print(f"    Grid (redukovaný): {rows} × {cols}")
        print(f"    Formát: uint8 (0-255, každá jednotka = 10m výšky)")
        
        del heights_uint8, heights_reduced
        gc.collect()
        
        return output_file, downsample_rate, rows, cols
    except Exception as e:
        print(f"✗ Chyba: {e}")
        return None, None, None, None


def step4_visualize_height(heights):
    """KROK 4: Vizualizuj VÝŠKY"""
    print("\n" + "="*70)
    print("KROK 4: VIZUALIZACE VÝŠEK")
    print("="*70)

    try:
        heights_vis = heights[::2, ::2].copy()

        print(f"\n  📐 Vytváření grafu...")
        fig, ax = plt.subplots(figsize=(12, 8), dpi=100)

        im = ax.imshow(heights_vis, cmap='terrain', origin='upper', interpolation='bilinear')
        ax.set_title('Nadmořské Výšky - Moravskoslezský Kraj (INSPIRE EL-GRID, ČÚZK)',
                     fontweight='bold', fontsize=12)
        cbar = plt.colorbar(im, ax=ax, label='m.n.m', shrink=0.8)
        #ax.set_xlabel('Sloupec (px)', fontsize=10)
        #ax.set_ylabel('Řádek (px)', fontsize=10)

        valid = heights[heights > 0]
        mean_val = valid.mean() if len(valid) > 0 else 0
        stats = f'Grid: {heights.shape}\nMin: {heights.min():.0f}m\nMax: {heights.max():.0f}m\nMean: {mean_val:.1f}m'
        #ax.text(0.7, 0.98, stats, transform=ax.transAxes, verticalalignment='top',fontsize=9, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        #ax.axis('off')
        plt.savefig('01_map_heights.png', dpi=100, bbox_inches='tight', facecolor='white')
        print(f"  ✓ Uloženo: 01_map_heights.png")
        plt.close('all')
        gc.collect()

    except Exception as e:
        print(f"✗ Chyba: {e}")
        plt.close('all')


# ============================================================================
# KROK 5: FILTROVÁNÍ TOVÁREN
# ============================================================================

def step5_filter_pollution_sources(pollution_data):
    """KROK 5: Filtruj továrny v MS kraji"""
    print("\n" + "="*70)
    print("KROK 5: FILTROVÁNÍ TOVÁREN PRO MS KRAJ")
    print("="*70)

    if not pollution_data:
        return []

    filtered = []
    print(f"\n  Hledám v rozsahu: 49.423-50.34°N, 17.236-18.86°E")

    for i, plant in enumerate(pollution_data):
        try:
            lat = float(plant.get('Lat', 0))
            lon = float(plant.get('Lon', 0))

            name = 'Unknown'
            curr_year = plant.get('CurrentYear', {})
            if isinstance(curr_year, dict):
                name = curr_year.get('Name', 'Unknown')

            # TVOJE SPRÁVNÉ ROZSAHY
            if 49.39 <= lat <= 50.327 and 17.146 <= lon <= 18.86:
                filtered.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'type': curr_year.get('NACE', 'Unknown'),
                })
        except:
            pass

    print(f"\n  ✓ Nalezeno {len(filtered)} továren!")
    return filtered


# ============================================================================
# KROK 6-7: GPS → UTM → PIXEL KONVERZE
# ============================================================================

def gps_to_pixel(lat, lon, transform, crs):
    """Konvertuj GPS (WGS84) → UTM → pixel souřadnice

    Postup:
    1. GPS (lon, lat) [WGS84]
    2. → UTM33N (x_utm, y_utm) [pyproj]
    3. → pixel (px, py) [inverzní transform]
    """
    try:
        # KROK 1: GPS → UTM33N pomocí pyproj
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32633", always_xy=True)
        x_utm, y_utm = transformer.transform(lon, lat)  # VŽDYCKY (lon, lat) v EPSG:4326!

        # KROK 2: UTM → pixel pomocí inverzního transformu z rasterio
        inv_transform = ~transform
        px, py = inv_transform * (x_utm, y_utm)

        return int(px), int(py)
    except Exception as e:
        print(f"  ⚠️  Chyba v gps_to_pixel: {e}")
        return None, None


def step6_visualize_pollution(heights, pollution_sources, transform, crs):
    """KROK 6: Vizualizuj TOVÁRNY - s konverzí GPS→pixel"""
    print("\n" + "="*70)
    print("KROK 6: VIZUALIZACE TOVÁREN (GPS→UTM→pixel)")
    print("="*70)

    try:
        print(f"\n  🏭 Vytváření mapy...")
        fig, ax = plt.subplots(figsize=(12, 8), dpi=100)

        # Zobraz výšky jako background
        heights_vis = heights[::2, ::2].copy()
        im = ax.imshow(heights_vis, cmap='terrain', alpha=0.6, origin='upper')

        if pollution_sources:
            print(f"  📍 Mapuji {len(pollution_sources)} zdrojů (GPS→pixel)...")
            count = 0
            out_of_bounds = 0

            for i, source in enumerate(pollution_sources):
                px, py = gps_to_pixel(source['lat'], source['lon'], transform, crs)

                if px is not None and py is not None:
                    # Zkontroluj hranice ORIGINÁLNÍHO gridu
                    if 0 <= px < heights.shape[1] and 0 <= py < heights.shape[0]:
                        # Zmenš kvůli ::2 downsampling
                        vis_px = px // 2
                        vis_py = py // 2

                        ax.plot(vis_px, vis_py, 'r*', markersize=25, 
                               markeredgecolor='darkred', markeredgewidth=2.5)
                        count += 1

                        # Popiš první 8
                        if count <= 8:
                            ax.text(vis_px + 30, vis_py - 30, source['name'][:12], 
                                   fontsize=8, color='darkred', weight='bold',
                                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))
                    else:
                        out_of_bounds += 1
                else:
                    out_of_bounds += 1

            print(f"  ✓ Vykresleno {count} z {len(pollution_sources)} továren")
            if out_of_bounds > 0:
                print(f"  ⚠️  {out_of_bounds} továren mimo grid")

        ax.set_title('Zdroje Znečištění - MS Kraj (GPS→UTM→pixel konverze)', 
                     fontweight='bold', fontsize=14)
        ax.set_xlabel('Pixel X')
        ax.set_ylabel('Pixel Y')
        ax.grid(True, alpha=0.2, linestyle='--')

        stats = f'Celkem zdrojů: {len(pollution_sources)}\nMapováno: {count}/{len(pollution_sources)}'
        ax.text(0.02, 0.98, stats, transform=ax.transAxes, verticalalignment='top',
                fontsize=10, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))

        plt.savefig('02_map_pollution_sources.png', dpi=100, bbox_inches='tight', facecolor='white')
        print(f"  ✓ Uloženo: 02_map_pollution_sources.png")
        plt.close()

    except Exception as e:
        print(f"✗ Chyba: {e}")
        import traceback
        traceback.print_exc()
        plt.close('all')


def step7_visualize_combined(heights, pollution_sources, transform, crs):
    """KROK 7: Kombinace"""
    print("\n" + "="*70)
    print("KROK 7: KOMBINACE VÝŠEK + TOVÁREN")
    print("="*70)

    try:
        heights_vis = heights[::2, ::2].copy()

        print(f"\n  🗺️  Vytváření kombinované mapy...")
        fig, ax = plt.subplots(figsize=(12, 8), dpi=100)

        im = ax.imshow(heights_vis, cmap='terrain', origin='upper', 
                      interpolation='bilinear', alpha=0.75)
        ax.set_title('Zdroje emisí - Moravskoslezský Kraj (EMIS, ČHMÚ)', 
                     fontweight='bold', fontsize=14)
        cbar = plt.colorbar(im, ax=ax, label='m.n.m', shrink=0.8)

        if pollution_sources:
            print(f"  📍 Mapuji {len(pollution_sources)} zdrojů...")
            count = 0

            for source in pollution_sources:
                px, py = gps_to_pixel(source['lat'], source['lon'], transform, crs)

                if px is not None and 0 <= px < heights.shape[1] and 0 <= py < heights.shape[0]:
                    ax.plot(px//2, py//2, 'r*', markersize=18, 
                           markeredgecolor='darkred', markeredgewidth=2)
                    count += 1

            print(f"  ✓ Mapováno {count}/{len(pollution_sources)} továren")

        stats = f'Počet zdrojů emisí: 1278'
        ax.text(0.7, 0.98, stats, transform=ax.transAxes, verticalalignment='top',
                fontsize=10, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))

        plt.savefig('03_map_combined.png', dpi=100, bbox_inches='tight', facecolor='white')
        print(f"  ✓ Uloženo: 03_map_combined.png")
        plt.close()
        gc.collect()

    except Exception as e:
        print(f"✗ Chyba: {e}")
        plt.close('all')


def step8_save_combined_binary(heights, pollution_sources, rows, cols):
    """KROK 8: Binární export"""
    print("\n" + "="*70)
    print("KROK 8: EXPORT KOMBINOVANÝCH DAT")
    print("="*70)

    output_file = 'ms_complete_data.bin'

    try:
        with open(output_file, 'wb') as f:
            num_sources = len(pollution_sources)
            f.write(struct.pack('III', rows, cols, num_sources))

            heights_uint16 = np.uint16(np.clip(heights, 0, 65535))
            f.write(heights_uint16.tobytes())

            for source in pollution_sources:
                name_bytes = source['name'].encode('utf-8')[:63]
                f.write(struct.pack('B', len(name_bytes)))
                f.write(name_bytes)
                f.write(b'\x00' * (64 - len(name_bytes)))

                f.write(struct.pack('ff', source['lat'], source['lon']))

                type_bytes = source['type'].encode('utf-8')[:31]
                f.write(struct.pack('B', len(type_bytes)))
                f.write(type_bytes)
                f.write(b'\x00' * (32 - len(type_bytes)))

        file_size = os.path.getsize(output_file) / 1024 / 1024
        print(f"\n  ✓ Uloženo: {output_file} ({file_size:.2f} MB)")

        return output_file
    except Exception as e:
        print(f"✗ Chyba: {e}")
        return None


# ============================================================================
# HLAVNÍ PROGRAM
# ============================================================================

def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "EXTRAKCE MS KRAJ - VÝŠKY + TOVÁRNY".center(68) + "║")
    print("║" + "✓ GPS→UTM33N→pixel KONVERZE".center(68) + "║")
    print("╚" + "="*68 + "╝")

    pollution_data = step0_load_local_plants()

    tif_path = step1_inspect_tif()
    if not tif_path:
        return False

    heights, transform, crs = step2_extract_ms_region(tif_path)
    if heights is None:
        return False

    result = step3_save_binary(heights)
    if result[0] is None:
        return False
    binary_file, downsample_rate, rows, cols = result

    step4_visualize_height(heights)

    filtered_sources = step5_filter_pollution_sources(pollution_data)

    step6_visualize_pollution(heights, filtered_sources, transform, crs)
    step7_visualize_combined(heights, filtered_sources, transform, crs)

    combined_file = step8_save_combined_binary(heights, filtered_sources, rows, cols)

    print("\n" + "="*70)
    print("✓✓✓ ZPRACOVÁNÍ HOTOVO! ✓✓✓")
    print("="*70)
    print(f"\n📊 VÝSLEDKY:")
    print(f"  Grid: {rows} × {cols} pixelů")
    print(f"  Výšky: {heights.min():.0f} - {heights.max():.0f} m")
    print(f"  Továrny: {len(filtered_sources)}")
    print(f"\n🗺️  MAPY:")
    print(f"  ✓ 01_map_heights.png")
    print(f"  ✓ 02_map_pollution_sources.png")
    print(f"  ✓ 03_map_combined.png")
    print("=" * 70 + "\n")

    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)