#!/usr/bin/env python3
"""
ČTENÍ BIN SOUBORU A VYTVOŘENÍ OBRÁZKŮ
Pracuje s oběma souubory: terrain.bin (z Pythonu) a terrain_modified.bin (z C++)
"""

import struct
import numpy as np
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:
    print("✗ Chybí matplotlib!")
    exit(1)


def read_binary(filename):
    """Čti optimalizovaný binární soubor"""
    print(f"\n{'='*70}")
    print(f"ČTENÍ: {filename}")
    print(f"{'='*70}")
    
    if not Path(filename).exists():
        print(f"✗ Soubor {filename} neexistuje!")
        return None
    
    with open(filename, 'rb') as f:
        # Čti HEADER
        rows = struct.unpack('I', f.read(4))[0]
        cols = struct.unpack('I', f.read(4))[0]
        num_plants = struct.unpack('I', f.read(4))[0]
        num_row_ranges = struct.unpack('I', f.read(4))[0]
        version = struct.unpack('I', f.read(4))[0]
        
        print(f"  Header:")
        print(f"    Řádků: {rows}, Sloupců: {cols}")
        print(f"    Řádků s daty: {num_row_ranges}")
        print(f"    Továren: {num_plants}")
        print(f"    Verze: {version}")
        
        # Čti ROW RANGES
        print(f"\n  Čtu row ranges...")
        row_ranges = []
        for i in range(num_row_ranges):
            row_id = struct.unpack('I', f.read(4))[0]
            col_start = struct.unpack('I', f.read(4))[0]
            col_end = struct.unpack('I', f.read(4))[0]
            col_count = struct.unpack('H', f.read(2))[0]
            
            row_ranges.append({
                'row_id': row_id,
                'col_start': col_start,
                'col_end': col_end,
                'col_count': col_count
            })
        
        # Čti HEIGHT DATA
        print(f"    ✓ Načteno {len(row_ranges)} řádků")
        print(f"  Čtu height data...")
        
        total_pixels = sum(rr['col_count'] for rr in row_ranges)
        height_data = np.frombuffer(f.read(total_pixels * 2), dtype=np.uint16)
        print(f"    ✓ Načteno {len(height_data)} pixelů")
        
        # Čti PLANTS
        print(f"  Čtu {num_plants} továren...")
        plants = []
        
        for p in range(num_plants):
            lat = struct.unpack('f', f.read(4))[0]
            lon = struct.unpack('f', f.read(4))[0]
            px = struct.unpack('I', f.read(4))[0]
            py = struct.unpack('I', f.read(4))[0]
            pollution_tons = struct.unpack('f', f.read(4))[0]
            
            name_len = struct.unpack('H', f.read(2))[0]
            name = f.read(name_len).decode('utf-8') if name_len > 0 else ''
            
            type_len = struct.unpack('H', f.read(2))[0]
            plant_type = f.read(type_len).decode('utf-8') if type_len > 0 else ''
            
            plants.append({
                'lat': lat,
                'lon': lon,
                'px': px,
                'py': py,
                'pollution_tons': pollution_tons,
                'name': name,
                'type': plant_type
            })
        
        print(f"    ✓ Načteno {len(plants)} továren")
    
    return {
        'rows': rows,
        'cols': cols,
        'row_ranges': row_ranges,
        'height_data': height_data,
        'plants': plants
    }


def reconstruct_heights(data):
    """Rekonstruuj 2D pole z komprimovaných dat"""
    print(f"\n  🔨 Rekonstrukce 2D pole...")
    
    rows = data['rows']
    cols = data['cols']
    row_ranges = data['row_ranges']
    height_data = data['height_data']
    
    heights = np.zeros((rows, cols), dtype=np.uint16)
    
    offset = 0
    for rr in row_ranges:
        row_id = rr['row_id']
        col_start = rr['col_start']
        col_count = rr['col_count']
        
        row_data = height_data[offset:offset + col_count]
        heights[row_id, col_start:col_start + col_count] = row_data
        
        offset += col_count
    
    print(f"    ✓ Hotovo: {rows}×{cols}")
    return heights


def create_height_map_image(data, output_file='height_map.png'):
    """Vytvoř obrázek výšek"""
    print(f"\n  📊 Vytváření mapy výšek...")
    
    heights = reconstruct_heights(data)
    
    fig, ax = plt.subplots(figsize=(14, 10), dpi=100)
    
    im = ax.imshow(heights, cmap='terrain', origin='upper', interpolation='bilinear')
    ax.set_title('Nadmořské Výšky - MS Kraj', fontweight='bold', fontsize=14)
    cbar = plt.colorbar(im, ax=ax, label='m.n.m', shrink=0.8)
    
    # Statistika
    valid = heights[heights > 0]
    if len(valid) > 0:
        stats = f'Grid: {heights.shape}\nMin: {heights.min():.0f}m\nMax: {heights.max():.0f}m\nMean: {valid.mean():.1f}m'
        ax.text(0.02, 0.98, stats, transform=ax.transAxes, verticalalignment='top',
                fontsize=10, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))
    
    plt.savefig(output_file, dpi=100, bbox_inches='tight', facecolor='white')
    print(f"    ✓ Uloženo: {output_file}")
    plt.close()


def create_pollution_map_image(data, output_file='pollution_map.png'):
    """Vytvoř obrázek znečištění"""
    print(f"\n  🏭 Vytváření mapy znečištění...")
    
    heights = reconstruct_heights(data)
    plants = data['plants']
    rows = data['rows']
    cols = data['cols']
    
    fig, ax = plt.subplots(figsize=(14, 10), dpi=100)
    
    # Pozadí - výšky
    heights_vis = heights[::2, ::2].copy()
    im = ax.imshow(heights_vis, cmap='gray', alpha=0.3, origin='upper')
    
    # Továrny - body s barvou podle znečištění
    if plants:
        max_pollution = max((p['pollution_tons'] for p in plants), default=1.0)
        
        for plant in plants:
            px = plant['px']
            py = plant['py']
            
            if 0 <= px < cols and 0 <= py < rows:
                # Normalizuj znečištění pro barvu
                pollution_norm = plant['pollution_tons'] / max_pollution if max_pollution > 0 else 0
                
                # Barva: červená = více znečištění
                color = (pollution_norm, 0, 1 - pollution_norm)
                size = 10 + pollution_norm * 100
                
                ax.plot(px//2, py//2, 'o', color=color, markersize=min(50, size),
                       markeredgecolor='black', markeredgewidth=1, alpha=0.7)
    
    ax.set_title('Zdroje Znečištění - MS Kraj', fontweight='bold', fontsize=14)
    ax.set_xlabel('Pixel X')
    ax.set_ylabel('Pixel Y')
    
    # Info
    stats = f'Továrny: {len(plants)}\nMax znečištění: {max((p["pollution_tons"] for p in plants), default=0):.1f} tun/rok'
    ax.text(0.02, 0.98, stats, transform=ax.transAxes, verticalalignment='top',
            fontsize=10, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))
    
    plt.savefig(output_file, dpi=100, bbox_inches='tight', facecolor='white')
    print(f"    ✓ Uloženo: {output_file}")
    plt.close()


def create_combined_image(data, output_file='combined_map.png'):
    """Vytvoř kombinovanou mapu"""
    print(f"\n  🗺️ Vytváření kombinované mapy...")
    
    heights = reconstruct_heights(data)
    plants = data['plants']
    rows = data['rows']
    cols = data['cols']
    
    fig, ax = plt.subplots(figsize=(14, 10), dpi=100)
    
    # Pozadí - výšky
    im = ax.imshow(heights, cmap='terrain', origin='upper', interpolation='bilinear', alpha=0.9)
    cbar = plt.colorbar(im, ax=ax, label='m.n.m', shrink=0.8)
    
    # Továrny - hvězdičky
    for plant in plants:
        px = plant['px']
        py = plant['py']
        
        if 0 <= px < cols and 0 <= py < rows:
            ax.plot(px, py, 'r*', markersize=20, markeredgecolor='darkred', markeredgewidth=2)
    
    ax.set_title('Výšky se Zdroji Znečištění - MS Kraj', fontweight='bold', fontsize=14)
    ax.set_xlabel('Pixel X')
    ax.set_ylabel('Pixel Y')
    
    # Info
    stats = f'Grid: {heights.shape}\nTovárny: {len(plants)}'
    ax.text(0.02, 0.98, stats, transform=ax.transAxes, verticalalignment='top',
            fontsize=10, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))
    
    plt.savefig(output_file, dpi=100, bbox_inches='tight', facecolor='white')
    print(f"    ✓ Uloženo: {output_file}")
    plt.close()


def print_plant_stats(data):
    """Vypis statistiku továren"""
    print(f"\n  🏭 STATISTIKA TOVÁREN:")
    
    plants = data['plants']
    if not plants:
        return
    
    total_pollution = sum(p['pollution_tons'] for p in plants)
    max_pollution = max(p['pollution_tons'] for p in plants)
    min_pollution = min(p['pollution_tons'] for p in plants)
    avg_pollution = total_pollution / len(plants)
    
    print(f"    Počet: {len(plants)}")
    print(f"    Celk. znečištění: {total_pollution:.1f} tun/rok")
    print(f"    Průměr: {avg_pollution:.1f} tun/rok")
    print(f"    Min: {min_pollution:.1f} tun/rok")
    print(f"    Max: {max_pollution:.1f} tun/rok")
    
    print(f"\n    Top 5 znečišťovatelů:")
    sorted_plants = sorted(plants, key=lambda p: p['pollution_tons'], reverse=True)
    for i, p in enumerate(sorted_plants[:5], 1):
        print(f"      {i}. {p['name'][:50]:50s} {p['pollution_tons']:8.1f} tun/rok")


def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "ČTENÍ BIN SOUBORU → OBRÁZKY".center(68) + "║")
    print("╚" + "="*68 + "╝")
    
    # Zkus oba soubory
    for bin_file in ['terrain.bin', 'terrain_modified.bin']:
        if not Path(bin_file).exists():
            continue
        
        print(f"\n📂 Zpracovávám: {bin_file}")
        
        data = read_binary(bin_file)
        if not data:
            continue
        
        # Výšky
        height_output = bin_file.replace('.bin', '_heights.png')
        create_height_map_image(data, height_output)
        
        # Znečištění
        pollution_output = bin_file.replace('.bin', '_pollution.png')
        create_pollution_map_image(data, pollution_output)
        
        # Kombinovaná
        combined_output = bin_file.replace('.bin', '_combined.png')
        create_combined_image(data, combined_output)
        
        # Statistika
        print_plant_stats(data)
    
    print("\n" + "="*70)
    print("✓ HOTOVO!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
