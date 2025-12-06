/**
 * TerrainLoaderV5 - C++ Header-Only Library
 * ==========================================
 * Čítač V5 binárního formátu
 * 
 * Struktura:
 *   [Header - 60B]
 *   [Row Ranges - 12B each]
 *   [Raw Data - 8B per cell]
 */

#ifndef TERRAIN_LOADER_V5_HPP
#define TERRAIN_LOADER_V5_HPP

#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include <cstring>
#include <iostream>

#pragma pack(push, 1)

struct TerrainHeader {
    uint32_t width;           // Šířka gridu [4B]
    uint32_t height;          // Výška gridu [4B]
    uint32_t num_valid_rows;  // Počet řádků s daty [4B]
    double transform[6];      // Affine transform [48B]
};

struct RowRange {
    uint32_t row_id;          // ID řádku [4B]
    uint32_t col_start;       // Kde začínají data [4B]
    uint32_t col_end;         // Kde končí data [4B]
    
    uint32_t col_count() const {
        return col_end - col_start;
    }
};

#pragma pack(pop)

class TerrainLoaderV5 {
private:
    std::string filename_;
    TerrainHeader header_;
    std::vector<RowRange> row_ranges_;
    std::vector<std::vector<uint16_t>> heights_;
    std::vector<std::vector<float>> pollution_;
    bool loaded_ = false;

public:
    /**
     * Konstruktor
     */
    TerrainLoaderV5(const std::string& filename) : filename_(filename) {}
    
    /**
     * Načti header a row ranges
     */
    bool load_header() {
        std::ifstream file(filename_, std::ios::binary);
        if (!file) {
            std::cerr << "Chyba: Nelze otevřít " << filename_ << std::endl;
            return false;
        }
        
        // Čti header
        file.read(reinterpret_cast<char*>(&header_), sizeof(TerrainHeader));
        if (!file) {
            std::cerr << "Chyba: Nelze číst header" << std::endl;
            return false;
        }
        
        std::cout << "Header: " << header_.width << "×" << header_.height 
                  << " (" << header_.num_valid_rows << " valid rows)" << std::endl;
        
        // Čti row ranges
        row_ranges_.resize(header_.num_valid_rows);
        file.read(reinterpret_cast<char*>(row_ranges_.data()), 
                  header_.num_valid_rows * sizeof(RowRange));
        
        if (!file) {
            std::cerr << "Chyba: Nelze číst row ranges" << std::endl;
            return false;
        }
        
        return true;
    }
    
    /**
     * Načti všechna data do paměti
     */
    bool load_all_data() {
        if (row_ranges_.empty()) {
            std::cerr << "Chyba: Nejprve zavolej load_header()" << std::endl;
            return false;
        }
        
        // Inicializuj 2D pole
        heights_.assign(header_.height, std::vector<uint16_t>(header_.width, 0));
        pollution_.assign(header_.height, std::vector<float>(header_.width, 0.0f));
        
        std::ifstream file(filename_, std::ios::binary);
        if (!file) return false;
        
        // Přeskoč header a row ranges
        file.seekg(sizeof(TerrainHeader) + header_.num_valid_rows * sizeof(RowRange));
        
        // Čti raw data
        for (const auto& rr : row_ranges_) {
            for (uint32_t col = rr.col_start; col < rr.col_end; ++col) {
                uint16_t h;
                float p;
                file.read(reinterpret_cast<char*>(&h), sizeof(uint16_t));
                file.read(reinterpret_cast<char*>(&p), sizeof(float));
                
                heights_[rr.row_id][col] = h;
                pollution_[rr.row_id][col] = p;
            }
        }
        
        loaded_ = true;
        std::cout << "Všechna data načtena (" << header_.num_valid_rows 
                  << " řádků)" << std::endl;
        
        return true;
    }
    
    /**
     * Accessors
     */
    
    const TerrainHeader& get_header() const { return header_; }
    const std::vector<RowRange>& get_row_ranges() const { return row_ranges_; }
    
    uint16_t get_height(uint32_t row, uint32_t col) const {
        if (!loaded_ || row >= header_.height || col >= header_.width) {
            return 0;
        }
        return heights_[row][col];
    }
    
    float get_pollution(uint32_t row, uint32_t col) const {
        if (!loaded_ || row >= header_.height || col >= header_.width) {
            return 0.0f;
        }
        return pollution_[row][col];
    }
    
    const std::vector<std::vector<uint16_t>>& get_heights() const {
        return heights_;
    }
    
    const std::vector<std::vector<float>>& get_pollution() const {
        return pollution_;
    }
    
    /**
     * Info
     */
    bool is_loaded() const { return loaded_; }
    
    void print_info() const {
        std::cout << "\n=== Terrain V5 Info ===" << std::endl;
        std::cout << "Soubor: " << filename_ << std::endl;
        std::cout << "Rozměry: " << header_.width << "×" << header_.height << std::endl;
        std::cout << "Valid rows: " << header_.num_valid_rows << std::endl;
        std::cout << "Loaded: " << (loaded_ ? "Yes" : "No") << std::endl;
        
        if (!row_ranges_.empty()) {
            uint64_t total_cells = 0;
            for (const auto& rr : row_ranges_) {
                total_cells += rr.col_count();
            }
            std::cout << "Total cells: " << total_cells << std::endl;
        }
        std::cout << "======================\n" << std::endl;
    }
};

#endif // TERRAIN_LOADER_V5_HPP
