#ifndef loader_hpp
#define loader_hpp

#pragma once

#include <vector>
#include <string>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <cstdio>
#include <cmath>

#pragma pack(push, 1)

struct RowRange
{
    uint32_t row_id;
    uint32_t col_start;
    uint32_t col_end;

    uint32_t col_count() const
    {
        return col_end - col_start;
    }
};

struct TerrainHeader
{
    uint32_t width;
    uint32_t height;
    uint32_t num_valid_rows;
    double transform[6];
};

struct Plant
{
    uint32_t row;
    uint32_t col;
    float emission; // [t/rok]

    Plant() : row(0), col(0), emission(0.0f) {}
    Plant(uint32_t r, uint32_t c, float e) 
        : row(r), col(c), emission(e) {}
};

#pragma pack(pop)

class Loader
{
    private:
        std::string filepath_;
        TerrainHeader header_;
        std::vector<RowRange> row_ranges_;
        std::vector<Plant> plants_;
        std::ifstream file_;

        std::vector<std::vector<uint16_t>> heights_;
        std::vector<std::vector<float>> pollution_;

        bool loaded = false;

    public:
        Loader(const std::string& path) : filepath_(path) {}

        bool load_header()
        {
            file_.open(filepath_, std::ios::binary);
            if (!file_)
                return false;

            // File header
            file_.read(reinterpret_cast<char*>(&header_.width), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&header_.height), sizeof(uint32_t));
            file_.read(reinterpret_cast<char*>(&header_.num_valid_rows), sizeof(uint32_t));
            for (int i = 0; i < 6; i++)
                file_.read(reinterpret_cast<char*>(&header_.transform[i]), sizeof(double));

            // Plant count
            uint32_t num_plants = 0;
            file_.read(reinterpret_cast<char*>(&num_plants), sizeof(uint32_t));

            // Read plant data
            plants_.reserve(num_plants);
            for (uint32_t i = 0; i < num_plants; i++)
            {
                Plant p;
                file_.read(reinterpret_cast<char*>(&p.row), sizeof(uint32_t));
                file_.read(reinterpret_cast<char*>(&p.col), sizeof(uint32_t));
                file_.read(reinterpret_cast<char*>(&p.emission), sizeof(float));
                plants_.push_back(p);
            }

            // Read row ranges
            row_ranges_.reserve(header_.num_valid_rows);
            for (uint32_t i = 0; i < header_.num_valid_rows; i++)
            {
                RowRange rr;
                file_.read(reinterpret_cast<char*>(&rr.row_id), sizeof(uint32_t));
                file_.read(reinterpret_cast<char*>(&rr.col_start), sizeof(uint32_t));
                file_.read(reinterpret_cast<char*>(&rr.col_end), sizeof(uint32_t));
                row_ranges_.push_back(rr);
            }

            return true;
        }
        
        bool load_all_data()
        {
            if (row_ranges_.empty())
                return false;

            heights_.resize(header_.height);
            pollution_.resize(header_.height);
            for (uint32_t row = 0; row < header_.height; row++)
            {
                heights_[row].resize(header_.width, 0);
                pollution_[row].resize(header_.width, 0.0f);
            }

            for (const auto& rr : row_ranges_)
            {
                uint32_t row_id = rr.row_id;
                uint32_t col_count = rr.col_count();

                for (uint32_t col = 0; col < col_count; col++)
                {
                    uint16_t h;
                    float p;
                    file_.read(reinterpret_cast<char*>(&h), sizeof(uint16_t));
                    file_.read(reinterpret_cast<char*>(&p), sizeof(float));
                    heights_[row_id][rr.col_start + col] = h;
                    pollution_[row_id][rr.col_start + col] = p;
                }
            }

            loaded = true;
            return true;
        }

        std::vector<std::vector<uint16_t>>& get_heights() {return heights_;}
        std::vector<std::vector<float>>& get_pollution() {return pollution_;}
        const std::vector<Plant>& get_plants() const {return plants_;}
        uint32_t get_width() const { return header_.width; }
        uint32_t get_height() const { return header_.height; }
        bool is_loaded() const { return loaded; }

        bool save_to_binary(const std::string& output_path)
        {
            if (!loaded)
                return false;

            std::ofstream out(output_path, std::ios::binary);
            if (!out)
                return false;

            // Header
            out.write(reinterpret_cast<char*>(&header_.width), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(&header_.height), sizeof(uint32_t));
            out.write(reinterpret_cast<char*>(&header_.num_valid_rows), sizeof(uint32_t));
            for (int i = 0; i < 6; i++)
                out.write(reinterpret_cast<char*>(&header_.transform[i]), sizeof(double));

            // Number of plants
            uint32_t num_plants = plants_.size();
            out.write(reinterpret_cast<char*>(&num_plants), sizeof(uint32_t));

            // Plant data
            for (const auto& p : plants_)
            {
                out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&p.row)), sizeof(uint32_t));
                out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&p.col)), sizeof(uint32_t));
                out.write(reinterpret_cast<char*>(const_cast<float*>(&p.emission)), sizeof(float));
            }

            // Row ranges
            for (const auto& rr : row_ranges_)
            {
                out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&rr.row_id)), sizeof(uint32_t));
                out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&rr.col_start)), sizeof(uint32_t));
                out.write(reinterpret_cast<char*>(const_cast<uint32_t*>(&rr.col_end)), sizeof(uint32_t));
            }

            // Raw data
            for (const auto& rr : row_ranges_)
            {
                uint32_t row_id = rr.row_id;
                uint32_t col_start = rr.col_start;
                uint32_t col_end = rr.col_end;
                for (uint32_t col = col_start; col < col_end; col++)
                {
                    uint16_t h = heights_[row_id][col];
                    float p = pollution_[row_id][col];
                    out.write(reinterpret_cast<char*>(&h), sizeof(uint16_t));
                    out.write(reinterpret_cast<char*>(&p), sizeof(float));
                }
            }

            out.close();
            return true;
        }

        void close() 
        {
            if (file_.is_open())
                file_.close();
        }

        ~Loader()
        {
            close();
        }
};


#endif // loader_hpp
