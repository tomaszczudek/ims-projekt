#include "loader.hpp"
#include "sim.hpp"

#define BIN_PATH "src/init32.bin"
#define OUTPUT_PATH "src/output.bin"
#define NUM_ITERATION 5

int main()
{
    Loader loader(BIN_PATH);

    if (!loader.load_header())
        return 1;

    if (!loader.load_all_data())
        return 1;

    Simulation sim(loader.get_heights(), loader.get_pollution());

    // Data loaded successfully
    sim.run_simulation(loader.get_plants(), NUM_ITERATION, loader.get_height(), loader.get_width());

    // Save results to binary file
    loader.save_to_binary(OUTPUT_PATH);

    return 0;
}
