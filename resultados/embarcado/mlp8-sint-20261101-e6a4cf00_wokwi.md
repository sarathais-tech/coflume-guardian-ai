# Bancada ESP32-S3 (Wokwi): mlp8-sint-20261101-e6a4cf00

> **[SINTÉTICO] · Ambiente simulado.** Este relatório registra a **correção funcional** da Guardiã IA em um ESP32-S3 **simulado** no wokwi.com. Ele **não** mede o desempenho da placa física. O modelo foi treinado com **dados sintéticos** e **não foi validado com crianças reais**. Exportado só para a bancada: **não é versão de produção**.

## 1. Identificação

| Campo | Valor |
|---|---|
| Data da execução | 01/11/2026 |
| Executado por | Sara Thais, manualmente em wokwi.com, sem conta, token ou credenciais |
| Ambiente | `wokwi`: simulação do ESP32-S3, **não** é a placa física |
| Chip informado pelo firmware | ESP32-S3 |
| Sketch | `embarcado/bancada_wokwi/sketch.ino` (bancada v2, `BANCADA_AMBIENTE "wokwi"`), commit `9252d47` |
| Modelo | `mlp8-sint-20261101-e6a4cf00` |
| Hash do modelo | `e6a4cf0086ccf5ab1eccecbe7aea02f3962a6ad7ced29b136d36c5b37b5b9991` |
| Arquitetura | MLP 13 → 8 → 1, 121 parâmetros, float32 |
| Origem dos pesos | Execução 41329660286 do CI ([`ORIGEM.json`](../sinteticos/treino_v2/ORIGEM.json)) |
| Vetores testados | 400: 200 aleatórios (semente 7) e 200 da **validação** |
| Conjunto de teste lacrado | **Não usado** (continua fechado) |

**Fonte dos valores:** transcrição do monitor serial feita por quem executou a bancada (Sara Thais, 01/11/2026). O log bruto não foi anexado ao repositório. Por isso, valores que não constam da transcrição aparecem como "não transcrito".

## 2. Critérios funcionais

| Critério | Medido no Wokwi | Exigido | Situação |
|---|---|---|---|
| Erro máximo de P(acerto) vs. Python, nos dois grupos de vetores | 1,1920929e-7 | < 1e-5 | atende |
| Erro máximo nas features calculadas | 0 | ≤ 1e-6 | atende |
| Divergências em features inteiras | 0 | 0 | atende |
| Saídas inválidas para entradas válidas | não transcrito¹ | 0 | coberto pelo critério de equivalência¹ |
| Entradas fora da faixa → `INVALIDO` (10) e partida a frio em [0, 1] (36) | 46 de 46 | 46 de 46 | atende |
| Variação do heap ao redor de 10.000 chamadas de `prever()` | 0 bytes | 0 bytes | atende |
| Variação do heap ao redor de 10.000 chamadas de `montar_entrada()` | 0 bytes | 0 bytes | atende |

¹ O sketch só emite `criterio_equivalencia = APROVADO` quando, **em cada grupo**, o erro de P(acerto) é menor que 1e-5, o erro das features é no máximo 1e-6, não há divergência inteira **e** não há saída inválida (`bancada_ia.ino`, função `equivalencia`). O valor 1,1920929e-7 corresponde ao máximo dos dois grupos; ele vale 2⁻²³, uma diferença da ordem do arredondamento do float32, e é o mesmo valor obtido no PC.

### Veredito emitido pelo firmware

| Chave | Valor |
|---|---|
| `criterio_equivalencia` | **APROVADO** |
| `criterio_entradas` | **APROVADO** |
| `criterio_sem_alocacao` | **APROVADO** |
| `criterio_latencia` | `NAO_AVALIADO` (Wokwi) |
| `resultado` | **APROVADO_FUNCIONAL** |
| Encerramento | `BANCADA,fim,ok` |

## 3. Comparação com a execução no PC

| Critério | PC (`tests/test_bancada_wokwi.py`) | Wokwi (01/11/2026) |
|---|---|---|
| Erro máximo de P(acerto) | 1,19e-7 | 1,1920929e-7 |
| Erro máximo nas features | 0 | 0 |
| Divergências inteiras | 0 | 0 |
| Casos de entrada | 46 de 46 | 46 de 46 |
| Heap `prever()` / `montar_entrada()` | 0 / 0 bytes | 0 / 0 bytes |

Os dois ambientes concordam em todos os critérios funcionais.

## 4. O que esta execução comprova e o que não comprova

**Comprova, no ESP32-S3 simulado:**
- o runtime `guardia_runtime.h` (contrato 1.0.0), compilado pelo core Arduino-ESP32, reproduz as features e as probabilidades calculadas em Python para os pesos da MLP candidata;
- entradas fora da faixa são recusadas com `INVALIDO`, e a partida a frio produz probabilidades válidas;
- `prever()` e `montar_entrada()` não fazem alocação dinâmica (medido só ao redor dessas funções; o consumo total do firmware não é critério).

**Não comprova:**
- **Latência.** O Wokwi executa a CPU mais devagar que o chip real (por padrão, cerca de 8 MHz, segundo a documentação do Wokwi), com o temporizador em tempo real. A latência simulada **não** foi usada no veredito, **não** representa o ESP32-S3 físico e **não** é apresentada como desempenho da placa. O critério de latência (< 1 ms) continua **pendente** da placa física (fase D).
- **Comportamento do hardware real:** alimentação, gravação via USB, PSRAM e flash da placa N16R8.
- **Qualidade preditiva.** A bancada confere que a placa repete o Python; a qualidade do modelo é avaliada pelo protocolo e só será medida no teste na fase C, que ainda não foi aberta.
- **Eficácia educacional.** Todos os dados são sintéticos; não houve validação com crianças reais.

## 5. Limitações do registro

- Os valores vêm da transcrição do monitor serial, não do log bruto. Para auditoria completa, recomenda-se anexar o log e gerar o relatório com `python -m ferramentas.ler_bancada log_wokwi.txt`.
- O tipo de placa no `diagram.json` (`board-esp32-s3-devkitc-1`) não pôde ser confirmado na documentação oficial do Wokwi. O firmware identificou o chip como ESP32-S3.
- As linhas informativas (`cpu_mhz_configurada`, `sketch_bytes`, heap total e latências simuladas) não foram transcritas e não fazem parte do veredito.

## 6. Efeito na regra de decisão

Pelo [adendo 02](../../docs/protocolo_adendo_02.md), seção 5, a condição de **viabilidade embarcada** exige a correção funcional (Wokwi ou placa) **e** a latência na placa física. Com esta execução:

- **correção funcional: atendida** (Wokwi, 01/11/2026);
- **latência: pendente** da placa física.

Nada nesta execução altera o modelo, os critérios ou o conjunto de teste lacrado.
