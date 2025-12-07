#include <iostream>
#include <cstdio>
#include <cmath>
#include "loader.hpp"
#include "model.hpp"

#define NUM_ITERATIONS 10
#define SEASON 3

int main()
{
    const char* bin_path = "src/init32.bin";

    Loader loader(bin_path);

    if (!loader.load_header())
        return 1;

    if (!loader.load_all_data())
        return 1;

    loader.print_info();

    std::cout << "\n2️⃣  Nastavení parametrů..." << std::endl;
    uint32_t width_px = loader.get_width();
    uint32_t height_px = loader.get_height();

    std::cout << "  Grid: " << width_px << "×" << height_px << " px" << std::endl;
    std::cout << "  Pokrytí: " << WIDTH_KM << "×" << HEIGHT_KM << " km" << std::endl;
    std::cout << "  Resolution: " << ((WIDTH_KM * 1000.0f) / width_px + (HEIGHT_KM * 1000.0f) / height_px) / 2.0f << " m/px" << std::endl;

    std::vector<MeteoData> scenarios;

    switch(SEASON)
    {
        case 1:
            scenarios = MeteoScenarios::get_winter_scenarios();
            break;
        case 2:
            scenarios = MeteoScenarios::get_spring_autumn_scenarios();
            break;
        case 3:
            scenarios = MeteoScenarios::get_summer_scenarios();
            break;
        default:
            scenarios = MeteoScenarios::get_winter_scenarios();
    }

    GaussianPlumeModel model(
        width_px,
        height_px,
        loader.get_pollution_mut(),    // Reference na pollution
        loader.get_heights_mut(),          // Reference na heights ← NOVÉ!
        3.0f,                          // Default wind speed (budeme měnit)
        StabilityClass::C,             // Default stability (budeme měnit)
        50.0f                          // Default effective height (budeme měnit)
    );

    model.print_stats();

    // ==================== KROK 5: ITERATIVNÍ VÝPOČET SE ELEVACÍ ====================
    std::cout << "\n5️⃣  Iterativní výpočet rozptylu se zohledněním terénu..." << std::endl;

    const auto& plants = loader.get_plants();

    float max_conc_overall = 0.0f;

    for (size_t iter = 0; iter < NUM_ITERATIONS; iter++)
    {
        const auto& meteo = getRandomScenario(scenarios);

        // Nastav meteorologické parametry
        model.set_wind_speed(meteo.wind_speed);
        model.set_stability(meteo.stability);
        model.set_effective_height(meteo.effective_height);

        // Vypočítej rozptyl (bude zohledňovat nadmořskou výšku!)
        model.calculate_dispersion_all_plants(plants, meteo.wind_direction);

        // Statistika
        auto& pollution = loader.get_pollution_mut();
        float max_conc = 0.0f;
        for (uint32_t row = 0; row < height_px; row++)
            for (uint32_t col = 0; col < width_px; col++)
                max_conc = std::max(max_conc, pollution[row][col]);

        if (max_conc > max_conc_overall)
            max_conc_overall = max_conc;

        printf("  [%2lu/%d] \n",
               iter+1, NUM_ITERATIONS);
        printf("           Vítr: %.1f m/s @ %.0f°, H_eff: %.0f m, Max: %.2e kg/m³\n",
               meteo.wind_speed, meteo.wind_direction, 
               meteo.effective_height, max_conc);
    }
/*
    // ==================== KROK 6: FINÁLNÍ STATISTIKA ====================
    std::cout << "\n6️⃣  KUMULATIVNÍ STATISTIKA (SE ELEVACÍ):" << std::endl;
    std::cout << "───────────────────────────────────────────────" << std::endl;

    auto& pollution_final = loader.get_pollution_mut();

    float total = 0.0f;
    float max_val = 0.0f;
    float min_val = 1e9f;
    uint32_t cells = 0;
    uint32_t nonzero = 0;

    for (uint32_t row = 0; row < height_px; row++)
    {
        for (uint32_t col = 0; col < width_px; col++)
        {
            float val = pollution_final[row][col];

            total += val;
            cells++;

            if (val > 0.0001f) {
                max_val = std::max(max_val, val);
                min_val = std::min(min_val, val);
                nonzero++;
            }
        }
    }

    printf("Iterací: %lu\n", scenarios.size());
    printf("Celkem buněk: %u\n", cells);
    printf("Nenulových: %u (%.1f%%)\n", nonzero, (float)nonzero/cells*100.0f);
    printf("\nZnečištění:\n");
    printf("  Součet: %.2e kg/m³\n", total);
    printf("  Max: %.2e kg/m³ (iter %u)\n", max_val, max_iter);
    printf("  Min (>0): %.2e kg/m³\n", min_val == 1e9f ? 0.0f : min_val);
    printf("  Průměr: %.2e kg/m³\n\n", total / cells);

    // Informace o terénu
    printf("Terén (ze Loaderu):\n");
    printf("  Min elevace: %u m\n", model.get_min_elevation());
    printf("  Max elevace: %u m\n", model.get_max_elevation());
    printf("  Avg elevace: %.1f m\n", model.get_avg_elevation());
    printf("  Rozpětí: %u m\n\n", 
           model.get_max_elevation() - model.get_min_elevation());

    // ==================== KROK 7: TOP ZDROJE ====================
    std::cout << "7️⃣  TOP 5 ZDROJŮ (Emise):" << std::endl;
    std::cout << "───────────────────────────────────────────────" << std::endl;

    std::vector<std::pair<size_t, float>> indexed_plants;
    for (size_t i = 0; i < plants.size(); i++) {
        indexed_plants.push_back({i, plants[i].emission});
    }

    std::sort(indexed_plants.begin(), indexed_plants.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });

    for (int i = 0; i < std::min(5, (int)plants.size()); i++) {
        size_t idx = indexed_plants[i].first;
        const auto& p = plants[idx];
        uint16_t elev = loader.get_heights_mut()[p.row][p.col];

        printf(" %d. Plant #%3lu: (%u, %u)\n", i+1, idx, p.row, p.col);
        printf("      Emise: %.2e kg/rok\n", p.emission);
        printf("      Elevace: %u m, Výška nad terénem: %.0f m (eff_height + elev)\n\n",
               elev, 50.0f + elev);  // Default 50m effective height
    }
*/
    // ==================== KROK 8: ULOŽ VÝSLEDKY ====================
    std::cout << "8️⃣  Uložení výsledků..." << std::endl;

    char output_file[20] = "src/output.bin";
    loader.save_to_binary(output_file);
/*
    // ==================== VÝSLEDEK ====================
    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "✓ ITERATIVNÍ SIMULACE V3 (SE ELEVACÍ) HOTOVA!" << std::endl;
    std::cout << std::string(70, '=') << std::endl;

    std::cout << "\n📊 SHRNUTÍ:" << std::endl;
    std::cout << "   Scénářů: " << scenarios.size() << std::endl;
    std::cout << "   Max znečištění: " << max_val << " kg/m³" << std::endl;
    std::cout << "   Pokrytí: " << (float)nonzero/cells*100.0f << "%% nenulových buněk" << std::endl;
    std::cout << "   Výstup: " << output_file << std::endl;
    std::cout << "\n✅ Model NYNÍ zohledňuje nadmořskou výšku!\n" << std::endl;

    std::cout << "🎯 ROZDÍLY OPROTI V2:" << std::endl;
    std::cout << "   ✓ Čte heights_ z Loaderu" << std::endl;
    std::cout << "   ✓ Počítá RELATIVNÍ výšku emise (zdroj - terén)" << std::endl;
    std::cout << "   ✓ Znečištění se lépe rozprostírá v horách" << std::endl;
    std::cout << "   ✓ V údolích se více akumuluje" << std::endl;
    std::cout << "   ✓ Fyzikálně realističtější\n" << std::endl;
*/
    std::cout << "✅ SIMULACE SE ZOHLEDNĚNÍM NADMOŘSKÉ VÝŠKY HOTOVA!" << std::endl;
    loader.close();
    return 0;
}
