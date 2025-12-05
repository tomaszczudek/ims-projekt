CXX = g++
CXXFLAGS = -Wall -Wextra -Werror -pedantic -std=c++17

SRC := $(wildcard src/*.cpp)
OBJ := $(SRC:.cpp=.o)

EXE = main

$(EXE): $(OBJ)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJ)

src/%.o: src/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

.PHONY: clean
clean:
	rm -f $(OBJ) $(EXE)