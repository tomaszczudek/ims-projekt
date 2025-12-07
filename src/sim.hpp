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

    public:
        Simulation(
            std::vector<std::vector<uint16_t>>& heights,
            std::vector<std::vector<float>>& pollution
        ) : heights_vec(heights), pollution_vec(pollution) {}

        void generatePolution(const std::vector<Plant>& plants)
        {
            for (const auto& plant : plants)
            {
                // Konverze: kg/rok → kg/hodinu
                float hourly_emission = plant.emission / CONVERSION_HOUR_KG;
                pollution_vec[plant.row][plant.col] += hourly_emission;
            }
        }

        void distributePolution(uint32_t height, uint32_t width, float wind_direction, float wind_speed)
        {
            /*
            std::cout << "💨 Distribuce znečištění..." << std::endl;
            std::cout << "  Vítr: " << wind_direction * 180.0f / PI << "°, "
                    << wind_speed << " m/s" << std::endl;
            */
            // Vytvoř dočasný grid pro nově distribuované hodnoty
            std::vector<std::vector<float>> distributed(
                height, std::vector<float>(width, 0.0f)
            );
            
            // Iteruj přes každou buňku v pollution gridu
            for (uint32_t r = 0; r < height; r++)
            {
                for (uint32_t c = 0; c < width; c++)
                {
                    // Pokud je znečištění zanedbatelné, přeskočit
                    if (pollution_vec[r][c] < THRESHOLD)
                        continue;
                    
                    float current_pollution = pollution_vec[r][c];
                    uint16_t source_height = heights_vec[r][c];
                    float transfered_amount = 0.0f;
                    
                    // ═══════════════════════════════════════════════════════════
                    // ROZPROSTŘI DO VŠECH 8 OKOLNÍCH BUNĚK
                    // ═══════════════════════════════════════════════════════════
                    
                    for (int dir = 0; dir < 8; dir++)
                    {
                        // Získej sousední buňku
                        NeighborPos neighbor = get_neighbor(r, c, dir, height, width);
                        
                        if (!neighbor.valid)
                            continue;  // Mimo grid
                        
                        int nr = neighbor.new_row;
                        int nc = neighbor.new_col;
                        
                        // ═════════════════════════════════════════════════════
                        // VÝPOČET ÚTLUMU NA ZÁKLADĚ VĚTRU
                        // ═════════════════════════════════════════════════════
                        
                        float decay = compute_decay_factor(wind_direction, dir);
                        
                        // ═════════════════════════════════════════════════════
                        // ZOHLEDNĚNÍ NADMOŘSKÉ VÝŠKY (emise padají dolů)
                        // ═════════════════════════════════════════════════════
                        
                        uint16_t dest_height = heights_vec[nr][nc];
                        
                        // Cílová buňka je VÝŠE → emise padají dolů
                        // Násobíme s penalizačním faktorem
                        if (dest_height > source_height)
                            decay *= GRAVITY_PENALTY;

                        // Pokud dest_height < source_height → normální šíření
                        
                        // ═════════════════════════════════════════════════════
                        // VÝPOČET DISTRIBUOVANÉ HODNOTY
                        // ═════════════════════════════════════════════════════
                        
                        float distributed_amount = current_pollution * decay;
                        
                        // ═════════════════════════════════════════════════════
                        // KONTROLA PRAHU ZANEDBATELNOSTI
                        // ═════════════════════════════════════════════════════
                        
                        if (distributed_amount < THRESHOLD)
                            continue;  // Příliš malé → ignoruj
                        
                        // ═════════════════════════════════════════════════════
                        // PŘIDEJ DO SOUSEDNÍ BUŇKY
                        // ═════════════════════════════════════════════════════
                        
                        distributed[nr][nc] += distributed_amount;
                        transfered_amount += distributed_amount;
                    }
                    
                    // ═══════════════════════════════════════════════════════════
                    // PŮVODNÍ BUŇKA ZŮSTANE (nebo se rozpustí)
                    // ═══════════════════════════════════════════════════════════
                    
                    // Možnost 1: Ponech původní hodnotu (akumulace)
                    distributed[r][c] = current_pollution - transfered_amount;
                    
                    // Možnost 2: Rozpusť (zbude 50%)
                    // distributed[r][c] += current_pollution * 0.5f;
                }
            }
            
            // ════════════════════════════════════════════════════════════════
            // PŘESUŇ DISTRIBUOVANÉ HODNOTY ZPĚT DO POLLUTION VEKTORU
            // ════════════════════════════════════════════════════════════════
            
            pollution_vec = distributed;
            
            // Statistika
            /*
            float max_conc = 0.0f;
            float total_conc = 0.0f;
            uint32_t cells_with_pollution = 0;
            
            for (uint32_t r = 0; r < height; r++)
            {
                for (uint32_t c = 0; c < width; c++)
                {
                    if (pollution_vec[r][c] > THRESHOLD)
                    {
                        max_conc = std::max(max_conc, pollution_vec[r][c]);
                        total_conc += pollution_vec[r][c];
                        cells_with_pollution++;
                    }
                }
            }
            
            
            std::cout << "  ✓ Distribuováno do " << cells_with_pollution 
                    << " buněk" << std::endl;
            std::cout << "  ✓ Max koncentrace: " << max_conc << " kg/m³" << std::endl;
            std::cout << "  ✓ Průměrná koncentrace: " 
                    << (cells_with_pollution > 0 ? total_conc / cells_with_pollution : 0)
                    << " kg/m³\n" << std::endl;
            */
        }

        void run_simulation(const std::vector<Plant>& plants, uint32_t iterations, uint32_t height, uint32_t width)
        {
            generatePolution(plants);
            
            for (uint32_t iter = 0; iter < iterations; iter++)
            {
                float wind_dir = generateWindDirection();
                float wind_spd = generateWindSpeed();
                
                distributePolution(height, width, wind_dir, wind_spd);
                
                std::cout << "  [" << (iter + 1) << "/" << iterations << "] iterací\n" 
                        << std::endl;
            }
        }

        std::vector<std::vector<float>>& get_pollution() { return pollution_vec; }
        const std::vector<std::vector<uint16_t>>& get_heights() const { return heights_vec; }
};

#endif  // sim_hpp