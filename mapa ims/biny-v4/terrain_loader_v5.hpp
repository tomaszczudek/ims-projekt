#ifndef TERRAIN_LOADER_V5_HPP
#define TERRAIN_LOADER_V5_HPP

#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include <cstring>

#pragma pack(push, 1)

/**
 * TERRAIN LOADER V5 - COMPACT FORMAT
 * ===================================
 * 
 * Čte binární soubor s kompaktním metadatem a row ranges
 * 
 * FORMÁT:
 *   Header (60B):
 *     uint32 width [4B]
 *     uint32 height [4B]
 *     uint32 num_valid_rows [4B]
 *     double transform[6] [48B]
 * 
 *   Row Ranges (12B per row):
 *     uint32 row_id [4B]
 *     uint32 col_start [4B]
 *     uint32 col_end [4B]
 * 
 *   Data:
 *     [height (uint16) | pollution (float)] * (col_end - col_start)
 */

struct RowRange {
    uint32_t row_id;
    uint32_t col_start;
    uint32_t col_end;
    
    uint32_t col_count() const {
        return col_end - col_start;
    }
};

struct TerrainHeader {
    uint32_t width;
    uint32_t height;
    uint32_t num_valid_rows;
    double transform[6];  // a, b, c, d, e, f
};

#pragma pack(pop)

class TerrainLoaderV5 {
private:
    std::string filepath_;
    TerrainHeader header_;
    std::vector<RowRange> row_ranges_;
    std::ifstream file_;
    
    // 2D arrays pro cached data
    std::vector<std::vector<uint16_t>> heights_;
    std::vector<std::vector<float>> pollution_;
    bool cache_loaded_ = false;

public:
    TerrainLoaderV5(const std::string& path) : filepath_(path) {}
    
    /**
     * Načti header a row ranges
     */
    bool load_header() {
        file_.open(filepath_, std::ios::binary);
        if (!file_) {
            std::cerr << "✗ Chyba: Nelze otevřít " << filepath_ << std::endl;
            return false;
        }
        
        // Čti header (60B: 4+4+4+48)
        file_.read(reinterpret_cast<char*>(&header_.width), sizeof(uint32_t));
        file_.read(reinterpret_cast<char*>(&header_.height), sizeof(uint32_t));
        file_.read(reinterpret_cast<char*>(&header_.num_valid_rows), sizeof(uint32_t));
        
        for (int i = 0; i < 6; i++) {
            file_.read(reinterpret_cast<char*>(&header_.transform[i]), sizeof(double));
        }
        
        std::cout << " ✓ Header:" << std::endl;
        std::cout << "   Width: " << header_.width << std::endl;
        std::cout << "   Height: " << header_.height << std::endl;
        std::cout << "   Valid rows: " << header_.num_valid_rows << std::endl;
        std::cout << "   Transform: [" << header_.transform[0] << ", " 
                  << header_.transform[2] << ", " << header_.transform[4] << "]" << std::endl;
        
        // Čti row ranges (12B per row)
        row_ranges_.reserve(header_.num_valid_rows);
        for (uint32_t i = 0; i < header_.num_valid_rows; i++) {
            RowRange rr;
            file_.read(reinterpret_cast<char*>(&rr.row_id), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&rr.col_start), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&rr.col_end), sizeof(uint32_t));
            row_ranges_.push_back(rr);
        }
        
        std::cout << " ✓ Row ranges: " << row_ranges_.size() << std::endl;
        return true;
    }
    
    /**
     * Načti všechna data do 2D polí (height, pollution)
     */
    bool load_all_data() {
        if (row_ranges_.empty()) {
            std::cerr << "✗ Nejdřív zavolej load_header()!" << std::endl;
            return false;
        }
        
        // Inicializuj 2D pole
        heights_.resize(header_.height);
        pollution_.resize(header_.height);
        for (uint32_t row = 0; row < header_.height; row++) {
            heights_[row].resize(header_.width, 0);
            pollution_[row].resize(header_.width, 0.0f);
        }
        
        std::cout << " 📊 Čtení dat..." << std::endl;
        
        // Čti data podle row ranges
        for (const auto& rr : row_ranges_) {
            uint32_t row_id = rr.row_id;
            uint32_t col_count = rr.col_count();
            
            for (uint32_t col = 0; col < col_count; col++) {
                uint16_t h;
                float p;
                file_.read(reinterpret_cast<char*>(&h), sizeof(uint16_t));
                file_.read(reinterpret_cast<char*>(&p), sizeof(float));
                
                heights_[row_id][rr.col_start + col] = h;
                pollution_[row_id][rr.col_start + col] = p;
            }
        }
        
        std::cout << " ✓ Všechna data načtena" << std::endl;
        cache_loaded_ = true;
        return true;
    }
    
    /**
     * Accessor - vrať výšku na [row, col]
     */
    uint16_t get_height(uint32_t row, uint32_t col) const {
        if (!cache_loaded_) {
            std::cerr << "✗ Nejdřív zavolej load_all_data()!" << std::endl;
            return 0;
        }
        
        if (row >= header_.height || col >= header_.width) {
            return 0;
        }
        
        return heights_[row][col];
    }
    
    /**
     * Accessor - vrať znečištění na [row, col]
     */
    float get_pollution(uint32_t row, uint32_t col) const {
        if (!cache_loaded_) {
            std::cerr << "✗ Nejdřív zavolej load_all_data()!" << std::endl;
            return 0.0f;
        }
        
        if (row >= header_.height || col >= header_.width) {
            return 0.0f;
        }
        
        return pollution_[row][col];
    }
    
    /**
     * Setter - nastav výšku na [row, col]
     */
    void set_height(uint32_t row, uint32_t col, uint16_t value) {
        if (!cache_loaded_ || row >= header_.height || col >= header_.width) {
            return;
        }
        heights_[row][col] = value;
    }
    
    /**
     * Setter - nastav znečištění na [row, col]
     */
    void set_pollution(uint32_t row, uint32_t col, float value) {
        if (!cache_loaded_ || row >= header_.height || col >= header_.width) {
            return;
        }
        pollution_[row][col] = value;
    }
    
    /**
     * Getter - header
     */
    const TerrainHeader& get_header() const {
        return header_;
    }
    
    /**
     * Getter - row ranges
     */
    const std::vector<RowRange>& get_row_ranges() const {
        return row_ranges_;
    }
    
    /**
     * Getter - 2D pole výšek
     */
    const std::vector<std::vector<uint16_t>>& get_heights() const {
        return heights_;
    }
    
    /**
     * Getter - 2D pole znečištění
     */
    const std::vector<std::vector<float>>& get_pollution() const {
        return pollution_;
    }
    
    /**
     * Non-const getter - 2D pole výšek (pro modifikace)
     */
    std::vector<std::vector<uint16_t>>& get_heights_mut() {
        return heights_;
    }
    
    /**
     * Non-const getter - 2D pole znečištění (pro modifikace)
     */
    std::vector<std::vector<float>>& get_pollution_mut() {
        return pollution_;
    }
    
    /**
     * Zapiš modifikovaná data zpátky do BIN souboru
     */
    bool save_to_binary(const std::string& output_path) {
        if (!cache_loaded_) {
            std::cerr << "✗ Nejdřív zavolej load_all_data()!" << std::endl;
            return false;
        }
        
        std::ofstream out(output_path, std::ios::binary);
        if (!out) {
            std::cerr << "✗ Chyba: Nelze otevřít " << output_path << std::endl;
            return false;
        }
        
        std::cout << " 📝 Zapis do " << output_path << "..." << std::endl;
        
        // Zapiš header (60B)
        out.write(reinterpret_cast<char*>(&header_.width), sizeof(uint32_t));
        out.write(reinterpret_cast<char*>(&header_.height), sizeof(uint32_t));
        out.write(reinterpret_cast<char*>(&header_.num_valid_rows), sizeof(uint32_t));
        
        for (int i = 0; i < 6; i++) {
            out.write(reinterpret_cast<char*>(&header_.transform[i]), sizeof(double));
        }
        
        std::cout << " ✓ Header zapsán (60B)" << std::endl;
        
        // Zapiš row ranges (12B each)
        for (const auto& rr : row_ranges_) {
            uint32_t row_id = rr.row_id;
            uint32_t col_start = rr.col_start;
            uint32_t col_end = rr.col_end;
            
            out.write(reinterpret_cast<char*>(&row_id), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(&col_start), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(&col_end), sizeof(uint32_t));
        }
        
        std::cout << " ✓ Row ranges zapsány (" << row_ranges_.size() << " rows)" << std::endl;
        
        // Zapiš raw data (8B per cell)
        uint64_t cells_written = 0;
        for (const auto& rr : row_ranges_) {
            uint32_t row_id = rr.row_id;
            uint32_t col_count = rr.col_count();
            
            for (uint32_t col = 0; col < col_count; col++) {
                uint16_t h = heights_[row_id][rr.col_start + col];
                float p = pollution_[row_id][rr.col_start + col];
                
                out.write(reinterpret_cast<char*>(&h), sizeof(uint16_t));
                out.write(reinterpret_cast<char*>(&p), sizeof(float));
                cells_written++;
            }
        }
        
        std::cout << " ✓ Data zapsána (" << cells_written << " cells)" << std::endl;
        
        out.close();
        std::cout << " ✓ Soubor uložen: " << output_path << std::endl;
        
        return true;
    }
    
    /**
     * Info o terenu
     */
    void print_info() const {
        std::cout << "\n=== Terrain V5 Info ===" << std::endl;
        std::cout << "Soubor: " << filepath_ << std::endl;
        std::cout << "Rozměry: " << header_.width << "×" << header_.height << std::endl;
        std::cout << "Valid rows: " << header_.num_valid_rows << std::endl;
        std::cout << "Loaded: " << (cache_loaded_ ? "Yes" : "No") << std::endl;
        
        if (!row_ranges_.empty()) {
            uint64_t total_cells = 0;
            for (const auto& rr : row_ranges_) {
                total_cells += rr.col_count();
            }
            std::cout << "Total cells: " << total_cells << std::endl;
        }
        std::cout << "======================\n" << std::endl;
    }
    
    /**
     * Close file
     */
    void close() {
        if (file_.is_open()) {
            file_.close();
        }
    }
    
    /**
     * Destruktor
     */
    ~TerrainLoaderV5() {
        close();
    }
};

#endif // TERRAIN_LOADER_V5_HPP