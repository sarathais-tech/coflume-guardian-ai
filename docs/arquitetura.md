# Arquitetura da Guardiã IA

**Projeto:** Coflume — O Conhecimento Abre Portas
**Componente:** Guardiã IA
**Versão do documento:** 1.0 (28/10/2026)

## 1. Papel da IA no Coflume

A Guardiã IA responde a uma única pergunta:

> Dado o comportamento do participante até agora nesta sessão, qual a probabilidade de ele acertar uma questão de **nível X** na **categoria Y**?

O rótulo de treino é **acertou ou errou**, um fato observado. O modelo nunca é treinado para imitar uma regra escrita por nós. Isso é o que diferencia a Guardiã de um conjunto de regras fixas.

O firmware usa essa probabilidade para escolher o nível da próxima questão (alvo de ~70% de chance de acerto). A decisão final, o desbloqueio e o servo continuam sendo lógica tradicional, auditável e testável.

## 2. Divisão entre repositórios

| Repositório | Responsabilidade |
|---|---|
| `coflume-guardian-ai` (este) | Features, modelos, dados sintéticos, treino, avaliação, exportação C++, runtime de inferência, documentação científica |
| `coflume` | Firmware do ESP32-S3, hardware, TFT, teclado, servo, LEDs, regras do jogo, desbloqueio |

A fronteira entre os dois é o [contrato de integração](contrato_integracao.md). Ver [ADR 0001](adr/0001-dois-repositorios-e-contrato.md).

## 3. Visão geral

```
┌──────────────────────── coflume-guardian-ai (PC, offline) ────────────────────────┐
│                                                                                    │
│  simulador (SINTÉTICO) ─┐                                                          │
│  logs do piloto (REAL) ─┴─> features.py ─> divisão por participante                │
│                                              │                                     │
│                         ┌────────────────────┼──────────────────┐                  │
│                      árvore            regressão logística     MLP (Keras)         │
│                         └────────────────────┼──────────────────┘                  │
│                                         avaliação (protocolo pré-registrado)       │
│                                              │ aprovado?                           │
│                                              ▼                                     │
│                     exportar/mlp_cpp.py ─> guardia_modelo.h + MODELO.json          │
│                     embarcado/runtime/guardia_runtime.h (fixo, versionado)         │
│                                              │                                     │
│                     testes: Python × C++ (g++) e bancada no ESP32-S3               │
│                                              │                                     │
│                                       release vX.Y.Z                               │
└──────────────────────────────────────────────┼─────────────────────────────────────┘
                                               ▼
┌─────────────────────────────── coflume (ESP32-S3) ─────────────────────────────────┐
│  registra respostas ─> guardia::montar_entrada() ─> guardia::prever() ─> P(acerto) │
│                                                          │                         │
│  política do jogo (alvo ~70%, sem repetição, reforço) ◄──┘                         │
│  validador de desbloqueio ─> servo   (a IA nunca aciona o servo)                   │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## 4. Machine Learning × lógica tradicional

| Componente | Onde | Tipo |
|---|---|---|
| Estimar `P(acerto)` | este repositório (treino) e runtime (inferência) | **Machine Learning** |
| Calcular as features a partir do histórico | `guardia_runtime.h` (`montar_entrada`) | Pré-processamento determinístico |
| Escolher o nível com `P` próxima de 0,70 | firmware | Lógica (política) que **usa** a IA |
| Escolher a categoria, evitar repetição | firmware | Lógica tradicional |
| Reforço após erro | firmware | Lógica tradicional |
| Critério de desbloqueio e servo | firmware | Lógica tradicional, nunca ML |

## 5. Modelos

| Modelo | Papel | Implementação embarcada |
|---|---|---|
| **MLP 13 → 16 → 8 → 1** | Modelo experimental principal | `guardia_runtime.h`, float32, C++ próprio ([ADR 0003](adr/0003-mlp-float32-runtime-proprio.md)) |
| Árvore de decisão | Baseline e alternativa de segurança | Exportador previsto para a versão 1.1 do contrato ([ADR 0002](adr/0002-arvore-baseline.md)) |
| Regressão logística | Referência de comparação | Somente em Python |
| Baseline ingênuo (taxa por nível) | Piso mínimo a superar | Somente em Python |
| MLP via TFLite Micro | Experimento comparativo | Branch `exp/*`, nunca no firmware ([ADR 0004](adr/0004-tflite-micro-experimental.md)) |
| ESP-DL | Avaliado e descartado | — ([ADR 0005](adr/0005-esp-dl-descartado.md)) |

### MLP

```
entrada (13) ─> Dense(16, ReLU) ─> Dense(8, ReLU) ─> Dense(1, Sigmoid) ─> P(acerto)
```

- 369 parâmetros, cerca de 1,5 KB em float32.
- As 9 features numéricas são padronizadas com média e desvio do **conjunto de treino**; os 4 valores one-hot de categoria não são padronizados.
- A padronização faz parte do modelo exportado: o firmware nunca normaliza nada por conta própria.

## 6. Entradas

Especificadas em [`features.md`](features.md), incluindo o comportamento na primeira questão.

## 7. Segurança da versão da feira

- O runtime é uma função pura, sem alocação dinâmica e sem estado global.
- Entradas fora da faixa ou saídas inválidas retornam `guardia::INVALIDO`, e o firmware usa a alternativa (árvore ou regra fixa).
- Nenhum modelo chega ao firmware sem passar no [protocolo de avaliação](protocolo_avaliacao.md) e nos testes de equivalência.
