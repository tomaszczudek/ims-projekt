#include <iostream>
#include "terrain_loader_v3_FIXED.hpp"

int main() {
    std::cout << "\n╔════════════════════════════════════════════╗" << std::endl;
    std::cout << "║   TERRAIN PROCESSOR V3                     ║" << std::endl;
    std::cout << "║   Čte: terrain.bin                         ║" << std::endl;
    std::cout << "║   Exportuje: terrain_modified.bin           ║" << std::endl;
    std::cout << "╚════════════════════════════════════════════╝\n" << std::endl;

    // Načti originální
    TerrainLoaderV3 terrain;
    if (!terrain.loadFromBinary("terrain.bin")) {
        std::cerr << "✗ Chyba při čtení terrain.bin" << std::endl;
        return 1;
    }

    terrain.printStatistics();

    // TADY BY BYLA MODIFIKACE ZNEČIŠTĚNÍ
    // Např. výpočet znečištění z továren

    // Exportuj
    if (!terrain.saveToBinary("terrain_modified.bin")) {
        std::cerr << "✗ Chyba při zápisu terrain_modified.bin" << std::endl;
        return 1;
    }

    std::cout << "✓ HOTOVO!" << std::endl;
    return 0;
}
