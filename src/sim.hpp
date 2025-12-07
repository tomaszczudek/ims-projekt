
/**
 * sim.hpp
 * 
 * Třída realizující běh simulace.
 */

#ifndef sim_hpp
#define sim_hpp

#pragma once

#include <iostream>
#include <vector>
#include <random>
#include <cmath>
#include <ctime>

struct Plant;

#define CONVERSION_SEC   (365.25f * 24.0f * 3600.0f)
#define CONVERSION_HOUR  (365.25f * 24.0f)
#define CONVERSION_DAY   (365.25f)

#define THRESHOLD        0.00001f      

static std::mt19937 rng(std::random_device{}());

float generateWindDirection()
{
    std::uniform_int_distribution<> dist(0, 23);
    return (dist(rng) * 15.0f);  // degrees
}

float compute_decay_factor(float wind_direction, int direction)
{
    int wind_sector = (int)((wind_direction + 22.5f) / 45.0f) % 8;
    
    int diff = (direction - wind_sector + 8) % 8;

    switch (diff)
    {
        case 0: return 0.7f;   // E
        case 1: return 0.5f;   // NE
        case 2: return 0.3f;   // N
        case 3: return 0.2f;   // NW
        case 4: return 0.1f;   // W
        case 5: return 0.2f;   // SW
        case 6: return 0.3f;   // S
        case 7: return 0.5f;   // SE
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
        case 0: dr =  0; dc =  1; break;  // E
        case 1: dr = -1; dc =  1; break;  // NE
        case 2: dr = -1; dc =  0; break;  // N
        case 3: dr = -1; dc = -1; break;  // NW
        case 4: dr =  0; dc = -1; break;  // W
        case 5: dr =  1; dc = -1; break;  // SW
        case 6: dr =  1; dc =  0; break;  // S
        case 7: dr =  1; dc =  1; break;  // SE
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

        float wind_direction;
        
        uint32_t height;
        uint32_t width;
    public:
        Simulation(
            std::vector<std::vector<uint16_t>>& heights,
            std::vector<std::vector<float>>& pollution,
            uint32_t height,
            uint32_t width
        ) : heights_vec(heights), pollution_vec(pollution), height(height), width(width) {}

        // Generate pollution from plants
        void generatePolution(const std::vector<Plant>& plants)
        {
            for (const auto& plant : plants)
                pollution_vec[plant.row][plant.col] += (plant.emission / CONVERSION_HOUR);
        }

        // Distribute pollution across the grid
        void distributePolution()
        {
            wind_direction = generateWindDirection();
                
            std::vector<std::vector<bool>> visited(
                height, std::vector<bool>(width, false)
            );
            
            for (uint32_t r = 0; r < height; r++)
            {
                for (uint32_t c = 0; c < width; c++)
                {
                    if (pollution_vec[r][c] < THRESHOLD)
                        continue;
                    
                    if (visited[r][c])
                        continue;
                    
                    distribute_recursive(r, c, pollution_vec[r][c], visited);
                }
            }
        }

        // Distribute pollution from cell
        void distribute_recursive(int r, int c, float current_pollution, std::vector<std::vector<bool>>& visited)
        {
            if (current_pollution < THRESHOLD)
                return;
            
            if (visited[r][c])
                return;
            
            visited[r][c] = true;
            
            uint16_t source_height = heights_vec[r][c];
            float transferred = 0.0f;
            
            for (int dir = 0; dir < 8; dir++)
            {
                NeighborPos neighbor = get_neighbor(r, c, dir, height, width);
                
                if (!neighbor.valid)
                    continue;
                
                float decay = compute_decay_factor(wind_direction, dir);
                
                uint16_t dest_height = heights_vec[neighbor.new_row][neighbor.new_col];
                
                if (dest_height <= 0)
                    continue;

                if (dest_height > source_height)
                    decay *= std::exp(-std::pow(dest_height - source_height, 1.2f) / 800.0f);
                
                float distributed_amount = current_pollution * decay;
                
                if (distributed_amount < THRESHOLD)
                    continue;
                
                pollution_vec[neighbor.new_row][neighbor.new_col] += distributed_amount;
                transferred += distributed_amount;
                
                if (distributed_amount >= THRESHOLD && !visited[neighbor.new_row][neighbor.new_col])
                    distribute_recursive(neighbor.new_row, neighbor.new_col, distributed_amount, visited);
            }
            pollution_vec[r][c] -= transferred;
        }

        // Run the simulation for a number of iterations
        void run_simulation(const std::vector<Plant>& plants, uint32_t iterations)
        {
            for (uint32_t iter = 0; iter < iterations; iter++)
            {
                generatePolution(plants);
                distributePolution();
                
                std::cout << "  [" << (iter + 1) << "/" << iterations << "] iterací" << std::endl;
            }
        }
};

#endif  // sim_hpp