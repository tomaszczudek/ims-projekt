/*
PŘÍKLAD C++ PROGRAMU
- Čte terrain.bin
- Provede analýzu/modifikaci
- Exportuje do terrain_modified.bin
*/

#include "terrain_loader.hpp"
#include <iostream>

int main() {
    std::cout << "\n╔════════════════════════════════════════════╗" << std::endl;
    std::cout << "║   C++ TERRAIN PROCESSOR                    ║" << std::endl;
    std::cout << "╚════════════════════════════════════════════╝" << std::endl;
    
    // ===== ČTENÍ =====
    TerrainLoader terrain;
    if (!terrain.loadFromBinary("terrain.bin")) {
        std::cerr << "✗ Chyba: Nelze načíst terrain.bin" << std::endl;
        return 1;
    }
    
    // Vypis statistiky
    terrain.printStatistics();
    
    // ===== ZPRACOVÁNÍ (PŘÍKLAD) =====
    std::cout << "\n🔨 ZPRACOVÁNÍ..." << std::endl;
    
    // Rekonstruuj 2D pole (pokud chceš standardní přístup)
    terrain.reconstructHeightMap();
    
    // PŘÍKLAD 1: Analyzuj výšky
    std::cout << "\n📍 PŘÍKLAD 1: Výšky v gridu" << std::endl;
    int count = 0;
    for (uint32_t y = 0; y < terrain.rows && count < 5; y++) {
        for (uint32_t x = 0; x < terrain.cols && count < 5; x++) {
            uint16_t h = terrain.getHeight(x, y);
            if (h > 0) {
                std::cout << "  (" << x << "," << y << "): " << h << "m" << std::endl;
                count++;
            }
        }
    }
    
    // PŘÍKLAD 2: Analýza továren
    std::cout << "\n📍 PŘÍKLAD 2: Analýza továren" << std::endl;
    for (size_t i = 0; i < terrain.plants.size() && i < 5; i++) {
        const auto& plant = terrain.plants[i];
        uint16_t height = terrain.getHeight(plant.px, plant.py);
        
        std::cout << "  " << plant.name << std::endl;
        std::cout << "    GPS: " << plant.lat << ", " << plant.lon << std::endl;
        std::cout << "    Index: (" << plant.px << ", " << plant.py << ")" << std::endl;
        std::cout << "    Výška: " << height << "m" << std::endl;
        std::cout << "    Znečištění: " << plant.pollution_tons << " tun/rok" << std::endl;
    }
    
    // PŘÍKLAD 3: Modifikace (např. snížení znečištění o 10%)
    std::cout << "\n📍 PŘÍKLAD 3: Modifikace - snížení znečištění o 10%" << std::endl;
    float total_before = 0, total_after = 0;
    
    for (auto& plant : terrain.plants) {
        total_before += plant.pollution_tons;
        plant.pollution_tons *= 0.9f;  // 10% snížení
        total_after += plant.pollution_tons;
    }
    
    std::cout << "  Před: " << total_before << " tun/rok" << std::endl;
    std::cout << "  Po: " << total_after << " tun/rok" << std::endl;
    std::cout << "  Úspora: " << (total_before - total_after) << " tun/rok" << std::endl;
    
    // ===== EXPORTOVÁNÍ ZPÁTKY =====
    std::cout << "\n💾 EXPORT DO BINÁRNÍHO SOUBORU..." << std::endl;
    if (terrain.saveToBinary("terrain_modified.bin")) {
        std::cout << "✓ Exportováno: terrain_modified.bin" << std::endl;
    } else {
        std::cerr << "✗ Chyba při exportu!" << std::endl;
        return 1;
    }
    
    std::cout << "\n✓ HOTOVO!" << std::endl;
    std::cout << "Nyní spusť: python3 bin_to_image.py" << std::endl;
    std::cout << "Pro generování obrázků!\n" << std::endl;
    
    return 0;
}

/*
KOMPILACE:
  g++ -std=c++11 -O2 main.cpp -o terrain_processor

SPUŠTĚNÍ:
  ./terrain_processor

WORKFLOW:
  1. python3 export_to_bin.py     → terrain.bin
  2. ./terrain_processor          → terrain_modified.bin
  3. python3 bin_to_image.py      → PNG obrázky
*/
