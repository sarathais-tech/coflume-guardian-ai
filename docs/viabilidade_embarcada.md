# Viabilidade embarcada da MLP no ESP32-S3

**Branch:** `exp/bancada-esp32s3`
**Situação:** sketch pronto e validado no PC; **execução na placa pendente**.

## 1. Objetivo

Comprovar, antes de treinar qualquer modelo e antes de tocar no firmware do cofre, que a MLP 13 → 16 → 8 → 1 em float32:

1. produz no ESP32-S3 as mesmas previsões do Python;
2. executa em menos de 1 ms;
3. não aloca memória dinâmica;
4. compila no Arduino-ESP32 3.x sem bibliotecas externas.

A bancada usa **pesos aleatórios**. O custo computacional depende só da arquitetura (número de multiplicações), não do valor dos pesos. Por isso o teste é válido para o modelo treinado com a mesma arquitetura, e o risco técnico é eliminado cedo.

## 2. Por que não usa o hardware do cofre

O sketch não usa TFT, teclado, servo nem LEDs. Basta a placa e o cabo USB. Assim, o resultado mede apenas a IA, e o firmware do cofre permanece intocado.

## 3. Procedimento

### 3.1 Gerar os cabeçalhos
```bash
python -m ferramentas.gerar_bancada --semente 2026
```
Isso cria, em `embarcado/bancada_ia/`, os arquivos `guardia_modelo.h`, `guardia_runtime.h` e `vetores_teste.h` (não versionados).

### 3.2 Compilar e gravar no Arduino IDE
1. Abra `embarcado/bancada_ia/bancada_ia.ino`.
2. Em **Ferramentas**, configure:

| Opção | Valor |
|---|---|
| Placa | ESP32S3 Dev Module |
| Flash Size | 16MB (128Mb) |
| PSRAM | OPI PSRAM |
| CPU Frequency | 240MHz (WiFi) |
| USB CDC On Boot | **Enabled** se o cabo estiver na porta "USB"; Disabled se estiver na porta "UART/COM" |

3. Anote o tamanho do sketch que o IDE informa ao compilar.
4. Grave na placa e abra o Monitor Serial a **115200 baud**.
5. Se nada aparecer, pressione o botão **RST** da placa.

### 3.3 Registrar o resultado
1. Copie toda a saída do Monitor Serial para `log_bancada.txt`.
2. Rode:
   ```bash
   python -m ferramentas.ler_bancada log_bancada.txt --salvar
   ```
3. O relatório vai para `resultados/embarcado/<modelo_id>.md`. Faça commit dele no branch `exp/bancada-esp32s3`.

### 3.4 Variações recomendadas
Para ter dados da escolha de tamanho da rede, repita com:
```bash
python -m ferramentas.gerar_bancada --ocultas 8
python -m ferramentas.gerar_bancada --ocultas 32 16
```

## 4. Critérios de aprovação

| Critério | Exigido |
|---|---|
| Erro máximo de `P(acerto)` vs. Python | < 1e-5 |
| Erro máximo nas features calculadas | ≤ 1e-6 |
| Divergências em features inteiras | 0 |
| Saídas inválidas para entradas válidas | 0 |
| Latência média de `prever()` | < 1000 µs |
| Pior latência observada de `prever()` | < 1000 µs |
| Heap consumido durante o teste | 0 bytes |
| Compila no Arduino-ESP32 3.x com `-Wall` | sim |

Uso de pilha: os buffers da inferência somam 37 floats (13 + 16 + 8), ou seja, 148 bytes, abaixo do limite de 256 bytes do contrato. Esse valor vem da análise do código e não é medido pela bancada.

## 5. Resultados

### 5.1 Simulação no PC (28/10/2026)

O mesmo sketch foi compilado no PC (g++ 13, `-O2 -Wall -Wextra -Werror`) com um stub da API Arduino e executado pelo teste `tests/test_bancada.py`. Isso valida a lógica do sketch e o formato do log, **não** o desempenho na placa.

| Critério | Resultado no PC |
|---|---|
| Erro máximo de P(acerto) | 1,19e-7 |
| Erro máximo nas features | 0 (idênticas bit a bit) |
| Divergências / inválidos | 0 / 0 |
| Pesos e padronização | 1.548 bytes |

### 5.2 ESP32-S3 N16R8

| Data | Modelo | Erro P máx. | Latência média | Pior latência | Decisão 3 níveis | Heap | Sketch | Resultado |
|---|---|---|---|---|---|---|---|---|
| _pendente_ | mlp16x8-aleat | | | | | | | |

### 5.3 Compilação no CI

O job `bancada-esp32s3` do GitHub Actions compila o sketch com o core oficial Arduino-ESP32. Esse job ainda não foi executado; ele roda no primeiro push ao GitHub.

## 6. Próximo experimento (opcional, ADR 0004)

TensorFlow Lite Micro num sketch separado, `exp/tflite-micro`, comparando tamanho e latência com este runtime. Só se houver tempo após o portão G1.
