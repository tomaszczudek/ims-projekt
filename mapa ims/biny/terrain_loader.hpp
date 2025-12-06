#ifndef TERRAIN_LOADER_HPP
#define TERRAIN_LOADER_HPP

#include <vector>
#include <string>
#include <fstream>
#include <cstdint>
#include <iostream>
#include <algorithm>

/**
 * RowRange metadata
 */
struct RowRange {
    uint32_t row_id;
    uint32_t col_start;
    uint32_t col_end;
    uint16_t col_count;
    size_t data_offset;
};

/**
 * Растения - zdroj znečištění
 */
struct PlantSource {
    float lat, lon;
    uint32_t px, py;
    float pollution_tons;
    std::string name;
    std::string type;
};

/**
 * TerrainLoader - Čtení/zápis binárního souboru
 */
class TerrainLoader {
public:
    uint32_t rows, cols;
    std::vector<RowRange> row_ranges;
    std::vector<uint16_t> height_data;
    std::vector<std::vector<uint16_t>> heights;
    std::vector<PlantSource> plants;
    
    /**
     * Načti z binárního souboru
     */
    bool loadFromBinary(const std::string& filename) {
        std::ifstream file(filename, std::ios::binary);
        if (!file.is_open()) {
            std::cerr << "✗ Nelze otevřít: " << filename << std::endl;
            return false;
        }
        
        // Čti HEADER
        uint32_t num_row_ranges, version;
        file.read((char*)&rows, sizeof(uint32_t));
        file.read((char*)&cols, sizeof(uint32_t));
        uint32_t num_plants;
        file.read((char*)&num_plants, sizeof(uint32_t));
        file.read((char*)&num_row_ranges, sizeof(uint32_t));
        file.read((char*)&version, sizeof(uint32_t));
        
        if (!file.good()) {
            std::cerr << "✗ Chyba při čtení headeru" << std::endl;
            return false;
        }
        
        std::cout << "✓ Header: " << rows << "×" << cols << ", "
                  << num_row_ranges << " řádků, " << num_plants << " továren" << std::endl;
        
        // Čti ROW RANGES
        row_ranges.resize(num_row_ranges);
        size_t data_offset = 0;
        
        for (uint32_t i = 0; i < num_row_ranges; i++) {
            RowRange& r = row_ranges[i];
            file.read((char*)&r.row_id, sizeof(uint32_t));
            file.read((char*)&r.col_start, sizeof(uint32_t));
            file.read((char*)&r.col_end, sizeof(uint32_t));
            file.read((char*)&r.col_count, sizeof(uint16_t));
            
            r.data_offset = data_offset;
            data_offset += r.col_count;
        }
        
        // Čti HEIGHT DATA
        height_data.resize(data_offset);
        file.read((char*)height_data.data(), data_offset * sizeof(uint16_t));
        
        if (!file.good()) {
            std::cerr << "✗ Chyba při čtení height dat" << std::endl;
            return false;
        }
        
        std::cout << "✓ Height data: " << data_offset << " pixelů" << std::endl;
        
        // Čti PLANTS
        plants.clear();
        for (uint32_t p = 0; p < num_plants; p++) {
            PlantSource plant;
            
            file.read((char*)&plant.lat, sizeof(float));
            file.read((char*)&plant.lon, sizeof(float));
            file.read((char*)&plant.px, sizeof(uint32_t));
            file.read((char*)&plant.py, sizeof(uint32_t));
            file.read((char*)&plant.pollution_tons, sizeof(float));
            
            // Čti jméno
            uint16_t name_len;
            file.read((char*)&name_len, sizeof(uint16_t));
            if (name_len > 0) {
                plant.name.resize(name_len);
                file.read(plant.name.data(), name_len);
            }
            
            // Čti typ
            uint16_t type_len;
            file.read((char*)&type_len, sizeof(uint16_t));
            if (type_len > 0) {
                plant.type.resize(type_len);
                file.read(plant.type.data(), type_len);
            }
            
            plants.push_back(plant);
        }
        
        std::cout << "✓ Načteno " << plants.size() << " továren" << std::endl;
        return true;
    }
    
    /**
     * Ulož do binárního souboru (pro C++ -> Python workflow)
     */
    bool saveToBinary(const std::string& filename) {
        std::cout << "\n✓ Zápis do: " << filename << std::endl;
        
        std::ofstream file(filename, std::ios::binary);
        if (!file.is_open()) {
            std::cerr << "✗ Nelze otevřít pro zápis: " << filename << std::endl;
            return false;
        }
        
        // HEADER
        file.write((char*)&rows, sizeof(uint32_t));
        file.write((char*)&cols, sizeof(uint32_t));
        uint32_t num_plants = plants.size();
        file.write((char*)&num_plants, sizeof(uint32_t));
        uint32_t num_row_ranges = row_ranges.size();
        file.write((char*)&num_row_ranges, sizeof(uint32_t));
        uint32_t version = 2;
        file.write((char*)&version, sizeof(uint32_t));
        
        // ROW RANGES
        for (const auto& r : row_ranges) {
            file.write((char*)&r.row_id, sizeof(uint32_t));
            file.write((char*)&r.col_start, sizeof(uint32_t));
            file.write((char*)&r.col_end, sizeof(uint32_t));
            file.write((char*)&r.col_count, sizeof(uint16_t));
        }
        
        // HEIGHT DATA
        file.write((char*)height_data.data(), height_data.size() * sizeof(uint16_t));
        
        // PLANTS
        for (const auto& p : plants) {
            file.write((char*)&p.lat, sizeof(float));
            file.write((char*)&p.lon, sizeof(float));
            file.write((char*)&p.px, sizeof(uint32_t));
            file.write((char*)&p.py, sizeof(uint32_t));
            file.write((char*)&p.pollution_tons, sizeof(float));
            
            uint16_t name_len = p.name.length();
            file.write((char*)&name_len, sizeof(uint16_t));
            file.write(p.name.c_str(), name_len);
            
            uint16_t type_len = p.type.length();
            file.write((char*)&type_len, sizeof(uint16_t));
            file.write(p.type.c_str(), type_len);
        }
        
        file.close();
        std::cout << "  ✓ Zápis hotov" << std::endl;
        return true;
    }
    
    /**
     * Rekonstruuj 2D pole z komprimovaných dat
     */
    void reconstructHeightMap() {
        std::cout << "🔨 Rekonstrukce 2D pole..." << std::endl;
        
        heights.assign(rows, std::vector<uint16_t>(cols, 0));
        
        for (const auto& rr : row_ranges) {
            const uint16_t* data_ptr = height_data.data() + rr.data_offset;
            std::copy(data_ptr, data_ptr + rr.col_count,
                     heights[rr.row_id].begin() + rr.col_start);
        }
        
        std::cout << "  ✓ Hotovo" << std::endl;
    }
    
    /**
     * Gettery
     */
    uint16_t getHeight(uint32_t x, uint32_t y) const {
        if (y >= rows) return 0;
        
        for (const auto& rr : row_ranges) {
            if (rr.row_id == y) {
                if (x >= rr.col_start && x < rr.col_end) {
                    size_t idx = rr.data_offset + (x - rr.col_start);
                    return height_data[idx];
                }
                return 0;
            }
        }
        return 0;
    }
    
    float getPollution(uint32_t x, uint32_t y) const {
        for (const auto& p : plants) {
            if (p.px == x && p.py == y) {
                return p.pollution_tons;
            }
        }
        return 0.0f;
    }
    
    /**
     * Statistika
     */
    void printStatistics() const {
        std::cout << "\n╔════════════════════════════════════════════╗" << std::endl;
        std::cout << "║            STATISTIKA TERÉNU               ║" << std::endl;
        std::cout << "╚════════════════════════════════════════════╝" << std::endl;
        
        std::cout << "\n📊 GRID:" << std::endl;
        std::cout << "  Rozměr: " << rows << " × " << cols << std::endl;
        std::cout << "  Řádků s daty: " << row_ranges.size() << " / " << rows << std::endl;
        
        if (!height_data.empty()) {
            uint16_t min_h = *std::min_element(height_data.begin(), height_data.end());
            uint16_t max_h = *std::max_element(height_data.begin(), height_data.end());
            uint32_t sum_h = 0;
            for (uint16_t h : height_data) sum_h += h;
            
            float avg_h = (float)sum_h / height_data.size();
            std::cout << "\n📈 VÝŠKY:" << std::endl;
            std::cout << "  Min: " << min_h << " m" << std::endl;
            std::cout << "  Max: " << max_h << " m" << std::endl;
            std::cout << "  Průměr: " << avg_h << " m" << std::endl;
        }
        
        std::cout << "\n🏭 TOVÁRNY:" << std::endl;
        std::cout << "  Počet: " << plants.size() << std::endl;
        
        float total_pollution = 0.0f;
        for (const auto& p : plants) {
            total_pollution += p.pollution_tons;
        }
        
        if (!plants.empty()) {
            std::cout << "  Celkové znečištění: " << total_pollution << " tun/rok" << std::endl;
            std::cout << "  Průměr: " << total_pollution / plants.size() << " tun/rok" << std::endl;
        }
        
        std::cout << "\n" << std::endl;
    }
};

#endif
