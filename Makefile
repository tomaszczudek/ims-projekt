CXX = g++
CXXFLAGS = -Wall -Wextra -pedantic -std=c++17

SRC := $(wildcard src/*.cpp)
OBJ := $(SRC:src/%.cpp=src/%.o)

EXE = src/main

# Výchozí cíl
all: $(EXE)

# Linkování výsledného programu
$(EXE): $(OBJ)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJ)

# Kompilace jednotlivých .cpp na .o
src/%.o: src/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

.PHONY: clean run bin img

run: $(EXE)
	./$(EXE)

clean:
	rm -f $(OBJ) $(EXE)

# Make init data
bin:
	cd py && python3 export_to_bin.py

# Make img from data
img:
	cd py && python3 bin_to_img.py
