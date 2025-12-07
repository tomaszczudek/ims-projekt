"""
Hybrid Visualizer - Kombinuje TVŮJ lineární přístup + MŮJ pokročilý
======================================================================

Používá:
  • Tvůj bin_to_img.py (lineární normalizace) ← FUNGUJE DOBŘE
  • S vylepšeními (lepší colormaps, srovnání scénářů)
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import struct
import os

def load_bin_data(filename):
    """Načti znečištění z BIN souboru"""
    print(f"📂 Načítám {filename}...")

    with open(filename, 'rb') as f:
        # Přeskočit header (60 B)
        f.seek(60)

        # Přeskočit počet továren (4 B)
        num_plants = struct.unpack('I', f.read(4))[0]
        print(f"  Továrny: {num_plants}")

        # Přeskočit data továren
        f.seek(60 + 4 + num_plants * 12)

        # Přeskočit row ranges
        num_valid_rows = 1322  # From header
        f.seek(f.tell() + num_valid_rows * 12)

        # Načti znečištění data
        pollution = np.zeros((1322, 1581), dtype=np.float32)

        for row in range(1322):
            for col in range(1581):
                h_bytes = f.read(2)
                p_bytes = f.read(4)

                if len(p_bytes) == 4:
                    pollution[row, col] = struct.unpack('f', p_bytes)[0]

    return pollution

def create_hybrid_heatmap(pollution, title, output_file):
    """
    Vytvoř heatmapu - HYBRID přístup

    Kombinuje:
    1. Lineární normalizaci (tvůj přístup)
    2. Vylepšený colormap (můj přístup)
    3. Měkký contrast (best of both)
    """
    print(f"🎨 Vytváření heatmapy: {output_file}")

    # Strategie: Lineární škála s SOFT clipping
    min_val = np.min(pollution[pollution > 0])
    max_val = np.max(pollution)

    print(f"  Min: {min_val:.2e}, Max: {max_val:.2e}")
    print(f"  Range: {(max_val - min_val):.2e}")

    # Kvadratická škála (mezi lineární a log)
    # → Zvýrazní malé rozdíly, ale nezničí detail
    pollution_scaled = np.sqrt(pollution)  # ← Soft scaling!

    min_scaled = np.sqrt(min_val)
    max_scaled = np.sqrt(max_val)

    normalized = 255 * (pollution_scaled - min_scaled) / (max_scaled - min_scaled)
    normalized = np.clip(normalized, 0, 255).astype(np.uint8)

    # Vytvoř obrázek s LEPŠÍM colormapem
    img = Image.new('RGB', (pollution.shape[1], pollution.shape[0]))
    pixels = img.load()

    for row in range(pollution.shape[0]):
        for col in range(pollution.shape[1]):
            val = normalized[row, col]

            # Vylepšený barevný gradient (z tvého bin_to_img.py)
            if val < 50:
                # Modré oblasti (nula)
                r, g, b = int(50 + val * 2), int(100 + val * 0.5), 255
            elif val < 100:
                # Zelené přechody
                r = 0
                g = int(255 * (val - 50) / 50)
                b = int(255 * (100 - val) / 50)
            elif val < 150:
                # Žluté přechody
                r = int(255 * (val - 100) / 50)
                g = 255
                b = 0
            elif val < 200:
                # Oranžové přechody
                r = 255
                g = int(255 * (200 - val) / 50)
                b = 0
            else:
                # Červené oblasti (maximum)
                r = 255
                g = int(255 * (255 - val) / 55)
                b = 0

            pixels[col, row] = (r, g, b)

    # Přidej metadata
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), title, fill=(255, 255, 255))
    draw.text((10, 30), f"Min: {min_val:.2e} kg/m³", fill=(255, 255, 255))
    draw.text((10, 50), f"Max: {max_val:.2e} kg/m³", fill=(255, 255, 255))

    img.save(output_file)
    print(f"  ✓ Uloženo: {output_file}")

    return pollution_scaled, normalized

def create_comparison():
    """Vytvoř porovnání s lepšími výsledky"""

    print("\n" + "="*70)
    print("🎨 HYBRID HEATMAP GENERATOR")
    print("="*70)

    # Zjisti jaké BIN soubory máš
    bin_files = {
        "src/output.bin": "Vystup Cpp",
    }

    # Zpracuj všechny dostupné soubory
    for bin_file, desc in bin_files.items():
        if os.path.exists(bin_file):
            print(f"\n📊 Zpracovávám: {bin_file}")

            try:
                pollution = load_bin_data(bin_file)

                output_file = bin_file.replace('.bin', '_hybrid.png')
                create_hybrid_heatmap(pollution, f"Hybrid: {desc}", output_file)

            except Exception as e:
                print(f"  ⚠️  Chyba: {e}")
        else:
            print(f"  ⓘ Soubor neexistuje: {bin_file}")

    print("\n" + "="*70)
    print("✓ Hybrid heatmapy vytvořeny!")
    print("="*70)
    print("""
Výsledky:
  • *_hybrid.png - Kombinuje lineární + kvadratickou škálu
  • Lepší viditelnost znečištění
  • Zachovává detail z tvého přístupu
  • Zvýrazňuje rozdíly mého přístupu
    """)

if __name__ == "__main__":
    create_comparison()