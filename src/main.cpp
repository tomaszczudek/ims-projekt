#include "loader.hpp"
#include "sim.hpp"

#define BIN_PATH "src/init.bin"
#define OUTPUT_PATH "src/output.bin"
#define NUM_ITERATION 200

int main()
{
    Loader loader(BIN_PATH);

    if (!loader.load_header())
        return 1;

    if (!loader.load_all_data())
        return 1;
    // Data loaded successfully

    Simulation sim(loader.get_heights(), loader.get_pollution(), loader.get_height(), loader.get_width());

    // Run the simulation
    sim.run_simulation(loader.get_plants(), NUM_ITERATION);

    // Save results to binary file
    loader.save_to_binary(OUTPUT_PATH);

    return 0;
}
