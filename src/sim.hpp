#ifndef sim_hpp
#define sim_hpp
/**
 * Pravidla simulace:
 * 
 * Pokud bunka ma hodnotu -> uber z bunky pulku a rozloz 
 */
#include <vector>
#include <iostream>
#include <cmath>

#define dir(x, y) M_PI * x / 8 < deg && deg < M_PI * y / 8
#define DISP 0.2

class Simulation {
    public:
        int run_sim() {
            std::vector<std::vector<int>> field(100, std::vector<int>(100, 0));

            field[50][50] = 80;

            

            print_sim(&field);
            

            int dx = 100;
            int dy = 100;
            int dz = 10;
            int dt = 10;
            float ux = -5;
            float uy = -5;
            float k = 20;
            float vs = 0.03;
            float vd = DISP;

            float windx = ux * dt / dx; 
            float windy = uy * dt / dy;
            float diffx = k * dt / (dx * dx);
            float diffy = k * dt / (dy * dy);

            int ddx=0, ddy=0;
            float deg = 0;

            for (int x = 0; x < 100; x++) {
                for (int y = 0; y < 100; y++) {
                    deg = atan2 (uy, ux);
                    
                    if (dir(1, 3))  {
                        ddx = 1;
                        ddy = 1;
                    } else if (dir(3, 5)) {
                        ddx = 0;
                        ddy = 1;
                    } else if (dir(5, 7)) {
                        ddx = -1;
                        ddy = 1;
                    } else if (dir(7, 9)) {
                        ddx = -1;
                        ddy = 0;
                    } else if (dir(9, 11)) {
                        ddx = -1;
                        ddy = -1;
                    } else if (dir(11, 13)) {
                        ddx = 0;
                        ddy = -1;
                    } else if (dir(13, 15)) {
                        ddx = 1;
                        ddy = -1;
                    } else {
                        ddx = 1;
                        ddy = 0;
                    }

                    if (field[y][x] != 0) {
                        if(y + 1 < 100 && x + 1 < 100 && field[y+1][x+1] < DISP * field[y][x])
                            field[y+1][x+1] = DISP * field[y][x];

                        if(y + 1 < 100 && field[y+1][x] < DISP * field[y][x])
                            field[y+1][x] = DISP * field[y][x];

                        if(y + 1 < 100 && x - 1 > 0 && field[y+1][x-1] < DISP * field[y][x])
                            field[y+1][x-1] = DISP * field[y][x];

                        if(x - 1 > 0 && field[y][x-1] < DISP * field[y][x])
                            field[y][x-1] = DISP * field[y][x];

                        if(y -1 > 0 && x - 1 > 0 && field[y-1][x-1] < DISP * field[y][x])
                            field[y-1][x-1] = DISP * field[y][x];

                        if(y - 1 > 0 && field[y-1][x] < DISP * field[y][x])
                            field[y-1][x] = DISP * field[y][x];

                        if(y - 1 > 0 && x + 1 < 100 && field[y-1][x+1] < DISP * field[y][x])
                            field[y-1][x+1] = DISP * field[y][x];

                        if(x + 1 < 100 && field[y][x+1] < DISP * field[y][x] && field[y][x+1] < DISP * field[y][x])
                            field[y][x+1] = DISP * field[y][x];
                    }

                    if (y+ddy < 100 && x+ddx < 100 && field[y][x] != 0) {
                        field[y+ddy][x+ddx] = 0.5 * field[y][x];
                    }
                }
            }

            print_sim(&field);

            return 0;
        }

        void print_sim(std::vector<std::vector<int>> *field) {
            std::cout << "    ";
            for (int x = 0; x < 100; x++)
                if (x < 10)
                    std::cout << x << "   ";
                else if (x < 100)
                    std::cout << x << "  ";
                else
                    std::cout << x << " ";

            std::cout << std::endl;

            for (int y = 99; y; y--) {
                if (y < 10)
                    std::cout << y << ":   ";
                else if (y < 100)
                    std::cout << y << ":  ";
                else 
                    std::cout << y << ": ";

                for (int x = 0; x < 100; x++) {
                    if ((*field)[y][x] == 0)
                        std::cout <<  " ";
                    else
                        std::cout << (int)(*field)[y][x];

                    if ((*field)[y][x] < 10)
                        std::cout << "   ";
                    else if ((*field)[y][x] < 100)
                        std::cout << "  ";
                    else 
                        std::cout << " ";
                }
                std::cout << std::endl;
            }
        }

        int translate_y(int x) {
            return 99 - x;
        }
};

#endif