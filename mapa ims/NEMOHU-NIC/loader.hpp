/**
 * TerrainLoaderV5 - UNIFIED HEADER
 * ==================================
 * Kombinace:
 *   - TerrainLoaderV5: Čtení/zápis terénů + továren
 *   - PlantLoader: Přístup k továrnám
 * 
 * Jednoduché API pro C++
 */

#ifndef TERRAIN_LOADER_V5_UNIFIED_HPP
#define TERRAIN_LOADER_V5_UNIFIED_HPP

#include <vector>
#include <string>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <cstdio>

// ============= STRUKTURY =============

#pragma pack(push, 1)

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

struct Plant {
    uint32_t row;
    uint32_t col;
    float emission;  // [kg/rok]

    Plant() : row(0), col(0), emission(0.0f) {}
    Plant(uint32_t r, uint32_t c, float e) 
        : row(r), col(c), emission(e) {}
};

#pragma pack(pop)

// ============= TERRAIN LOADER =============

class TerrainLoaderV5 {
private:
    std::string filepath_;
    TerrainHeader header_;
    std::vector<RowRange> row_ranges_;
    std::vector<Plant> plants_;
    std::ifstream file_;

    // 2D arrays
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
        std::cout << "  Width: " << header_.width << std::endl;
        std::cout << "  Height: " << header_.height << std::endl;
        std::cout << "  Valid rows: " << header_.num_valid_rows << std::endl;

        // Čti počet továren (4B)
        uint32_t num_plants = 0;
        file_.read(reinterpret_cast<char*>(&num_plants), sizeof(uint32_t));
        std::cout << "  Plants: " << num_plants << std::endl;

        // Čti data továren (12B per plant)
        plants_.reserve(num_plants);
        for (uint32_t i = 0; i < num_plants; i++) {
            Plant p;
            file_.read(reinterpret_cast<char*>(&p.row), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&p.col), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&p.emission), sizeof(float));
            plants_.push_back(p);
        }

        // Čti row ranges (12B per row)
        row_ranges_.reserve(header_.num_valid_rows);
        for (uint32_t i = 0; i < header_.num_valid_rows; i++) {
            RowRange rr;
            file_.read(reinterpret_cast<char*>(&rr.row_id), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&rr.col_start), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&rr.col_end), sizeof(uint32_t));
            row_ranges_.push_back(rr);
        }

        std::cout << "  ✓ Row ranges: " << row_ranges_.size() << std::endl;
        std::cout << "  ✓ Továren: " << plants_.size() << std::endl;

        return true;
    }

    /**
     * Načti všechna data
     */
    bool load_all_data() {
        if (row_ranges_.empty()) {
            std::cerr << "✗ Nejdřív zavolej load_header()!" << std::endl;
            return false;
        }

        heights_.resize(header_.height);
        pollution_.resize(header_.height);
        for (uint32_t row = 0; row < header_.height; row++) {
            heights_[row].resize(header_.width, 0);
            pollution_[row].resize(header_.width, 0.0f);
        }

        std::cout << " 📊 Čtení dat..." << std::endl;
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

    // ========== GETTERY ==========

    uint16_t get_height(uint32_t row, uint32_t col) const {
        if (!cache_loaded_ || row >= header_.height || col >= header_.width) {
            return 0;
        }
        return heights_[row][col];
    }

    float get_pollution(uint32_t row, uint32_t col) const {
        if (!cache_loaded_ || row >= header_.height || col >= header_.width) {
            return 0.0f;
        }
        return pollution_[row][col];
    }

    std::vector<std::vector<uint16_t>>& get_heights_mut() {
        return heights_;
    }

    std::vector<std::vector<float>>& get_pollution_mut() {
        return pollution_;
    }

    const std::vector<Plant>& get_plants() const {
        return plants_;
    }

    uint32_t get_width() const { return header_.width; }
    uint32_t get_height() const { return header_.height; }

    bool is_loaded() const { return cache_loaded_; }

    // ========== TISKOVÁ FUNKCE ==========

    void print_info() const {
        std::cout << "\n=== Terrain V5 Info ===" << std::endl;
        std::cout << "Soubor: " << filepath_ << std::endl;
        std::cout << "Rozměry: " << header_.width << "×" << header_.height << std::endl;
        std::cout << "Valid rows: " << header_.num_valid_rows << std::endl;
        std::cout << "Továrny: " << plants_.size() << std::endl;
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

    void print_plants() const {
        if (plants_.empty()) {
            std::cout << "\n 🏭 Žádné továrny!\n" << std::endl;
            return;
        }

        std::cout << "\n 🏭 TOVÁRNY V GRIDU:" << std::endl;
        std::cout << " " << std::string(60, '-') << std::endl;
        std::cout << " ID | Row | Col | Emission [kg/rok]" << std::endl;
        std::cout << " " << std::string(60, '-') << std::endl;

        for (size_t i = 0; i < plants_.size(); i++) {
            const auto& p = plants_[i];
            printf(" %3lu | %6u | %6u | %.2e\n",
                   i, p.row, p.col, p.emission);
        }

        std::cout << " " << std::string(60, '-') << std::endl;

        // Statistika
        double total_emission = 0;
        double max_emission = 0;
        for (const auto& p : plants_) {
            total_emission += p.emission;
            if (p.emission > max_emission) max_emission = p.emission;
        }

        printf(" Celkem: %.2e kg/rok (max: %.2e)\n", total_emission, max_emission);
        std::cout << std::endl;
    }

    // ========== ZÁPIS ==========

    bool save_to_binary(const std::string& output_path) {
        if (!cache_loaded_) {
            std::cerr << "✗ Nejdřív zavolej load_all_data()!" << std::endl;
            return false;
        }

        std::cout << " 💾 Zápis do " << output_path << "..." << std::endl;
        std::ofstream out(output_path, std::ios::binary);
        if (!out) {
            std::cerr << "✗ Chyba: Nelze otevřít " << output_path << " pro zápis" << std::endl;
            return false;
        }

        // Header
        out.write(reinterpret_cast<char*>(&header_.width), sizeof(uint32_t));
        out.write(reinterpret_cast<char*>(&header_.height), sizeof(uint32_t));
        out.write(reinterpret_cast<char*>(&header_.num_valid_rows), sizeof(uint32_t));
        for (int i = 0; i < 6; i++) {
            out.write(reinterpret_cast<char*>(&header_.transform[i]), sizeof(double));
        }

        // Počet továren
        uint32_t num_plants = plants_.size();
        out.write(reinterpret_cast<char*>(&num_plants), sizeof(uint32_t));

        // Data továren
        for (const auto& p : plants_) {
            out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&p.row)), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&p.col)), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(const_cast<float*>(&p.emission)), sizeof(float));
        }

        // Row ranges
        for (const auto& rr : row_ranges_) {
            out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&rr.row_id)), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&rr.col_start)), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&rr.col_end)), sizeof(uint32_t));
        }

        // Raw data
        for (const auto& rr : row_ranges_) {
            uint32_t row_id = rr.row_id;
            uint32_t col_start = rr.col_start;
            uint32_t col_end = rr.col_end;
            for (uint32_t col = col_start; col < col_end; col++) {
                uint16_t h = heights_[row_id][col];
                float p = pollution_[row_id][col];
                out.write(reinterpret_cast<char*>(&h), sizeof(uint16_t));
                out.write(reinterpret_cast<char*>(&p), sizeof(float));
            }
        }

        out.close();
        std::cout << " ✓ Soubor uložen!" << std::endl;
        return true;
    }

    void close() {
        if (file_.is_open()) {
            file_.close();
        }
    }

    ~TerrainLoaderV5() {
        close();
    }
};

#endif // TERRAIN_LOADER_V5_UNIFIED_HPP