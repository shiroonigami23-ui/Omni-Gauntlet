CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Werror
core_test: core_test.cpp ../lib/omni_core/src/omni_core.cpp ../lib/omni_core/src/omni_core.h
	$(CXX) $(CXXFLAGS) -o $@ core_test.cpp ../lib/omni_core/src/omni_core.cpp -lm
	./$@
.PHONY: clean
clean:
	rm -f core_test
