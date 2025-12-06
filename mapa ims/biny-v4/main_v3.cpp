/**
 * Main V5 - C++ Example with Save
 * ===============================
 * Příklad použití TerrainLoaderV5 s možností zápisu
 */

#include "terrain_loader_v5.hpp"
#include <iostream>
#include <cmath>

int main() {
    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "╔" << std::string(68, '=') << "╗" << std::endl;
    std::cout << "║" << std::string(12, ' ') << "TERRAIN LOADER V5 - C++ EXAMPLE WITH SAVE" 
              << std::string(15, ' ') << "║" << std::endl;
    std::cout << "╚" << std::string(68, '=') << "╝" << std::endl;
    std::cout << std::string(70, '=') << "\n\n";
    
    // ===== KROK 1: Vytvoř loader =====
    std::cout << " KROK 1: VYTVOŘENÍ LOADERU" << std::endl;
    TerrainLoaderV5 loader("terrain.bin");
    std::cout << " ✓ Loader vytvořen\n" << std::endl;
    
    // ===== KROK 2: Načti header =====
    std::cout << " KROK 2: ČTENÍ HEADERU" << std::endl;
    if (!loader.load_header()) {
        std::cerr << " ✗ Chyba: Nelze načíst header" << std::endl;
        return 1;
    }
    std::cout << " ✓ Header načten\n" << std::endl;
    
    // ===== KROK 3: Načti všechna data =====
    std::cout << " KROK 3: ČTENÍ VŠECH DAT" << std::endl;
    if (!loader.load_all_data()) {
        std::cerr << " ✗ Chyba: Nelze načíst data" << std::endl;
        return 1;
    }
    std::cout << " ✓ Všechna data načtena\n" << std::endl;
    
    // ===== KROK 4: Vypiš info =====
    std::cout << " KROK 4: INFORMACE O TERRENU" << std::endl;
    loader.print_info();
    
    // ===== KROK 5: Přistupuj k datům =====
    std::cout << " KROK 5: PŘÍSTUP K DATŮM" << std::endl;
    
    // Jednotlivé buňky
    uint16_t h = loader.get_height(100, 200);
    float p = loader.get_pollution(100, 200);
    std::cout << " Buňka [100, 200]:" << std::endl;
    std::cout << "  - Výška: " << h << " m" << std::endl;
    std::cout << "  - Znečištění: " << p << " units\n" << std::endl;
    
    // ===== KROK 6: Zpracuj data =====
    std::cout << " KROK 6: ANALÝZA DAT - PŘED MODIFIKACÍ" << std::endl;
    const auto& heights = loader.get_heights();
    const auto& pollution = loader.get_pollution();
    
    // Statistika
    uint64_t total_cells = 0;
    uint64_t cells_with_data = 0;
    double sum_height = 0;
    double sum_pollution = 0;
    double max_height = 0;
    double max_pollution = 0;
    
    for (size_t r = 0; r < heights.size(); ++r) {
        for (size_t c = 0; c < heights[r].size(); ++c) {
            total_cells++;
            if (heights[r][c] > 0) {
                cells_with_data++;
                sum_height += heights[r][c];
                sum_pollution += pollution[r][c];
                if (heights[r][c] > max_height) max_height = heights[r][c];
                if (pollution[r][c] > max_pollution) max_pollution = pollution[r][c];
            }
        }
    }
    
    double avg_height = cells_with_data > 0 ? sum_height / cells_with_data : 0;
    double avg_pollution = cells_with_data > 0 ? sum_pollution / cells_with_data : 0;
    
    std::cout << " 📊 STATISTIKA PŘED:" << std::endl;
    std::cout << "  Total buněk: " << total_cells << std::endl;
    std::cout << "  Buněk s daty: " << cells_with_data << std::endl;
    std::cout << "  Průměrná výška: " << avg_height << " m" << std::endl;
    std::cout << "  Max výška: " << max_height << " m" << std::endl;
    std::cout << "  Průměrné znečištění: " << avg_pollution << " units" << std::endl;
    std::cout << "  Max znečištění: " << max_pollution << " units\n" << std::endl;
    
    // ===== KROK 7: Modifikuj data =====
    std::cout << " KROK 7: MODIFIKACE DAT" << std::endl;
    std::cout << " Zvýšení znečištění v oblasti kolem továren...\n" << std::endl;
    
    // Příklad: Zvýš znečištění v určité oblasti (např. kolem továren)
    // Např. obdélník od [2500-3000] x [3200-3700]
    auto& heights_mut = loader.get_heights_mut();
    auto& pollution_mut = loader.get_pollution_mut();
    
    uint32_t mod_count = 0;
    for (size_t r = 2500; r < 3000 && r < heights_mut.size(); ++r) {
        for (size_t c = 3200; c < 3700 && c < heights_mut[r].size(); ++c) {
            // Zvýš znečištění proporcionálně k výšce
            if (heights_mut[r][c] > 0) {
                float factor = 1.5f;  // Zvýšení o 50%
                pollution_mut[r][c] *= factor;
                mod_count++;
            }
        }
    }
    
    std::cout << " ✓ Modifikováno " << mod_count << " buněk" << std::endl;
    std::cout << " Znečištění zvýšeno o 50% v oblasti [2500-3000] x [3200-3700]\n" << std::endl;
    
    // ===== KROK 8: Analýza DAT - PO MODIFIKACI =====
    std::cout << " KROK 8: ANALÝZA DAT - PO MODIFIKACI" << std::endl;
    
    // Nová statistika
    sum_height = 0;
    sum_pollution = 0;
    max_height = 0;
    max_pollution = 0;
    cells_with_data = 0;
    
    for (size_t r = 0; r < heights_mut.size(); ++r) {
        for (size_t c = 0; c < heights_mut[r].size(); ++c) {
            if (heights_mut[r][c] > 0) {
                cells_with_data++;
                sum_height += heights_mut[r][c];
                sum_pollution += pollution_mut[r][c];
                if (heights_mut[r][c] > max_height) max_height = heights_mut[r][c];
                if (pollution_mut[r][c] > max_pollution) max_pollution = pollution_mut[r][c];
            }
        }
    }
    
    avg_height = cells_with_data > 0 ? sum_height / cells_with_data : 0;
    avg_pollution = cells_with_data > 0 ? sum_pollution / cells_with_data : 0;
    
    std::cout << " 📊 STATISTIKA PO:" << std::endl;
    std::cout << "  Buněk s daty: " << cells_with_data << std::endl;
    std::cout << "  Průměrná výška: " << avg_height << " m" << std::endl;
    std::cout << "  Max výška: " << max_height << " m" << std::endl;
    std::cout << "  Průměrné znečištění: " << avg_pollution << " units" << std::endl;
    std::cout << "  Max znečištění: " << max_pollution << " units\n" << std::endl;
    
    // ===== KROK 9: Zapiš modifikovaná data =====
    std::cout << " KROK 9: ZÁPIS MODIFIKOVANÝCH DAT" << std::endl;
    if (!loader.save_to_binary("terrain_modified.bin")) {
        std::cerr << " ✗ Chyba: Nelze zapsat data" << std::endl;
        return 1;
    }
    std::cout << " ✓ Data uložena do terrain_modified.bin\n" << std::endl;
    
    std::cout << std::string(70, '=') << std::endl;
    std::cout << " ✓ PROGRAM HOTOV!" << std::endl;
    std::cout << std::string(70, '=') << "\n" << std::endl;
    
    std::cout << " Příští krok:" << std::endl;
    std::cout << "  $ python3 bin_to_image_v5_msk_only.py" << std::endl;
    std::cout << "  (Změň 'terrain.bin' na 'terrain_modified.bin' v kódu)\n" << std::endl;
    
    return 0;
}