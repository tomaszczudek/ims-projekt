#include <iostream>
#include <fstream>
#include <cstdint>
#include <vector>
#include <cstring>
#include <algorithm>
#include <iomanip>

struct PollutionSource {
    char name[64];
    float lat, lon;
    char type[32];
};

struct Grid {
    int rows = 2000;
    int cols = 1600;
    int downsample_rate = 5;
    int num_sources = 0;
    uint8_t* heights = nullptr;
    std::vector<PollutionSource> sources;
};

bool loadBinary(const char* filename, Grid& grid) {
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "✗ Chyba: Nelze otevřít " << filename << std::endl;
        return false;
    }
    
    uint32_t r, c, d, s;
    file.read((char*)&r, sizeof(uint32_t));
    file.read((char*)&c, sizeof(uint32_t));
    file.read((char*)&d, sizeof(uint32_t));
    file.read((char*)&s, sizeof(uint32_t));
    
    grid.heights = new uint8_t[r * c];
    file.read((char*)grid.heights, r * c * sizeof(uint8_t));
    
    std::cout << "✓ Načteny výšky: " << r << " × " << c << " = " << (r*c/1000) << "k pixelů" << std::endl;
    
    for (uint32_t i = 0; i < s; ++i) {
        PollutionSource source;
        
        uint8_t name_len;
        file.read((char*)&name_len, sizeof(uint8_t));
        file.read(source.name, 64);
        
        file.read((char*)&source.lat, sizeof(float));
        file.read((char*)&source.lon, sizeof(float));
        
        uint8_t type_len;
        file.read((char*)&type_len, sizeof(uint8_t));
        file.read(source.type, 32);
        
        grid.sources.push_back(source);
    }
    
    std::cout << "✓ Načteny zdroje: " << s << " zdrojů znečištění" << std::endl;
    
    file.close();
    return true;
}

int main() {
    std::cout << "\n╔════════════════════════════════════════════════╗" << std::endl;
    std::cout << "║  MS KRAJ - VÝŠKY + ZDROJE ZNEČIŠTĚNÍ         ║" << std::endl;
    std::cout << "╚════════════════════════════════════════════════╝\n" << std::endl;
    
    Grid grid;
    if (!loadBinary("ms_complete_data.bin", grid)) return 1;
    
    std::cout << "\n--- TOPOGRAFIE ---\n" << std::endl;
    uint8_t min_h = 255, max_h = 0;
    double sum = 0;
    int count = 0;
    for (int i = 0; i < grid.rows * grid.cols; ++i) {
        if (grid.heights[i] > 0) {
            min_h = std::min(min_h, grid.heights[i]);
            max_h = std::max(max_h, grid.heights[i]);
            sum += grid.heights[i];
            count++;
        }
    }
    double mean = count > 0 ? sum / count : 0;
    
    std::cout << "  Min výška: " << (int)min_h * 10 << " m" << std::endl;
    std::cout << "  Max výška: " << (int)max_h * 10 << " m" << std::endl;
    std::cout << "  Průměr: " << std::fixed << std::setprecision(1) << mean * 10 << " m" << std::endl;
    
    std::cout << "\n--- ZDROJE ZNEČIŠTĚNÍ ---\n" << std::endl;
    std::cout << "  Celkem zdrojů: " << grid.sources.size() << "\n" << std::endl;
    
    for (size_t i = 0; i < grid.sources.size() && i < 15; ++i) {
        std::cout << "  " << (i+1) << ". " << grid.sources[i].name << std::endl;
        std::cout << "     Typ: " << grid.sources[i].type << std::endl;
        std::cout << "     GPS: " << std::fixed << std::setprecision(4) 
                  << grid.sources[i].lat << "°N, " << grid.sources[i].lon << "°E" << std::endl;
    }
    
    if (grid.sources.size() > 15) {
        std::cout << "  ... a " << (grid.sources.size() - 15) << " dalších" << std::endl;
    }
    
    delete[] grid.heights;
    return 0;
}
