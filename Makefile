CXX = g++
CXXFLAGS = -std=c++17 -O2

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

zip:
	zip -r 07_xczudet00_xkohutj00.zip src/  Makefile
# Make init data
bin:
	cd py && python3 export_to_bin.py

# Make img from data
img:
	cd py && python3 bin_to_img.py
