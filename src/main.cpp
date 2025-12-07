#include "loader.hpp"
#include "sim.hpp"

#define BIN_PATH "src/init32.bin"
#define OUTPUT_PATH_BIN "src/output.bin"
#define OUTPUT_PATH_PNG "output.png"
#define NUM_ITERATION 200

#define DEBUG 0

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

    // Save results to image
    loader.save_png(OUTPUT_PATH_PNG);
    
    #if DEBUG
        loader.save_to_binary(OUTPUT_PATH_BIN);
    #endif

    return 0;
}
