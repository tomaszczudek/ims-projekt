#ifndef model_hpp
#define model_hpp

#pragma once

#include <vector>
#include <cstdint>
#include <cmath>
#include <iostream>
#include <random>

#define EMISSION_CONVERSION_FACTOR_SEC (365.25f * 24.0f * 3600.0f)
#define EMISSION_CONVERSION_FACTOR_HOUR (365.25f * 24.0f)
#define EMISSION_CONVERSION_FACTOR_DAY (365.25f)

#define WIDTH_KM 105.0f
#define HEIGHT_KM 127.0f

static std::mt19937 rng(std::random_device{}());
struct Plant;

enum class StabilityClass
{
    A = 0, B = 1, C = 2, D = 3, E = 4, F = 5
};

constexpr float PI = 3.14159265359f;

struct CoeffParam
{
    float a;
    float b;
};

struct MeteoData
{
    float wind_speed;
    float wind_direction;
    StabilityClass stability;
    float effective_height;
};

class PasquillGifford
{
    public:
        static CoeffParam get_sigma_y_params(StabilityClass stability)
        {
            switch (stability)
            {
                case StabilityClass::A: return {0.22f, 0.894f};
                case StabilityClass::B: return {0.16f, 0.894f};
                case StabilityClass::C: return {0.11f, 0.894f};
                case StabilityClass::D: return {0.08f, 0.894f};
                case StabilityClass::E: return {0.06f, 0.894f};
                case StabilityClass::F: return {0.03f, 0.894f};
                default: return {0.11f, 0.894f};
            }
        }

        static CoeffParam get_sigma_z_params(StabilityClass stability)
        {
            switch (stability)
            {
                case StabilityClass::A: return {0.20f, 0.894f};
                case StabilityClass::B: return {0.12f, 0.894f};
                case StabilityClass::C: return {0.08f, 0.894f};
                case StabilityClass::D: return {0.06f, 0.894f};
                case StabilityClass::E: return {0.03f, 0.894f};
                case StabilityClass::F: return {0.016f, 0.894f};
                default: return {0.08f, 0.894f};
            }
        }
};

class GaussianPlumeModel
{
    private:
        uint32_t grid_width_;
        uint32_t grid_height_;
        float grid_resolution_;
        float wind_speed_;
        StabilityClass stability_;
        float effective_height_;

        std::vector<std::vector<float>>& pollution_ref_;
        const std::vector<std::vector<uint16_t>>& heights_ref_;

        // Metadata o terénu
        uint16_t min_elevation_;
        uint16_t max_elevation_;
        float avg_elevation_;

    public:
        /**
         * 
         * @param width - Šířka gridu
         * @param height - Výška gridu
         * @param pollution_ref - Reference na pole znečištění
         * @param heights_ref - Reference na pole nadmořských výšek ← NOVÉ!
         * @param resolution - Rozlišení gridu (m/pixel)
         * @param wind_speed - Větrná rychlost (m/s)
         * @param stability - Třída stability
         * @param effective_height - Efektivní výška emise (m)
         */
        GaussianPlumeModel(
            uint32_t width,
            uint32_t height,
            std::vector<std::vector<float>>& pollution_ref,
            const std::vector<std::vector<uint16_t>>& heights_ref,
            float wind_speed = 3.0f,
            StabilityClass stability = StabilityClass::C,
            float effective_height = 50.0f
        )
            : grid_width_(width),
            grid_height_(height),
            wind_speed_(wind_speed),
            stability_(stability),
            effective_height_(effective_height),
            pollution_ref_(pollution_ref),
            heights_ref_(heights_ref)  // ← NOVÉ!
        {
            grid_resolution_ = ((WIDTH_KM * 1000.0f) / width + 
                       (HEIGHT_KM * 1000.0f) / height) / 2.0f;

            // Vypočítej statistiku terénu
            compute_elevation_stats();

            std::cout << "\n✓ GaussianPlumeModel V3 inicializován (SE ELEVACÍ):" << std::endl;
            std::cout << "  Grid: " << grid_width_ << "×" << grid_height_ << std::endl;
            std::cout << "  Resolution: " << grid_resolution_ << " m/px" << std::endl;
            std::cout << "  Elevace - Min: " << min_elevation_ << " m, Max: " 
                    << max_elevation_ << " m, Avg: " << avg_elevation_ << " m" << std::endl;
        }

        /**
         * Vypočítej statistiku terénu
         */
        void compute_elevation_stats()
        {
            min_elevation_ = 65535;
            max_elevation_ = 0;
            uint64_t sum = 0;
            uint32_t count = 0;

            for (uint32_t row = 0; row < grid_height_; row++)
            {
                for (uint32_t col = 0; col < grid_width_; col++)
                {
                    uint16_t elev = heights_ref_[row][col];
                    min_elevation_ = std::min(min_elevation_, elev);
                    max_elevation_ = std::max(max_elevation_, elev);
                    sum += elev;
                    count++;
                }
            }

            avg_elevation_ = (count > 0) ? (float)sum / count : 0.0f;
        }

        /**
         * Přidej příspěvek jedné továrny - SE ZOHLEDNĚNÍM NADMOŘSKÉ VÝŠKY
         */
        void add_plume_from_source(uint32_t source_row, uint32_t source_col, float emission_kg_rok, float wind_direction_deg = 0.0f)
        {
            // Konverze: kg/rok → kg/s
            float emision_plume = emission_kg_rok / (1);

            // Větrný úhel
            float wind_rad = wind_direction_deg * PI / 180.0f;

            // Parametry rozptylu
            auto sigma_y_params = PasquillGifford::get_sigma_y_params(stability_);
            auto sigma_z_params = PasquillGifford::get_sigma_z_params(stability_);

            // Nadmořská výška zdroje
            float source_elevation = (float)heights_ref_[source_row][source_col];
            float source_height_abs = source_elevation + effective_height_;  // Absolutní výška

            // Iteruj přes všechny body v gridu
            for (uint32_t row = 0; row < grid_height_; row++)
            {
                for (uint32_t col = 0; col < grid_width_; col++)
                {
                    if (heights_ref_[row][col] == 0) 
                        continue; 

                    // Fyzické souřadnice (m)
                    float x_m = (float)col * grid_resolution_;
                    float y_m = (float)row * grid_resolution_;
                    float source_x_m = (float)source_col * grid_resolution_;
                    float source_y_m = (float)source_row * grid_resolution_;

                    // Vzdálenost od zdroje
                    float dx = x_m - source_x_m;
                    float dy = y_m - source_y_m;

                    // Rotace o úhel větru
                    float downwind = dx * std::cos(wind_rad) + dy * std::sin(wind_rad);
                    float crosswind = -dx * std::sin(wind_rad) + dy * std::cos(wind_rad);

                    // Filtruj
                    if (downwind < 10.0f) continue;
                    if (downwind > 50000.0f) continue;

                    // Vypočítej rozptylové parametry
                    float sigma_y = sigma_y_params.a * std::pow(downwind, sigma_y_params.b);
                    float sigma_z = sigma_z_params.a * std::pow(downwind, sigma_z_params.b);

                    sigma_y = std::max(sigma_y, 10.0f);
                    sigma_z = std::max(sigma_z, 5.0f);

                    // ========== NOVÉ: ZOHLEDNĚNÍ NADMOŘSKÉ VÝŠKY ==========

                    // Nadmořská výška příjemce
                    float receiver_elevation = (float)heights_ref_[row][col];

                    // Efektivní výška emise (z = absolutní výška zdroje - elev. příjemce)
                    // Tedy: jak vysoko je zdroj NAD terén u příjemce
                    float H = source_height_abs - receiver_elevation;

                    // Pokud je příjemce výš než zdroj, emise se nepočítá (fyzika)
                    if (H < 0.0f) continue;

                    // Minimální výška nad terénem (aby model dával smysl)
                    H = std::max(H, 5.0f);  // Alespoň 5 m nad terénem

                    // =====================================================

                    // Gaussova rovnice (se zohledněním nadmořské výšky)
                    float gauss_y = std::exp(-0.5f * (crosswind / sigma_y) * (crosswind / sigma_y));
                    float gauss_z = std::exp(-0.5f * ((0.0f - H) / sigma_z) * ((0.0f - H) / sigma_z))
                                + std::exp(-0.5f * ((0.0f + H) / sigma_z) * ((0.0f + H) / sigma_z));

                    // Výpočet koncentrace
                    float denom = 2.0f * PI * wind_speed_ * sigma_y * sigma_z;
                    if (denom > 0.0001f)
                    {
                        float conc = (emision_plume / denom) * gauss_y * gauss_z;
                        pollution_ref_[row][col] += conc;
                    }
                }
            }
        }

        /**
         * Vypočítej rozptyl od VŠECH továren (SE ELEVACÍ)
         */
        void calculate_dispersion_all_plants(const std::vector<Plant>& plants, float wind_direction_deg = 45.0f)
        {
            std::cout << "\n📍 Výpočet rozptylu Gaussovým modelem V3 (s elevací)..." << std::endl;
            std::cout << "  Vítr: " << wind_speed_ << " m/s, směr " << wind_direction_deg << "°" << std::endl;
            std::cout << "  Stabilita: " << (int)stability_ << std::endl;
            std::cout << "  Počet zdrojů: " << plants.size() << std::endl;
            std::cout << "  ⚠️  Zohledňuji nadmořskou výšku!" << std::endl;

            for (size_t i = 0; i < plants.size(); i++)
            {
                const auto& plant = plants[i];
                if (plant.emission > 0.0001f)
                {
                    add_plume_from_source(
                        plant.row,
                        plant.col,
                        plant.emission,
                        wind_direction_deg
                    );
                }

                if (i % 100 == 0)
                {
                    std::cout << "  ✓ Zpracováno " << i << "/" << plants.size() 
                            << " zdrojů" << std::endl;
                }
            }

            std::cout << "  ✓ Rozptyl vypočítán (s zohledněním terénu)" << std::endl;
        }

        // ========== GETTERY ==========

        std::vector<std::vector<float>>& get_pollution_ref() {return pollution_ref_;}

        uint16_t get_min_elevation() const { return min_elevation_; }
        uint16_t get_max_elevation() const { return max_elevation_; }
        float get_avg_elevation() const { return avg_elevation_; }

        void set_wind_speed(float speed) { wind_speed_ = speed; }
        void set_stability(StabilityClass stability) { stability_ = stability; }
        void set_effective_height(float height) { effective_height_ = height; }

        void print_stats() const
        {
            std::cout << "\n=== Gaussian Plume Model V3 (s elevací) ===" << std::endl;
            std::cout << "Grid: " << grid_width_ << "×" << grid_height_ << std::endl;
            std::cout << "Resolution: " << grid_resolution_ << " m/px" << std::endl;
            std::cout << "Wind speed: " << wind_speed_ << " m/s" << std::endl;
            std::cout << "Effective height: " << effective_height_ << " m" << std::endl;
            std::cout << "Stability class: " << (int)stability_ << std::endl;

            std::cout << "\nTerrén:" << std::endl;
            std::cout << "  Min elevace: " << min_elevation_ << " m" << std::endl;
            std::cout << "  Max elevace: " << max_elevation_ << " m" << std::endl;
            std::cout << "  Avg elevace: " << avg_elevation_ << " m" << std::endl;
            std::cout << "  Rozpětí: " << (max_elevation_ - min_elevation_) << " m" << std::endl;

            // Statistika koncentrací
            float total_conc = 0.0f;
            float max_conc = 0.0f;
            uint32_t nonzero_cells = 0;

            for (uint32_t row = 0; row < grid_height_; row++) {
                for (uint32_t col = 0; col < grid_width_; col++) {
                    if (pollution_ref_[row][col] > 0.0001f)
                    {
                        total_conc += pollution_ref_[row][col];
                        max_conc = std::max(max_conc, pollution_ref_[row][col]);
                        nonzero_cells++;
                    }
                }
            }

            std::cout << "\nZnečištění:" << std::endl;
            std::cout << "Nonzero cells: " << nonzero_cells << std::endl;
            std::cout << "Max concentration: " << max_conc << " kg/m³" << std::endl;
            std::cout << "Avg concentration: " << (total_conc / std::max(1u, nonzero_cells)) 
                    << " kg/m³" << std::endl;
            std::cout << "===========================================\n" << std::endl;
        }
};


class MeteoScenarios
{
    public:
        static std::vector<MeteoData> get_winter_scenarios()
        {
            return
            {
                {2.0f, 45.0f, StabilityClass::F, 30.0f},
                {1.5f, 90.0f, StabilityClass::F, 25.0f},
                {3.0f, 135.0f, StabilityClass::E, 35.0f},
                {4.5f, 180.0f, StabilityClass::D, 45.0f},
                {2.5f, 225.0f, StabilityClass::F, 30.0f},
                {1.0f, 270.0f, StabilityClass::F, 20.0f},
                {3.5f, 315.0f, StabilityClass::E, 40.0f},
                {2.0f, 0.0f, StabilityClass::F, 30.0f},
                {4.0f, 45.0f, StabilityClass::D, 50.0f},
                {3.0f, 90.0f, StabilityClass::E, 35.0f},
                {1.0f, 45.0f, StabilityClass::F, 25.0f},
                {1.5f, 90.0f, StabilityClass::F, 30.0f},
                {2.5f, 135.0f, StabilityClass::E, 35.0f},
                {3.5f, 180.0f, StabilityClass::D, 45.0f},
                {2.0f, 225.0f, StabilityClass::F, 30.0f},
                {0.8f, 270.0f, StabilityClass::F, 20.0f},
                {4.0f, 315.0f, StabilityClass::E, 40.0f},
                {1.3f, 0.0f, StabilityClass::F, 28.0f},
                {2.2f, 45.0f, StabilityClass::F, 32.0f},
                {3.0f, 90.0f, StabilityClass::D, 42.0f}
            };
        }

        static std::vector<MeteoData> get_spring_autumn_scenarios()
        {
            return
            {
                {3.5f, 45.0f, StabilityClass::C, 50.0f},
                {4.0f, 90.0f, StabilityClass::C, 55.0f},
                {3.0f, 135.0f, StabilityClass::D, 40.0f},
                {5.0f, 180.0f, StabilityClass::C, 60.0f},
                {4.5f, 225.0f, StabilityClass::C, 55.0f},
                {3.5f, 270.0f, StabilityClass::D, 45.0f},
                {4.0f, 315.0f, StabilityClass::C, 50.0f},
                {3.5f, 0.0f, StabilityClass::C, 50.0f},
                {2.5f, 45.0f, StabilityClass::D, 35.0f},
                {3.0f, 180.0f, StabilityClass::D, 40.0f},
                {3.5f, 45.0f, StabilityClass::C, 50.0f},
                {4.0f, 90.0f, StabilityClass::C, 55.0f},
                {2.8f, 135.0f, StabilityClass::D, 45.0f},
                {5.5f, 180.0f, StabilityClass::C, 60.0f},
                {3.0f, 225.0f, StabilityClass::D, 48.0f},
                {2.5f, 270.0f, StabilityClass::D, 42.0f},
                {4.5f, 315.0f, StabilityClass::D, 52.0f},
                {3.2f, 0.0f, StabilityClass::C, 48.0f},
                {3.8f, 45.0f, StabilityClass::C, 50.0f},
                {4.2f, 90.0f, StabilityClass::B, 58.0f}
            };
        }

        static std::vector<MeteoData> get_summer_scenarios()
        {
            return
            {
                {2.0f, 45.0f, StabilityClass::B, 40.0f},
                {1.5f, 90.0f, StabilityClass::B, 35.0f},
                {5.5f, 135.0f, StabilityClass::A, 70.0f},
                {6.0f, 180.0f, StabilityClass::A, 75.0f},
                {5.0f, 225.0f, StabilityClass::A, 65.0f},
                {4.5f, 270.0f, StabilityClass::B, 60.0f},
                {5.0f, 315.0f, StabilityClass::A, 65.0f},
                {4.0f, 0.0f, StabilityClass::B, 55.0f},
                {3.0f, 45.0f, StabilityClass::C, 50.0f},
                {2.5f, 180.0f, StabilityClass::B, 40.0f},
                {2.0f, 45.0f, StabilityClass::A, 70.0f},
                {1.5f, 90.0f, StabilityClass::A, 65.0f},
                {5.0f, 135.0f, StabilityClass::B, 60.0f},
                {6.0f, 180.0f, StabilityClass::B, 65.0f},            
                {2.5f, 225.0f, StabilityClass::C, 50.0f},
                {3.5f, 270.0f, StabilityClass::B, 62.0f},
                {4.2f, 315.0f, StabilityClass::B, 58.0f},
                {2.8f, 0.0f, StabilityClass::C, 55.0f},
                {1.2f, 45.0f, StabilityClass::A, 72.0f},
                {5.5f, 90.0f, StabilityClass::B, 62.0f}
            };
        }
};

inline const MeteoData& getRandomScenario(const std::vector<MeteoData>& scenarios)
{
    std::uniform_int_distribution<size_t> dist(0, scenarios.size() - 1);
    return scenarios[dist(rng)];
}

#endif // model_hpp