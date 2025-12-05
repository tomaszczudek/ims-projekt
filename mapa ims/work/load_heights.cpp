#include <iostream>
#include <fstream>
#include <cstdint>
#include <cstring>
#include <algorithm>

struct Grid {
    int rows = 21157;
    int cols = 25299;
    uint16_t* heights = nullptr;
};

bool loadBinary(const char* filename, Grid& grid) {
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "Chyba: Nelze otevřít " << filename << std::endl;
        return false;
    }
    
    uint32_t r, c;
    file.read((char*)&r, sizeof(uint32_t));
    file.read((char*)&c, sizeof(uint32_t));
    
    grid.heights = new uint16_t[r * c];
    file.read((char*)grid.heights, r * c * sizeof(uint16_t));
    
    std::cout << "✓ Načteno: " << r << " × " << c << " grid" << std::endl;
    
    file.close();
    return true;
}

int main() {
    std::cout << "\n=== NADMOŘSKÉ VÝŠKY - MS KRAJ ===\n\n";
    
    Grid grid;
    if (!loadBinary("ms_heights.bin", grid)) return 1;
    
    std::cout << "✓ Data úspěšně načtena!\n\n";
    
    // Vypočítej statistiku
    uint16_t min_h = UINT16_MAX, max_h = 0;
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
    
    std::cout << "Statistika:\n";
    std::cout << "  Min: " << min_h << " m\n";
    std::cout << "  Max: " << max_h << " m\n";
    std::cout << "  Mean: " << mean << " m\n";
    std::cout << "  Platných pixelů: " << count << "/" << (grid.rows * grid.cols) << "\n";
    
    delete[] grid.heights;
    return 0;
}
