# ADR 0003: MLP float32 com runtime C++ próprio

- **Status:** aceito
- **Data:** 2026-10-28

## Contexto
A MLP tem 369 parâmetros e cerca de 350 multiplicações por inferência. O firmware usa Arduino IDE com Arduino-ESP32 3.x. O ESP32-S3 tem FPU de precisão simples.

## Opções avaliadas
1. Runtime próprio em C++, float32, *header-only*.
2. TensorFlow Lite Micro via biblioteca da comunidade para Arduino.
3. ESP-DL (ver ADR 0005).

## Decisão
Opção 1 como implementação principal. Os pesos são exportados para arrays `constexpr` por `guardia/exportar/mlp_cpp.py`, e a inferência fica em `embarcado/runtime/guardia_runtime.h`.

## Consequências
- Nenhuma dependência externa no firmware.
- O mesmo código é compilado no PC (g++) e testado contra o Python a cada commit.
- A equipe implementa e explica cada operação da rede, o que tem valor didático.
- Não aproveita as otimizações do ESP-NN, o que é irrelevante para este tamanho de rede.
- Quantização int8 fica como experimento separado.
