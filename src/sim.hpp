#ifndef sim_hpp
#define sim_hpp

#pragma once

#include <iostream>
#include <vector>
#include <random>
#include <cmath>
#include <ctime>

struct Plant;

#define CONVERSION_SEC_KG   (365.25f * 24.0f * 3600.0f)
#define CONVERSION_HOUR_KG  (365.25f * 24.0f)
#define CONVERSION_DAY_KG   (365.25f)

#define AREA_OF_CELL32   (132 * 192)
#define AREA_OF_CELL16   (66 * 96)

#define THRESHOLD        0.00001f      
#define GRAVITY_PENALTY  0.5f          

constexpr float PI = 3.14159265359f;

static std::mt19937 rng(std::random_device{}());

float generateWindDirection()
{
    std::uniform_int_distribution<> dist(0, 23);
    return (dist(rng) * 15.0f) * (PI / 180.0f);  // 0-360° v radiánech
}

float generateWindSpeed()
{
    std::uniform_real_distribution<> dist(1.0f, 10.0f);
    return dist(rng);  // m/s
}

float compute_decay_factor(float wind_direction, int direction)
{
    float wind_deg = wind_direction * 180.0f / PI;
    int wind_sector = (int)((wind_deg + 22.5f) / 45.0f) % 8;
    
    int diff = (direction - wind_sector + 8) % 8;

    switch (diff)
    {
        case 0: return 0.7f;   // Přímý vítr
        case 1: return 0.5f;   // Diagonálně s větrem
        case 2: return 0.3f;   // Kolmo na vítr
        case 3: return 0.2f;   // Částečně proti větru
        case 4: return 0.1f;   // Proti větru (nejslabší)
        case 5: return 0.2f;   // Částečně proti větru
        case 6: return 0.3f;   // Kolmo na vítr
        case 7: return 0.5f;   // Diagonálně s větrem
        default: return 0.1f;
    }
}

struct NeighborPos
{
    int new_row;
    int new_col;
    bool valid;
};

NeighborPos get_neighbor(int row, int col, int direction, uint32_t height, uint32_t width)
{
    int dr = 0, dc = 0;
    
    switch (direction)
    {
        case 0: dr =  0; dc =  1; break;  // E (Východ)
        case 1: dr = -1; dc =  1; break;  // NE (Severovýchod)
        case 2: dr = -1; dc =  0; break;  // N (Sever)
        case 3: dr = -1; dc = -1; break;  // NW (Severozápad)
        case 4: dr =  0; dc = -1; break;  // W (Západ)
        case 5: dr =  1; dc = -1; break;  // SW (Jihozápad)
        case 6: dr =  1; dc =  0; break;  // S (Jih)
        case 7: dr =  1; dc =  1; break;  // SE (Jihovýchod)
    }
    
    int new_row = row + dr;
    int new_col = col + dc;
    
    bool valid = (new_row >= 0 && new_row < (int)height &&new_col >= 0 && new_col < (int)width);
    
    return {new_row, new_col, valid};
}


class Simulation
{
    private:
        std::vector<std::vector<uint16_t>>& heights_vec;
        std::vector<std::vector<float>>& pollution_vec;

        uint32_t height;
        uint32_t width;
    public:
        Simulation(
            std::vector<std::vector<uint16_t>>& heights,
            std::vector<std::vector<float>>& pollution,
            uint32_t height,
            uint32_t width
        ) : heights_vec(heights), pollution_vec(pollution), height(height), width(width) {}

        void generatePolution(const std::vector<Plant>& plants)
        {
            for (const auto& plant : plants)
                pollution_vec[plant.row][plant.col] += (plant.emission / CONVERSION_HOUR_KG);
        }

        void distributePolution(float wind_direction, float wind_speed)
        {
            std::vector<std::vector<bool>> visited(
                height, std::vector<bool>(width, false)
            );
            
            // Projdi všechny buňky (bez tohoto bychom nezačali shora)
            for (uint32_t r = 0; r < height; r++)
            {
                for (uint32_t c = 0; c < width; c++)
                {
                    // Pokud je znečištění pod prahem, skip
                    if (pollution_vec[r][c] < THRESHOLD)
                        continue;
                    
                    if (visited[r][c])
                        continue;
                    
                    // SPUSŤ REKURZIVNÍ FLOOD-FILL!
                    distribute_recursive(r, c, pollution_vec[r][c],
                                        wind_direction, visited);
                }
            }
        }

        void distribute_recursive(int r, int c, float current_pollution, float wind_direction, std::vector<std::vector<bool>>& visited)
        {
            if (current_pollution < THRESHOLD) return;
            if (visited[r][c]) return;
            
            visited[r][c] = true;
            
            uint16_t source_height = heights_vec[r][c];
            float transferred = 0.0f;  // ← SLEDUJ KOLIK SE ODEŠLE
            
            for (int dir = 0; dir < 8; dir++) {
                NeighborPos neighbor = get_neighbor(r, c, dir, height, width);
                
                if (!neighbor.valid)
                    continue;
                
                float decay = compute_decay_factor(wind_direction, dir);
                
                uint16_t dest_height = heights_vec[neighbor.new_row][neighbor.new_col];
                
                if (dest_height > source_height)
                    decay *= GRAVITY_PENALTY;
                
                float distributed_amount = current_pollution * decay;
                
                if (distributed_amount < THRESHOLD)
                    continue;
                
                // PŘIDEJ do souseda
                pollution_vec[neighbor.new_row][neighbor.new_col] += distributed_amount;
                transferred += distributed_amount;
                
                // REKURZE
                if (distributed_amount >= THRESHOLD && !visited[neighbor.new_row][neighbor.new_col])
                    distribute_recursive(neighbor.new_row, neighbor.new_col, distributed_amount, wind_direction, visited);
            }
            
            pollution_vec[r][c] -= transferred;
        }


        void run_simulation(const std::vector<Plant>& plants, uint32_t iterations)
        {
            for (uint32_t iter = 0; iter < iterations; iter++)
            {
                generatePolution(plants);
                distributePolution(generateWindDirection(), generateWindSpeed());
                
                std::cout << "  [" << (iter + 1) << "/" << iterations << "] iterací\n" 
                        << std::endl;
            }
        }

        std::vector<std::vector<float>>& get_pollution() { return pollution_vec; }
        const std::vector<std::vector<uint16_t>>& get_heights() const { return heights_vec; }
};

#endif  // sim_hpp