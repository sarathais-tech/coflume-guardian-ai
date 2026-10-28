// Stub mínimo da API Arduino-ESP32 para compilar e executar o sketch de bancada
// no PC. Usado apenas em tests/test_bancada_host.py; não vai para a placa.
#pragma once
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <thread>

inline uint32_t millis() {
  using namespace std::chrono;
  static const auto t0 = steady_clock::now();
  return (uint32_t)duration_cast<milliseconds>(steady_clock::now() - t0).count();
}
inline void delay(uint32_t) {}
inline uint32_t getCpuFrequencyMhz() { return 0; }

struct StubSerial {
  void begin(unsigned long) {}
  explicit operator bool() const { return true; }
  int printf(const char* fmt, ...) __attribute__((format(printf, 2, 3))) {
    va_list ap;
    va_start(ap, fmt);
    int n = std::vprintf(fmt, ap);
    va_end(ap);
    return n;
  }
};
static StubSerial Serial;

struct StubEsp {
  const char* getChipModel() { return "HOST"; }
  uint32_t getSketchSize() { return 0; }
  uint32_t getPsramSize() { return 0; }
  uint32_t getFreeHeap() { return 100000; }
};
static StubEsp ESP;
