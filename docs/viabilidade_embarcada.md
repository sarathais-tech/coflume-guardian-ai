# Viabilidade embarcada da MLP no ESP32-S3

**Sketch:** `embarcado/bancada_ia/bancada_ia.ino` (v2) · **Bancada com a MLP treinada:** `embarcado/bancada_wokwi/` ([instruções](bancada_wokwi.md))
**Situação (01/11/2026):** validado no PC com pesos aleatórios e com a MLP candidata treinada; **Wokwi e placa física pendentes**.

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

| Critério | Exigido | Onde vale |
|---|---|---|
| Erro máximo de `P(acerto)` vs. Python (vetores aleatórios e de validação) | < 1e-5 | Wokwi e placa |
| Erro máximo nas features calculadas | ≤ 1e-6 | Wokwi e placa |
| Divergências em features inteiras | 0 | Wokwi e placa |
| Saídas inválidas para entradas válidas | 0 | Wokwi e placa |
| Entradas fora da faixa retornam `INVALIDO`; partida a frio em [0, 1] | 46 de 46 casos | Wokwi e placa |
| Variação do heap livre ao redor de 10.000 chamadas de `prever()` e de `montar_entrada()` | 0 bytes | Wokwi e placa |
| Latência média de `prever()` | < 1000 µs | **Só na placa** |
| Pior latência observada de `prever()` | < 1000 µs | **Só na placa** |
| Compila no Arduino-ESP32 3.x com `-Wall` | sim | CI |

**Esclarecimentos de 01/11/2026 (bancada v2), pedidos pela equipe:**
1. O critério de heap passou a medir **só as funções da Guardiã**, lendo o heap livre imediatamente antes e depois de laços que chamam apenas `prever()` ou `montar_entrada()`. O consumo total do firmware é registrado à parte, como informação. A exigência (nenhuma alocação dinâmica) é a mesma.
2. No Wokwi, a CPU simulada é mais lenta que a real. A latência é registrada, mas só é avaliada na placa física. O resultado no Wokwi é `APROVADO_FUNCIONAL`.

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

### 5.2 MLP candidata treinada no PC (01/11/2026)

Modelo `mlp8-sint-20261101-e6a4cf00` (13 → 8 → 1, 121 parâmetros, 556 bytes de pesos e padronização), com 200 vetores aleatórios e 200 da validação. Executado pelo teste `tests/test_bancada_wokwi.py`:

| Critério | Resultado no PC |
|---|---|
| Erro máximo de P(acerto): aleatórios / validação | 1,19e-7 / 1,19e-7 |
| Erro máximo nas features | 0 |
| Divergências / inválidos | 0 / 0 |
| Entradas inválidas e partida a frio | 46 de 46 |
| Variação do heap em `prever()` / `montar_entrada()` | 0 / 0 bytes (medido com alocações reais do processo) |

### 5.3 Wokwi (ESP32-S3 simulado)

| Data | Modelo | Erro P máx. (aleat. / valid.) | Casos de entrada | Heap prever / montar | Resultado |
|---|---|---|---|---|---|
| _pendente_ | mlp8-sint-20261101-e6a4cf00 | | | | |

### 5.4 ESP32-S3 N16R8 (placa física)

| Data | Modelo | Erro P máx. | Latência média | Pior latência | Decisão 3 níveis | Heap prever / montar | Resultado |
|---|---|---|---|---|---|---|---|
| _pendente_ | mlp8-sint-20261101-e6a4cf00 | | | | | | |

### 5.5 Compilação no CI

O job `bancada-esp32s3` compila `embarcado/bancada_ia` (pesos aleatórios) e `embarcado/bancada_wokwi` (MLP treinada) com o core oficial Arduino-ESP32 para ESP32-S3.

Execução 41334398909 (01/11/2026), `embarcado/bancada_wokwi`: **compilou sem erros** com `--warnings all`. O sketch ocupa **349.059 bytes** de programa (26% da partição padrão de 1.310.720 bytes) e **31.676 bytes** de RAM em variáveis globais (9%). Esses números incluem os 400 vetores de teste da bancada, que não estarão no firmware do cofre.

## 6. Próximo experimento (opcional, ADR 0004)

TensorFlow Lite Micro num sketch separado, `exp/tflite-micro`, comparando tamanho e latência com este runtime. Só se houver tempo após o portão G1.
