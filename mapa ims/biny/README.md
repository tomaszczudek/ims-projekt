# Terrain Data Pipeline: Python ↔ C++ ↔ Images

## 📦 Binární Formát

```
[HEADER - 20 bytes]
  uint32  rows              ← počet řádků
  uint32  cols              ← počet sloupců
  uint32  num_plants        ← počet továren
  uint32  num_row_ranges    ← počet řádků s daty
  uint32  version           ← verze formátu

[ROW RANGES - num_row_ranges × 16 bytes]
  uint32  row_id            ← číslo řádku
  uint32  col_start         ← začátek nenulových dat
  uint32  col_end           ← konec nenulových dat
  uint16  col_count         ← počet pixelů

[HEIGHT DATA - VARIABILNÍ]
  uint16[]  heights         ← jen nenulové sloupce (bez modrého pozadí!)

[PLANTS - VARIABILNÍ]
  Pro KAŽDOU továrnu:
  ├─ float32  lat, lon      ← GPS souřadnice
  ├─ uint32   px, py        ← INDEXY do gridu!
  ├─ float32  pollution_tons ← TUNY za rok!
  ├─ uint16   name_len
  ├─ char[]   name
  ├─ uint16   type_len
  └─ char[]   type
```

## 🚀 Workflow

### 1. PYTHON: Exportovat do BIN

```bash
python3 export_to_bin.py
```

**Výstup:** `terrain.bin` (~100-200 MB)

**Co dělá:**
- Čte `plants.json` (lokálně)
- Čte `EL-GRID.tif` (výšky)
- Filtruje MS kraj
- Komprimuje 2D pole (row ranges)
- Exportuje do binárního formátu

### 2. C++: Zpracovat BIN

```bash
g++ -std=c++11 -O2 main.cpp -o terrain_processor
./terrain_processor
```

**Čte:** `terrain.bin`
**Exportuje:** `terrain_modified.bin`

**Co umožňuje:**
- Čtení komprimovaných dat
- Analýza výšek a továren
- Modifikace znečištění
- Zpět export do BIN

**Příklad v main.cpp:**
```cpp
TerrainLoader terrain;
terrain.loadFromBinary("terrain.bin");
terrain.printStatistics();

// Modifikace - snížení znečištění o 10%
for (auto& plant : terrain.plants) {
    plant.pollution_tons *= 0.9f;
}

terrain.saveToBinary("terrain_modified.bin");
```

### 3. PYTHON: Čtení BIN → Obrázky

```bash
python3 bin_to_image.py
```

**Čte:** `terrain.bin` a/nebo `terrain_modified.bin`
**Vytváří:**
- `terrain_heights.png` - mapa výšek
- `terrain_pollution.png` - mapa znečištění
- `terrain_combined.png` - kombinovaná mapa

## 📊 Komprese

- **Original:** ~1GB (21157×25299×2 bytes)
- **Optimalizovaný:** ~100-200 MB
- **Kompresní poměr:** 4-10x

**Důvod:** Uloženou POUZE řádky s daty, bez modrého pozadí (океанských zón)

## 📁 Soubory

| Soubor | Popis |
|--------|-------|
| `export_to_bin.py` | Export z Python do BIN |
| `terrain_loader.hpp` | C++ header pro čtení/zápis BIN |
| `main.cpp` | Příklad C++ programu |
| `bin_to_image.py` | Import z BIN do Python + obrázky |

## 🔑 Klíčové Vlastnosti

✅ **Kompatibilita:** Python ↔ C++
✅ **Komprese:** 4-10x bez ztráty dat
✅ **Rychlost:** Binární I/O
✅ **Flexibilita:** Lze rozšiřovat (version field)
✅ **Paměť:** Row ranges - efektivní uložení
✅ **Přesnost:** uint16 výšky, float32 znečištění

## 🎯 Příklady Použití

### Analýza v C++

```cpp
// Najdi továrnu s max znečištěním
auto max_plant = std::max_element(terrain.plants.begin(), 
                                   terrain.plants.end(),
    [](const auto& a, const auto& b) {
        return a.pollution_tons < b.pollution_tons;
    });

std::cout << "Max znečištění: " << max_plant->pollution_tons << " tun/rok" << std::endl;

// Filtruj továrny v rozsahu
for (const auto& plant : terrain.plants) {
    if (plant.px >= 1000 && plant.px <= 2000 &&
        plant.py >= 1000 && plant.py <= 2000) {
        std::cout << plant.name << std::endl;
    }
}

// Mapuj výšku na znečištění
for (uint32_t y = 0; y < terrain.rows; y++) {
    for (uint32_t x = 0; x < terrain.cols; x++) {
        uint16_t h = terrain.getHeight(x, y);
        float p = terrain.getPollution(x, y);
        
        if (h > 500 && p > 0) {
            std::cout << "Vysoká místa se znečištěním!" << std::endl;
        }
    }
}
```

### Vizualizace v Python

```python
import bin_to_image

# Čti soubor
data = bin_to_image.read_binary("terrain.bin")

# Vytvoř obrázky
bin_to_image.create_height_map_image(data)
bin_to_image.create_pollution_map_image(data)
bin_to_image.create_combined_image(data)

# Statistika
bin_to_image.print_plant_stats(data)
```

## 🔄 Typický Workflow

1. **Příprava dat v Pythonu**
   ```bash
   python3 export_to_bin.py
   # → terrain.bin
   ```

2. **Zpracování v C++**
   ```bash
   g++ -std=c++11 main.cpp -o processor
   ./processor
   # → terrain_modified.bin
   ```

3. **Vizualizace v Pythonu**
   ```bash
   python3 bin_to_image.py
   # → *.png obrázky
   ```

## 📝 Poznámky

- **Row Ranges:** Komprimují 2D pole tím, že ukládají jen nenulové sloupce
- **Znečištění:** Uloženo v tunách za rok (float32) z JSON pole `Emissions`
- **Indexy:** `px, py` jsou přímo indexy do 2D pole `heights[py][px]`
- **Rozšiřitelnost:** Version field (nyní = 2) pro budoucí formáty

## 🎓 Struktura Dat v Paměti (C++)

```cpp
// Height map - komprimovaný
std::vector<uint16_t> height_data;        // Jen nenulové sloupce
std::vector<RowRange> row_ranges;         // Metadata řádků

// Nebo rekonstruovaný
std::vector<std::vector<uint16_t>> heights;  // [rows][cols]

// Zdroje znečištění
std::vector<PlantSource> plants;
  ├─ lat, lon          (float)
  ├─ px, py            (uint32) ← indexy!
  ├─ pollution_tons    (float)
  ├─ name              (string)
  └─ type              (string)
```

---

**Hotovo!** Máš kompletní pipeline Python → BIN ← C++ → PNG
