"""
ČTENÍ BIN SOUBORU V3 A VYTVOŘENÍ OBRÁZKŮ S POLLUTION MAPOU
FIXED: Správný offset po čtení height/pollution dat
"""

import struct
import numpy as np
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
except ImportError:
    print("✗ Chybí matplotlib!")
    exit(1)


def read_binary_v3(filename):
    """Čti binární soubor V3"""
    print(f"\n{'='*70}")
    print(f"ČTENÍ V3: {filename}")
    print(f"{'='*70}")
    
    if not Path(filename).exists():
        print(f"✗ Soubor {filename} neexistuje!")
        return None
    
    with open(filename, 'rb') as f:
        # Header
        rows = struct.unpack('I', f.read(4))[0]
        cols = struct.unpack('I', f.read(4))[0]
        num_plants = struct.unpack('I', f.read(4))[0]
        num_row_ranges = struct.unpack('I', f.read(4))[0]
        version = struct.unpack('I', f.read(4))[0]
        
        print(f"  Header (v{version}): {rows}×{cols}, {num_row_ranges} řádků, {num_plants} továren")
        
        # Row ranges
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
        
        print(f"  ✓ {len(row_ranges)} řádků s daty")
        
        # Height data - KOMPRIMOVANÁ!
        total_pixels = sum(rr['col_count'] for rr in row_ranges)
        print(f"  Čtení {total_pixels} pixelů height dat...")
        
        height_data = np.frombuffer(f.read(total_pixels * 2), dtype=np.uint16)
        print(f"  ✓ Height: {len(height_data)} pixelů")
        
        # Pollution data - KOMPRIMOVANÁ!
        print(f"  Čtení {total_pixels} pixelů pollution dat...")
        
        pollution_data = np.frombuffer(f.read(total_pixels * 4), dtype=np.float32)
        print(f"  ✓ Pollution: {len(pollution_data)} pixelů")
        
        if len(pollution_data) > 0 and pollution_data.max() > 0:
            print(f"    Min: {pollution_data.min():.6f}, Max: {pollution_data.max():.6f}")
        else:
            print(f"    (Všechno = 0)")
        
        # Plants - TEĎ JE SPRÁVNÝ OFFSET!
        print(f"  Čtení {num_plants} továren...")
        plants = []
        
        for p in range(num_plants):
            # Čti headers NEJPRVE
            bytes_read = f.read(4 + 4 + 4 + 4 + 4)  # lat + lon + px + py + pollution_tons
            
            if len(bytes_read) < 20:
                print(f"    ⚠️  Chyba: nedostatek dat pro továrnu {p}")
                break
            
            lat = struct.unpack('f', bytes_read[0:4])[0]
            lon = struct.unpack('f', bytes_read[4:8])[0]
            px = struct.unpack('I', bytes_read[8:12])[0]
            py = struct.unpack('I', bytes_read[12:16])[0]
            pollution_tons = struct.unpack('f', bytes_read[16:20])[0]
            
            # Čti jméno
            name_len_bytes = f.read(2)
            if len(name_len_bytes) < 2:
                print(f"    ⚠️  Chyba: nedostatek dat pro délku jména")
                break
            
            name_len = struct.unpack('H', name_len_bytes)[0]
            name = f.read(name_len).decode('utf-8') if name_len > 0 else ''
            
            # Čti typ
            type_len_bytes = f.read(2)
            if len(type_len_bytes) < 2:
                print(f"    ⚠️  Chyba: nedostatek dat pro délku typu")
                break
            
            type_len = struct.unpack('H', type_len_bytes)[0]
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
        
        print(f"  ✓ {len(plants)} továren")
    
    return {
        'rows': rows,
        'cols': cols,
        'row_ranges': row_ranges,
        'height_data': height_data,
        'pollution_data': pollution_data,
        'plants': plants,
        'version': version
    }


def reconstruct_grids(data):
    """Rekonstruuj 2D pole"""
    print(f"  🔨 Rekonstrukce 2D polí...")
    
    rows = data['rows']
    cols = data['cols']
    row_ranges = data['row_ranges']
    height_data = data['height_data']
    pollution_data = data['pollution_data']
    
    heights = np.zeros((rows, cols), dtype=np.uint16)
    pollution = np.zeros((rows, cols), dtype=np.float32)
    
    offset = 0
    for rr in row_ranges:
        row_id = rr['row_id']
        col_start = rr['col_start']
        col_count = rr['col_count']
        
        row_height = height_data[offset:offset + col_count]
        row_pollution = pollution_data[offset:offset + col_count]
        
        heights[row_id, col_start:col_start + col_count] = row_height
        pollution[row_id, col_start:col_start + col_count] = row_pollution
        
        offset += col_count
    
    print(f"    ✓ Hotovo: {rows}×{cols}")
    return heights, pollution


def create_pollution_heatmap(data, output_file='pollution_heatmap.png'):
    """Vytvoř heatmapu znečištění"""
    print(f"  🌡️  Vytváření heatmapy znečištění...")
    
    heights, pollution = reconstruct_grids(data)
    
    fig, ax = plt.subplots(figsize=(16, 12), dpi=100)
    
    colors = ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff8800', '#ff0000']
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('pollution', colors, N=n_bins)
    
    pollution_vis = np.copy(pollution)
    pollution_vis[pollution_vis <= 0] = 1e-10
    pollution_vis = np.log10(pollution_vis + 1)
    
    im = ax.imshow(pollution_vis, cmap=cmap, origin='upper', interpolation='bilinear')
    ax.set_title('Znečištění - Heatmapa (log scale)', fontweight='bold', fontsize=14)
    
    cbar = plt.colorbar(im, ax=ax, label='log₁₀(znečištění)', shrink=0.8)
    
    plants = data['plants']
    for plant in plants:
        px = plant['px']
        py = plant['py']
        
        if 0 <= px < data['cols'] and 0 <= py < data['rows']:
            ax.plot(px, py, 'r*', markersize=15, markeredgecolor='darkred', markeredgewidth=1.5)
    
    valid_pixels = np.sum(pollution > 0)
    stats = f'Grid: {pollution.shape}\nPixelů s daty: {valid_pixels}\nMax: {pollution.max():.2f}'
    ax.text(0.02, 0.98, stats, transform=ax.transAxes, verticalalignment='top',
            fontsize=10, family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))
    
    plt.savefig(output_file, dpi=100, bbox_inches='tight', facecolor='white')
    print(f"    ✓ Uloženo: {output_file}")
    plt.close()


def create_pollution_contour(data, output_file='pollution_contour.png'):
    """Vytvoř kontury znečištění"""
    print(f"  📍 Vytváření kontur znečištění...")
    
    heights, pollution = reconstruct_grids(data)
    
    fig, ax = plt.subplots(figsize=(16, 12), dpi=100)
    
    # Pozadí - výšky
    im_bg = ax.imshow(heights, cmap='gray', alpha=0.2, origin='upper')
    
    # Kontury znečištění
    nonzero_vals = pollution[pollution > 0]
    if len(nonzero_vals) > 0:
        levels = np.logspace(np.log10(nonzero_vals.min()), 
                             np.log10(pollution.max()), 15)
        
        cs = ax.contourf(pollution, levels=levels, cmap='RdYlBu_r', origin='upper', alpha=0.7)
        ax.contour(pollution, levels=levels, colors='black', linewidths=0.5, origin='upper', alpha=0.3)
        cbar = plt.colorbar(cs, ax=ax, label='znečištění', shrink=0.8)
    else:
        # Všechno je nula - jen background
        print(f"    ℹ️  Všechno znečištění = 0 (jen výšky)")
        cbar = plt.colorbar(im_bg, ax=ax, label='výšky (m)', shrink=0.8)
    
    ax.set_title('Znečištění - Izoplochy', fontweight='bold', fontsize=14)
    
    # Továrny
    plants = data['plants']
    for plant in plants:
        px = plant['px']
        py = plant['py']
        if 0 <= px < data['cols'] and 0 <= py < data['rows']:
            ax.plot(px, py, 'ko', markersize=8, markeredgecolor='white', markeredgewidth=1)
    
    plt.savefig(output_file, dpi=100, bbox_inches='tight', facecolor='white')
    print(f"    ✓ Uloženo: {output_file}")
    plt.close()


def create_combined_v3(data, output_file='combined_v3.png'):
    """Vytvoř kombinovanou mapu"""
    print(f"  🗺️  Vytváření kombinované mapy...")
    
    heights, pollution = reconstruct_grids(data)
    plants = data['plants']
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10), dpi=100)
    
    # Levá: Výšky
    im1 = ax1.imshow(heights, cmap='terrain', origin='upper', interpolation='bilinear')
    ax1.set_title('Nadmořské Výšky', fontweight='bold', fontsize=12)
    plt.colorbar(im1, ax=ax1, label='m.n.m')
    
    # Pravá: Znečištění
    pollution_vis = np.copy(pollution)
    pollution_vis[pollution_vis <= 0] = 1e-10
    pollution_vis = np.log10(pollution_vis + 1)
    
    colors = ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff8800', '#ff0000']
    cmap = LinearSegmentedColormap.from_list('pollution', colors, N=256)
    
    im2 = ax2.imshow(pollution_vis, cmap=cmap, origin='upper', interpolation='bilinear')
    ax2.set_title('Znečištění (log scale)', fontweight='bold', fontsize=12)
    plt.colorbar(im2, ax=ax2, label='log₁₀(znečištění)')
    
    # Továrny
    for plant in plants:
        px = plant['px']
        py = plant['py']
        if 0 <= px < data['cols'] and 0 <= py < data['rows']:
            ax1.plot(px, py, 'r*', markersize=12)
            ax2.plot(px, py, 'r*', markersize=12)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=100, bbox_inches='tight', facecolor='white')
    print(f"    ✓ Uloženo: {output_file}")
    plt.close()


def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + "ČTENÍ BIN V3 → POLLUTION MAPY".center(68) + "║")
    print("╚" + "="*68 + "╝")
    
    for bin_file in ['terrain.bin', 'terrain_modified.bin']:
        if not Path(bin_file).exists():
            continue
        
        print(f"\n📂 Zpracovávám: {bin_file}")
        
        data = read_binary_v3(bin_file)
        if not data:
            continue
        
        # Heatmapa
        pollution_output = bin_file.replace('.bin', '_pollution_heatmap.png')
        create_pollution_heatmap(data, pollution_output)
        
        # Kontury
        contour_output = bin_file.replace('.bin', '_pollution_contour.png')
        create_pollution_contour(data, contour_output)
        
        # Kombinovaná
        combined_output = bin_file.replace('.bin', '_combined_v3.png')
        create_combined_v3(data, combined_output)
    
    print("\n" + "="*70)
    print("✓ HOTOVO!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()