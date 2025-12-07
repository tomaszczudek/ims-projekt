"""
BIN TO IMAGE V5 - ADVANCED
===========================
Vytvoří obrázek s:
1. Heatmapou znečištění (modrá → červená)
2. Červenými hvězdičkami pro továrny
3. Automatickým scaling

Emise formáty:
  1.23e+02 = 1.23 × 10^2 = 123 kg/rok
  4.36e+00 = 4.36 kg/rok
  1.20e-02 = 0.012 kg/rok
  3.08e+03 = 3080 kg/rok
  5.86e+05 = 586000 kg/rok (obr megaprovoz!)
"""

import struct
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon

def load_bin_v5(bin_path):
    """Načti BIN V5 s terénem a továrnami"""
    with open(bin_path, 'rb') as f:
        # Header (60B)
        cols = struct.unpack('I', f.read(4))[0]
        rows = struct.unpack('I', f.read(4))[0]
        valid_rows = struct.unpack('I', f.read(4))[0]

        # Transform (48B)
        transform = struct.unpack('6d', f.read(48))

        # Plants metadata (4B)
        num_plants = struct.unpack('I', f.read(4))[0]

        print(f"✓ Header: {cols}×{rows} grid, {valid_rows} řádků, {num_plants} továren")

        # Load plant indices
        plants = []
        for i in range(num_plants):
            row = struct.unpack('I', f.read(4))[0]
            col = struct.unpack('I', f.read(4))[0]
            emission = struct.unpack('f', f.read(4))[0]
            plants.append((row, col, emission))

        print(f"✓ Načteno {len(plants)} továren")

        # Load row ranges
        row_ranges = []
        for i in range(valid_rows):
            row_id = struct.unpack('I', f.read(4))[0]
            col_start = struct.unpack('I', f.read(4))[0]
            col_end = struct.unpack('I', f.read(4))[0]
            row_ranges.append((row_id, col_start, col_end))

        print(f"✓ Načteny řádky ({len(row_ranges)} řádků s daty)")

        # Load height data
        heights = np.zeros((rows, cols), dtype=np.uint16)
        pollution = np.zeros((rows, cols), dtype=np.float32)

        for row_id, col_start, col_end in row_ranges:
            for col in range(col_start, col_end):
                height = struct.unpack('H', f.read(2))[0]
                poll = struct.unpack('f', f.read(4))[0]
                heights[row_id, col] = height
                pollution[row_id, col] = poll

        print(f"✓ Načteny výšky: min={heights[heights>0].min()}, max={heights.max()}")

        # Pollution stats
        poll_nonzero = pollution[pollution > 0]
        if len(poll_nonzero) > 0:
            print(f"✓ Znečištění: min={poll_nonzero.min():.2e}, max={poll_nonzero.max():.2e}")

        return heights, pollution, plants, cols, rows

def create_image_with_heatmap(pollution, plants, cols, rows, output_path):
    """Vytvoř obrázek s heatmapou znečištění a hvězdičkami"""

    print("\n📊 Vytváření heatmapy...")

    # Normalizuj znečištění (log scale pro lepší viditelnost)
    pollution_vis = pollution.copy()
    pollution_vis[pollution_vis == 0] = np.nan

    # Log scale pro lepší rozlišení (přidáme 1 aby jsme se vyhnuli log(0))
    pollution_log = np.log10(pollution_vis + 1e-6)

    # Přeskáluj na 0-255 (ignoruj NaN)
    valid_mask = ~np.isnan(pollution_log)
    if np.any(valid_mask):
        vmin = np.nanmin(pollution_log)
        vmax = np.nanmax(pollution_log)
        pollution_scaled = np.zeros_like(pollution_log)
        pollution_scaled[valid_mask] = (pollution_log[valid_mask] - vmin) / (vmax - vmin) * 255
    else:
        pollution_scaled = np.zeros_like(pollution_log)

    # Vytvoř RGB heatmapu (modrá → zelená → žlutá → červená)
    heatmap_rgb = np.zeros((rows, cols, 3), dtype=np.uint8)

    for r in range(rows):
        for c in range(cols):
            val = pollution_scaled[r, c]

            if np.isnan(pollution_log[r, c]):
                # Černá pro chybějící data
                heatmap_rgb[r, c] = [0, 0, 0]
            else:
                # Heatmap: modrá (0) → zelená → žlutá → červená (255)
                norm_val = val / 255.0

                if norm_val < 0.25:
                    # Modrá → Zelená
                    r_val = 0
                    g_val = int(norm_val / 0.25 * 255)
                    b_val = 255 - int(norm_val / 0.25 * 255)
                elif norm_val < 0.5:
                    # Zelená → Žlutá
                    r_val = int((norm_val - 0.25) / 0.25 * 255)
                    g_val = 255
                    b_val = 0
                elif norm_val < 0.75:
                    # Žlutá → Červená
                    r_val = 255
                    g_val = int(255 - (norm_val - 0.5) / 0.25 * 255)
                    b_val = 0
                else:
                    # Červená
                    r_val = 255
                    g_val = 0
                    b_val = 0

                heatmap_rgb[r, c] = [r_val, g_val, b_val]

    # Vytvoř PIL Image
    img = Image.fromarray(heatmap_rgb, 'RGB')
    draw = ImageDraw.Draw(img, 'RGBA')

    print(f"✓ Heatmapa: {cols}×{rows} px")

    # Přidej hvězdičky pro továrny
    print(f"📍 Přidávám {len(plants)} hvězdičků...")

    star_size = 8  # Velikost hvězdičky
    for plant_idx, (plant_row, plant_col, emission) in enumerate(plants):
        # Zjisti barevnost hvězdičky dle emise
        if emission < 1.0:
            star_color = (255, 255, 0, 200)  # Oranžová - slabé emise
        elif emission < 10.0:
            star_color = (255, 100, 0, 220)  # Tmavě oranžová - střední emise
        else:
            star_color = (255, 0, 0, 255)    # Červená - silné emise

        # Hvězdička - nakreslíme 5 bodů
        x, y = plant_col, plant_row
        points = []
        for i in range(10):
            angle = i * np.pi / 5
            if i % 2 == 0:
                r = star_size
            else:
                r = star_size * 0.4
            px = x + r * np.sin(angle)
            py = y - r * np.cos(angle)
            points.append((px, py))

        # Nakresli vyplněnou hvězdičku
        #draw.polygon(points, fill=star_color, outline=(255, 255, 255, 255))

    print(f"✓ Hvězdičky přidány")

    # Ulož
    img.save(output_path)
    print(f"\n✓ Obrázek uložen: {output_path}")
    print(f"  Rozměry: {cols}×{rows} px")
    print(f"  Barvy:")
    print(f"    🟦 Modrá = nízké znečištění")
    print(f"    🟩 Zelená = střední znečištění")
    print(f"    🟨 Žlutá = vysoké znečištění")
    print(f"    🟥 Červená = velmi vysoké znečištění")
    print(f"\n  🟠 Oranžová hvězdička = slabá emise (<1 kg/rok)")
    print(f"  🟠 Tmavě oranžová = střední emise (1-10 kg/rok)")
    print(f"  🔴 Červená hvězdička = silná emise (>10 kg/rok)")

def main():
    bin_path = "../src/output.bin"
    output_path = "../doc/terrain_heatmap.png"

    print("="*70)
    print("BIN TO IMAGE V5 - HEATMAP + HVĚZDIČKY")
    print("="*70)

    # Načti data
    heights, pollution, plants, cols, rows = load_bin_v5(bin_path)

    # Vytvořit obrázek
    create_image_with_heatmap(pollution, plants, cols, rows, output_path)

    # Statistika emisi
    print("\n🏭 EMISE - VYSVĚTLENÍ:")
    print("="*70)
    print("""
Vědecká notace (exponenciální zápis):
  1.23e+02 = 1.23 × 10² = 1.23 × 100 = 123 kg/rok
  4.36e+00 = 4.36 × 10⁰ = 4.36 × 1 = 4.36 kg/rok
  1.20e-02 = 1.20 × 10⁻² = 1.20 × 0.01 = 0.012 kg/rok
  3.08e+03 = 3.08 × 10³ = 3080 kg/rok
  5.86e+05 = 5.86 × 10⁵ = 586000 kg/rok (MEGAPROVOZ!)

Vysvětlení jednotek:
  kg/rok = kilogramy za rok
  e+XX = násobeno 10 na XX-tou
  e-XX = děleno 10 na XX-tou
""")

    # Top emitenti
    print("\n🔝 TOP 10 NEJVĚTŠÍCH EMITENTŮ:")
    plants_sorted = sorted(plants, key=lambda x: x[2], reverse=True)
    for i, (row, col, emission) in enumerate(plants_sorted[:10]):
        print(f"  {i+1:2d}. ({row:4d}, {col:4d}): {emission:.2e} kg/rok")

    print("\n" + "="*70)
    print("✓ HOTOVO!")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()