#include "Configuration.h"
#include "Util.h"
#include <iostream>
#include <limits>
int main(int argc, char* argv[]) {
  Configuration config; config.parse(argc, argv);
  int actual = config.get<int>("eval_limit");
  std::cout << "declared " << config.get<std::string>("eval_limit") << "\n"
            << "actual_int " << actual << "\n"
            << "actual_size_t " << static_cast<size_t>(actual) << "\n"
            << "int_max " << std::numeric_limits<int>::max() << "\n";
  Random random(63001); std::cout << "rng_initial " << random << "\n";
}
