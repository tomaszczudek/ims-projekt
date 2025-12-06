#include <iostream>
#include <cstdio>
#include "loader.hpp"

int main()
{
    const char* bin_path = "src/init.bin";

    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "TERRAIN LOADER V5 - TERÉNS + TOVÁRNY" << std::endl;
    std::cout << std::string(70, '=') << std::endl;

    // Vytvoř loader
    Loader loader(bin_path);

    std::cout << "\n1️⃣  Načtení headeru..." << std::endl;
    if (!loader.load_header())
    {
        std::cerr << "✗ Chyba při načítání headeru!" << std::endl;
        return 1;
    }

    std::cout << "\n2️⃣  Načtení dat..." << std::endl;
    if (!loader.load_all_data())
    {
        std::cerr << "✗ Chyba při načítání dat!" << std::endl;
        return 1;
    }

    // Vypiš info
    std::cout << "\n3️⃣  Informace o terenu:" << std::endl;
    loader.print_info();

    // Vypiš továrny
    std::cout << "\n4️⃣  Továrny:" << std::endl;
    loader.print_plants();

    // Přístup k datům - PŘÍKLAD
    std::cout << "\n5️⃣  Přístup k datům - PŘÍKLADY:" << std::endl;
    std::cout << "------------------------------------" << std::endl;

    const auto& plants = loader.get_plants();
    if (!plants.empty())
    {
        // Vezmi první továrnu
        const auto& p = plants[0];
        std::cout << "\nPrvní továrna:" << std::endl;
        printf("  Pozice: (%u, %u)\n", p.row, p.col);
        printf("  Emise: %.2e kg/rok\n", p.emission);

        // Přístup k výšce a znečištění na dané pozici
        uint16_t height = loader.get_height(p.row, p.col);
        float pollution = loader.get_pollution(p.row, p.col);
        printf("  Výška na pozici: %u m\n", height);
        printf("  Znečištění na pozici: %.2e\n", pollution);
    }

    // Statistika terénu
    std::cout << "\n6️⃣  Statistika terénu:" << std::endl;
    std::cout << "------------------------------------" << std::endl;

    uint16_t min_height = UINT16_MAX;
    uint16_t max_height = 0;
    float min_pollution = 1e9;
    float max_pollution = 0;

    for (uint32_t row = 0; row < loader.get_height(); row++)
    {
        for (uint32_t col = 0; col < loader.get_width(); col++)
        {
            uint16_t h = loader.get_height(row, col);
            float p = loader.get_pollution(row, col);

            if (h > 0)
            {
                min_height = std::min(min_height, h);
                max_height = std::max(max_height, h);
            }

            if (p > 0)
            {
                min_pollution = std::min(min_pollution, p);
                max_pollution = std::max(max_pollution, p);
            }
        }
    }

    printf("Výšky: %u - %u m\n", min_height, max_height);
    printf("Znečištění: %.2e - %.2e\n\n", min_pollution, max_pollution);

    std::cout << std::string(70, '=') << std::endl;
    std::cout << "✓ HOTOVO!" << std::endl;
    std::cout << std::string(70, '=') << std::endl << std::endl;

    loader.save_to_binary("src/output.bin");
    // Cleanup
    loader.close();

    return 0;
}
