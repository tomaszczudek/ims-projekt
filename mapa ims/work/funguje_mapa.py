"""
╔════════════════════════════════════════════════════════════════════╗
║   EXTRAKCE MS KRAJE Z INSPIRE EL-GRID (UTM 33N/EPSG:25833)        ║
║              Nadmořské výšky → Binární formát → C++                ║
║           ✓ MEMORY OPTIMIZED - bez crash na Graphics              ║
╚════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import struct
from pathlib import Path
import gc

try:
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    import matplotlib
    matplotlib.use('Agg')  # ✓ Non-GUI backend - méně paměti!
    import matplotlib.pyplot as plt
except ImportError as e:
    print(f"✗ Chybí balíček: {e}")
    print("Nainstaluj: pip install rasterio numpy matplotlib")
    sys.exit(1)


def step1_inspect_tif():
    """KROK 1: Inspektuj TIF soubor"""
    print("\n" + "="*70)
    print("KROK 1: INSPEKCE TIF SOUBORU")
    print("="*70)
    
    el_grid_path = Path('../EL_GRID_DATA')
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
                print(f"       CRS: {src.crs} (EPSG:{src.crs.to_epsg() if src.crs else 'N/A'})")
                print(f"       Shape: {src.height} × {src.width}")
                print(f"       Dtype: {src.dtypes[0]}")
                print(f"       Bounds: {src.bounds}")
                print(f"       Res: {src.res}")
                print(f"       Bandů: {src.count}")
                print(f"       NoData value: {src.nodata}")
                
                return tif_path
        except Exception as e:
            print(f"       ✗ Chyba: {e}")
    
    return None


def step2_extract_ms_region(tif_path):
    """KROK 2: Extrahuj MS kraj - ČTENÍ ZE STŘEDU"""
    print("\n" + "="*70)
    print("KROK 2: EXTRAKCE MORAVSKOSLEZSKÉHO KRAJE")
    print("="*70)
    
    try:
        with rasterio.open(str(tif_path)) as src:
            print(f"\n  Čtu soubor: {tif_path.name}")
            print(f"  CRS: {src.crs}")
            print(f"  Shape: {src.height} × {src.width}")
            print(f"  NoData value: {src.nodata}")
            
            print(f"\n  ⚠️  Data jsou ve STŘEDU souboru (okraje = NoData)")
            print(f"  Čtu centrální část kde jsou správná data...")
            
            # Vezmi střed - od 75% do 100% šířky, od 20% do 60% výšky
            col_start = int(src.width * 0.74)
            col_end = int(src.width)
            row_start = int(src.height * 0.27)
            row_end = int(src.height * 0.65)
            
            width = col_end - col_start
            height = row_end - row_start
            
            print(f"\n  Pixel indexy pro čtení:")
            print(f"    Sloupce: {col_start} - {col_end} (šířka {width})")
            print(f"    Řádky: {row_start} - {row_end} (výška {height})")
            
            print(f"\n  Čtu centrální region z TIF (může trvat 10-20 sekund)...")
            heights = src.read(1, window=Window(col_start, row_start, width, height))
            
            print(f"  ✓ Data načtena: {heights.shape}")
            print(f"    Raw dtype: {heights.dtype}")
            
            # ========== ČIŠTĚNÍ NoData ==========
            print(f"\n  ⚠️  Čistím NoData hodnoty...")
            
            nodata = src.nodata
            
            # Převeď na float
            heights = heights.astype(np.float32)
            
            # Detekuj špatné pixely
            nan_mask = np.isnan(heights)
            inf_mask = np.isinf(heights)
            nodata_mask = (heights == nodata) if nodata is not None else np.zeros_like(heights, dtype=bool)
            extreme_mask = np.abs(heights) > 10000
            
            bad_mask = nan_mask | inf_mask | nodata_mask | extreme_mask
            print(f"     - Špatných pixelů: {bad_mask.sum()}")
            
            heights[bad_mask] = 0
            
            # Odstraň nereálné hodnoty
            heights[heights < -500] = 0
            heights[heights > 2500] = 0
            
            print(f"\n  ✓ Data očištěna")
            print(f"    Výšky: min={heights.min():.1f}, max={heights.max():.1f}")
            
            valid = heights[heights > 0]
            if len(valid) > 0:
                print(f"    Průměr (bez nul): {valid.mean():.1f} m")
                print(f"    Platných pixelů: {len(valid)} / {heights.size}")
            else:
                print(f"    ⚠️  Žádné platné pixely!")
            
            return heights.astype(np.float32)
    
    except Exception as e:
        print(f"✗ Chyba: {e}")
        import traceback
        traceback.print_exc()
        return None


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


def step4_visualize(heights):
    """KROK 4: Vizualizuj - MEMORY OPTIMIZED"""
    print("\n" + "="*70)
    print("KROK 4: VIZUALIZACE DAT (memory optimized)")
    print("="*70)
    
    try:
        print(f"\n  📊 Vstupní data: {heights.shape}")
        print(f"  🔄 Snižuji rozlišení pro grafiku...")
        
        # Downsample 2x - ušetří paměť
        heights_vis = heights[::2, ::2].copy()
        print(f"  ✓ Downsampled: {heights_vis.shape}")
        
        # Vytvoř minimalistický graf
        print(f"  📐 Vytváření grafu...")
        fig, ax = plt.subplots(figsize=(10, 7), dpi=100)
        
        im = ax.imshow(heights_vis, cmap='terrain', origin='upper', interpolation='bilinear')
        ax.set_title('Nadmořské Výšky - Moravskoslezský Kraj\n(INSPIRE EL-GRID, UTM33N)', 
                     fontweight='bold', fontsize=12)
        
        cbar = plt.colorbar(im, ax=ax, label='m.n.m', shrink=0.8)
        ax.set_xlabel('Sloupec (px)', fontsize=10)
        ax.set_ylabel('Řádek (px)', fontsize=10)
        
        # Statistika
        valid = heights[heights > 0]
        mean_val = valid.mean() if len(valid) > 0 else 0
        
        stats = f'Grid: {heights.shape}\nMin: {heights.min():.0f}m\nMax: {heights.max():.0f}m\nMean: {mean_val:.1f}m'
        ax.text(0.70, 0.98, stats, transform=ax.transAxes,
                verticalalignment='top', fontsize=9, family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        output_png = 'ms_heights_visualization.png'
        print(f"  💾 Ukládám PNG (100 DPI)...")
        plt.savefig(output_png, dpi=100, bbox_inches='tight', format='png', facecolor='white')
        print(f"  ✓ Uloženo: {output_png}")
        
        # Agresivní cleanup
        plt.close('all')
        del fig, ax, im, heights_vis
        gc.collect()
        print(f"  ✓ Paměť uvolněna\n")
        
    except Exception as e:
        print(f"✗ Chyba při vizualizaci: {e}")
        print(f"  (Pokračuji bez grafiky...)")
        plt.close('all')
        gc.collect()


def step5_create_cpp(rows, cols):
    """KROK 5: Vytvoř C++"""
    print("\n" + "="*70)
    print("KROK 5: GENEROVÁNÍ C++ PROGRAMU")
    print("="*70)
    
    cpp_code = f'''#include <iostream>
#include <fstream>
#include <cstdint>
#include <cstring>
#include <algorithm>

struct Grid {{
    int rows = {rows};
    int cols = {cols};
    uint16_t* heights = nullptr;
}};

bool loadBinary(const char* filename, Grid& grid) {{
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {{
        std::cerr << "Chyba: Nelze otevřít " << filename << std::endl;
        return false;
    }}
    
    uint32_t r, c;
    file.read((char*)&r, sizeof(uint32_t));
    file.read((char*)&c, sizeof(uint32_t));
    
    grid.heights = new uint16_t[r * c];
    file.read((char*)grid.heights, r * c * sizeof(uint16_t));
    
    std::cout << "✓ Načteno: " << r << " × " << c << " grid" << std::endl;
    
    file.close();
    return true;
}}

int main() {{
    std::cout << "\\n=== NADMOŘSKÉ VÝŠKY - MS KRAJ ===\\n\\n";
    
    Grid grid;
    if (!loadBinary("ms_heights.bin", grid)) return 1;
    
    std::cout << "✓ Data úspěšně načtena!\\n\\n";
    
    // Vypočítej statistiku
    uint16_t min_h = UINT16_MAX, max_h = 0;
    double sum = 0;
    int count = 0;
    for (int i = 0; i < grid.rows * grid.cols; ++i) {{
        if (grid.heights[i] > 0) {{
            min_h = std::min(min_h, grid.heights[i]);
            max_h = std::max(max_h, grid.heights[i]);
            sum += grid.heights[i];
            count++;
        }}
    }}
    double mean = count > 0 ? sum / count : 0;
    
    std::cout << "Statistika:\\n";
    std::cout << "  Min: " << min_h << " m\\n";
    std::cout << "  Max: " << max_h << " m\\n";
    std::cout << "  Mean: " << mean << " m\\n";
    std::cout << "  Platných pixelů: " << count << "/" << (grid.rows * grid.cols) << "\\n";
    
    delete[] grid.heights;
    return 0;
}}
'''
    
    output_file = 'load_heights.cpp'
    with open(output_file, 'w') as f:
        f.write(cpp_code)
    
    print(f"  ✓ Vytvořen: {output_file}")
    return output_file


def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "EXTRAKCE INSPIRE EL-GRID".center(68) + "║")
    print("║" + "Nadmořské výšky Moravskoslezského kraje".center(68) + "║")
    print("║" + "✓ MEMORY OPTIMIZED".center(68) + "║")
    print("╚" + "="*68 + "╝")
    
    # KROK 1
    tif_path = step1_inspect_tif()
    if not tif_path:
        print("✗ Inspekce TIF selhala!")
        return False
    
    # KROK 2
    heights = step2_extract_ms_region(tif_path)
    if heights is None:
        print("✗ Extrakce selhala!")
        return False
    
    # KROK 3
    binary_file = step3_save_binary(heights)
    if not binary_file:
        return False
    
    # KROK 4 - GRAPHICS (now memory safe)
    step4_visualize(heights)
    
    # KROK 5
    rows, cols = heights.shape
    cpp_file = step5_create_cpp(rows, cols)
    
    # SOUHRN
    print("\n" + "="*70)
    print("✓✓✓ HOTOVO! ✓✓✓")
    print("="*70)
    print(f"\n✓ Binární soubor: {binary_file}")
    print(f"✓ C++ program: {cpp_file}")
    print(f"✓ Vizualizace: ms_heights_visualization.png")
    print(f"\nGrid: {heights.shape[0]} × {heights.shape[1]}")
    print(f"Rozsah: {heights.min():.0f} - {heights.max():.0f} m")
    
    valid = heights[heights > 0]
    if len(valid) > 0:
        print(f"Průměr: {valid.mean():.1f} m")
    
    print(f"\nKompilace: clang++ -std=c++17 -O2 -o load_heights load_heights.cpp")
    print(f"Spuštění: ./load_heights")
    print("=" * 70 + "\n")
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)