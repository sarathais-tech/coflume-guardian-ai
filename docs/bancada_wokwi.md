# Bancada da Guardiã IA no Wokwi (ESP32-S3)

**Pasta:** `embarcado/bancada_wokwi/` · **Modelo:** `mlp8-sint-20261101-e6a4cf00` (MLP 13 → 8 → 1, 121 parâmetros)
**Origem dos pesos:** execução 41329660286 do CI, conferida ([`ORIGEM.json`](../resultados/sinteticos/treino_v2/ORIGEM.json))

> **Exportação só para a bancada.** Não é versão de produção nem release. O modelo foi treinado com **dados sintéticos** e **não foi validado com crianças reais**. A bancada não usa o conjunto de teste lacrado. A v0.7 do cofre não é alterada.

## 1. O que a bancada prova

| Pergunta | Onde é respondida |
|---|---|
| O ESP32-S3 calcula as mesmas features e as mesmas probabilidades que o Python? | **Wokwi** e placa |
| Entradas inválidas retornam `INVALIDO`, e a partida a frio funciona? | **Wokwi** e placa |
| `prever()` e `montar_entrada()` fazem alocação dinâmica? | **Wokwi** e placa |
| A previsão leva menos de 1 ms? | **Somente na placa física** |

O Wokwi executa a CPU do ESP32 mais devagar que o chip real (por padrão, cerca de 8 MHz, segundo a documentação do Wokwi), enquanto o temporizador continua em tempo real. Por isso **a latência medida no Wokwi não representa o ESP32-S3 físico** e não entra no veredito.

## 2. Executar no wokwi.com (sem conta, token ou credenciais)

1. Acesse **wokwi.com** e crie um projeto novo de **Arduino para ESP32-S3**. Se só encontrar o modelo de ESP32 comum, crie-o e substitua o `diagram.json` no passo 4.
2. Abra o arquivo `sketch.ino` do projeto, apague tudo e cole o conteúdo de `embarcado/bancada_wokwi/sketch.ino`.
3. Crie três arquivos novos no projeto, com **exatamente** estes nomes, e cole o conteúdo correspondente:
   - `guardia_modelo.h`
   - `guardia_runtime.h`
   - `vetores_teste.h` (o maior, com cerca de 75 KB)
4. **`diagram.json`:** se o modelo do Wokwi já for ESP32-S3, mantenha o dele. Senão, cole o de `embarcado/bancada_wokwi/diagram.json`. Esse arquivo usa o tipo `board-esp32-s3-devkitc-1`, um nome comum que **não pôde ser confirmado** na documentação oficial; se o Wokwi não reconhecer, use o modelo dele.
5. Clique em **Start the simulation** (botão verde ▶).
6. Aguarde a linha **`BANCADA,fim,ok`** no monitor serial. Como a CPU simulada é lenta, **pode levar alguns minutos**: são dezenas de milhares de chamadas da rede.
7. Copie **todo** o texto do monitor serial para um arquivo `log_wokwi.txt`.

Para gerar o relatório:

```bash
python -m ferramentas.ler_bancada log_wokwi.txt --salvar
```

O relatório vai para `resultados/embarcado/mlp8-sint-20261101-e6a4cf00_wokwi.md`. Sem Python à mão, basta enviar o log para análise.

## 3. Como ler o monitor serial

Cada linha tem o formato `BANCADA,<chave>,<valor>`.

### Identificação

| Chave | Esperado |
|---|---|
| `inicio` | `guardia_bancada_v2` |
| `ambiente` | `wokwi` |
| `modelo_id` | `mlp8-sint-20261101-e6a4cf00` |
| `modelo_hash` | `e6a4cf0086ccf5ab1eccecbe7aea02f3962a6ad7ced29b136d36c5b37b5b9991` |
| `modelo_fonte` | `SINTETICO` |
| `modelo_uso` | `bancada (nao e versao de producao)` |
| `n_parametros` / `camadas_ocultas` | `121` / `1` |
| `chip` | `ESP32-S3` |
| `cpu_mhz_configurada` | Valor pedido ao chip; no Wokwi, **não** é a velocidade real da simulação |

### Correção funcional (critérios)

| Chave | Significado | Exigido |
|---|---|---|
| `erro_p_max_aleatorios` | Maior diferença de P(acerto) entre o ESP32-S3 e o Python, nos 200 vetores aleatórios | < 1e-5 |
| `erro_p_max_validacao` | O mesmo, nos 200 vetores tirados da validação | < 1e-5 |
| `erro_features_max` | Maior diferença nas features calculadas | ≤ 1e-6 |
| `falhas_inteiras` | Divergências em nível, categoria, contagem, resultado ou sequência | 0 |
| `invalidos` | Entradas válidas que retornaram `INVALIDO` por engano | 0 |
| `casos_entrada_corretos` / `casos_entrada_testados` | 10 entradas fora da faixa devem dar `INVALIDO`, e 36 partidas a frio devem dar uma probabilidade entre 0 e 1 | 46 de 46 |
| `heap_variacao_prever_bytes` | Variação do heap livre ao redor de 10.000 chamadas de `prever()` | **0** |
| `heap_variacao_montar_entrada_bytes` | O mesmo para `montar_entrada()` | **0** |

O **critério de heap** mede só as funções da Guardiã: o heap livre é lido imediatamente antes e depois de laços que só as chamam. Os valores `heap_livre_total_informativo` e `heap_minimo_livre_informativo` mostram o estado geral do firmware e **não são critério**.

### Latência (informativa no Wokwi)

`latencia_prever_us_media`, `latencia_decisao_3_niveis_us_media` e `latencia_prever_us_pior` aparecem com `latencia_valida = nao (CPU simulada; apenas indicativa)` e `criterio_latencia = NAO_AVALIADO`. **Não use esses números como desempenho da placa.**

### Veredito

| Chave | Valor esperado no Wokwi |
|---|---|
| `criterio_equivalencia`, `criterio_entradas`, `criterio_sem_alocacao` | `APROVADO` |
| `resultado_funcional` | `APROVADO` |
| `resultado` | **`APROVADO_FUNCIONAL`**: correto, mas sem avaliação de desempenho |
| `fim` | `ok` |

## 4. Resultado esperado

O mesmo `sketch.ino`, compilado no PC com uma imitação da API do Arduino (`tests/test_bancada_wokwi.py`), teve:
- erro máximo de **1,19e-7** nos dois grupos de vetores;
- features idênticas;
- 46 de 46 casos de entrada corretos;
- **0 bytes** de variação do heap.

No Wokwi espera-se o mesmo resultado funcional. Diferenças da ordem de 1e-7 são normais em `float32`.

**Execução registrada (01/11/2026):** a bancada foi executada no wokwi.com e terminou com `BANCADA,fim,ok` e `resultado = APROVADO_FUNCIONAL`. O erro máximo foi de 1,1920929e-7, com features idênticas, 46 de 46 casos de entrada e 0 byte de variação do heap. Relatório completo e limitações em [`resultados/embarcado/mlp8-sint-20261101-e6a4cf00_wokwi.md`](../resultados/embarcado/mlp8-sint-20261101-e6a4cf00_wokwi.md).

## 5. Se algo der errado

| Sintoma | Causa provável |
|---|---|
| Erro de compilação `guardia_modelo.h: No such file` | Nome de arquivo diferente do exigido (passo 3) |
| `#error "Inclua guardia_modelo.h antes..."` | O `sketch.ino` não foi colado inteiro |
| Monitor serial vazio | Placa ou ligação do monitor serial incorretas no `diagram.json`; use o modelo ESP32-S3 do Wokwi |
| Nunca aparece `BANCADA,fim,ok` | Simulação ainda em andamento; aguarde |
| `REPROVADO` em algum critério | **Não ajuste nada.** Envie o log completo para análise |

## 6. Na placa física (fase D)

Use os mesmos arquivos, trocando a segunda linha do `sketch.ino` para `#define BANCADA_AMBIENTE "placa"`. Assim a latência é avaliada (< 1 ms, média e pior caso) e o `resultado` passa a ser `APROVADO` ou `REPROVADO`. Configuração do Arduino IDE em [`viabilidade_embarcada.md`](viabilidade_embarcada.md).
