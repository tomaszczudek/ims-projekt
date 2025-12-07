CXX = g++
CXXFLAGS = -std=c++17 -O2

SRC := $(wildcard src/*.cpp)
OBJ := $(SRC:src/%.cpp=src/%.o)

EXE = src/main

all: $(EXE)

$(EXE): $(OBJ)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJ)

src/%.o: src/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

.PHONY: clean run bin img

run: $(EXE)
	./$(EXE)

clean:
	rm -f $(OBJ) $(EXE)

zip:
	zip -r 07_xczudet00_xkohutj00.zip src/loader.hpp src/stb_image_write.hpp src/sim.hpp src/main.cpp Makefile *.pdf
