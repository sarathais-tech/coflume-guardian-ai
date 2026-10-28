// =============================================================================
//  bancada_ia.ino — Teste de viabilidade da Guardiã IA no ESP32-S3
//  Coflume — O Conhecimento Abre Portas
//
//  Sketch ISOLADO: não faz parte do firmware do cofre e não usa TFT, teclado,
//  servo nem LEDs. Só precisa da placa e do cabo USB.
//
//  Antes de compilar, gere os cabeçalhos:
//      python -m ferramentas.gerar_bancada --semente 2026
//
//  Placa: ESP32S3 Dev Module · Flash 16MB · PSRAM "OPI PSRAM" · CPU 240MHz
//  Monitor serial: 115200 baud. Copie toda a saída para um arquivo .txt e rode
//      python -m ferramentas.ler_bancada <arquivo.txt>
// =============================================================================
#include <Arduino.h>
#include <esp_timer.h>
#include <math.h>

#include "guardia_modelo.h"
#include "guardia_runtime.h"
#include "vetores_teste.h"

static const int N_REPETICOES = 10000;
static const int N_AMOSTRAS_PIOR_CASO = 1000;
static const float TOL_P = 1e-5f;        // contrato, seção 4, item 6
static const float LIMITE_LATENCIA_US = 1000.0f;

volatile float sumidouro = 0.0f;  // impede o compilador de descartar as chamadas

static guardia::Entrada entradas[GUARDIA_N_VETORES];

static void linha(const char* chave, const char* valor) { Serial.printf("BANCADA,%s,%s\n", chave, valor); }
static void linha(const char* chave, long valor) { Serial.printf("BANCADA,%s,%ld\n", chave, valor); }
static void linha(const char* chave, float valor) { Serial.printf("BANCADA,%s,%.9g\n", chave, (double)valor); }

static void montar_historico(const GuardiaVetorTeste& v, guardia::Historico& h) {
  guardia::historico_limpar(h);
  for (int i = 0; i < v.n_historico; ++i) guardia::historico_adicionar(h, v.historico[i]);
}

void setup() {
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 5000) delay(10);
  delay(1000);

  linha("inicio", "guardia_bancada_v1");
  linha("modelo_id", GUARDIA_MODELO_ID);
  linha("modelo_hash", GUARDIA_MODELO_HASH);
  linha("modelo_fonte", GUARDIA_MODELO_FONTE);
  linha("contrato", GUARDIA_CONTRATO_VERSAO);
  linha("n_parametros", (long)GUARDIA_MODELO_N_PARAMETROS);
  linha("chip", ESP.getChipModel());
  linha("cpu_mhz", (long)getCpuFrequencyMhz());
  linha("sketch_bytes", (long)ESP.getSketchSize());
  linha("psram_bytes", (long)ESP.getPsramSize());
  linha("pesos_bytes", (long)((GUARDIA_MODELO_N_PARAMETROS + 2 * guardia::N_NUMERICAS) * sizeof(float)));

  // ---- 1. Equivalência com o Python --------------------------------------
  const uint32_t heap_antes = ESP.getFreeHeap();
  float erro_p_max = 0.0f, erro_feat_max = 0.0f;
  long falhas_inteiras = 0, invalidos = 0;
  guardia::Historico h;

  for (int k = 0; k < GUARDIA_N_VETORES; ++k) {
    const GuardiaVetorTeste& v = GUARDIA_VETORES[k];
    montar_historico(v, h);
    const guardia::Entrada e = guardia::montar_entrada(h, v.nivel_inicial, v.categoria, v.nivel_candidato);
    entradas[k] = e;
    const guardia::Entrada& x = v.entrada_esperada;
    if (e.nivel_candidato != x.nivel_candidato || e.nivel_inicial != x.nivel_inicial ||
        e.n_respondidas != x.n_respondidas || e.categoria != x.categoria ||
        e.resultado_ultima != x.resultado_ultima || e.sequencia != x.sequencia) {
      ++falhas_inteiras;
    }
    const float d[4] = {fabsf(e.taxa_acerto_sessao - x.taxa_acerto_sessao),
                        fabsf(e.taxa_acerto_categoria - x.taxa_acerto_categoria),
                        fabsf(e.tempo_medio_norm - x.tempo_medio_norm),
                        fabsf(e.dicas_por_questao - x.dicas_por_questao)};
    for (float di : d) erro_feat_max = di > erro_feat_max ? di : erro_feat_max;

    const float p = guardia::prever(e);
    if (p == guardia::INVALIDO) ++invalidos;
    const float dp = fabsf(p - v.p_esperado);
    erro_p_max = dp > erro_p_max ? dp : erro_p_max;
  }
  linha("n_vetores", (long)GUARDIA_N_VETORES);
  linha("erro_p_max", erro_p_max);
  linha("erro_features_max", erro_feat_max);
  linha("falhas_inteiras", falhas_inteiras);
  linha("invalidos", invalidos);

  // ---- 2. Latência média de prever() --------------------------------------
  float acc = 0.0f;
  int64_t inicio = esp_timer_get_time();
  for (int i = 0; i < N_REPETICOES; ++i) acc += guardia::prever(entradas[i % GUARDIA_N_VETORES]);
  int64_t fim = esp_timer_get_time();
  sumidouro = acc;
  const float us_prever = (float)(fim - inicio) / N_REPETICOES;
  linha("latencia_prever_us_media", us_prever);

  // ---- 3. Decisão completa: 3 candidatos (montar_entrada + prever) --------
  acc = 0.0f;
  inicio = esp_timer_get_time();
  for (int i = 0; i < N_REPETICOES; ++i) {
    const GuardiaVetorTeste& v = GUARDIA_VETORES[i % GUARDIA_N_VETORES];
    montar_historico(v, h);
    for (uint8_t nivel = 0; nivel < 3; ++nivel)
      acc += guardia::prever(guardia::montar_entrada(h, v.nivel_inicial, v.categoria, nivel));
  }
  fim = esp_timer_get_time();
  sumidouro = acc;
  const float us_decisao = (float)(fim - inicio) / N_REPETICOES;
  linha("latencia_decisao_3_niveis_us_media", us_decisao);

  // ---- 4. Pior caso observado de prever() ---------------------------------
  int64_t pior = 0;
  for (int i = 0; i < N_AMOSTRAS_PIOR_CASO; ++i) {
    const int64_t a = esp_timer_get_time();
    sumidouro = guardia::prever(entradas[i % GUARDIA_N_VETORES]);
    const int64_t b = esp_timer_get_time();
    if (b - a > pior) pior = b - a;
  }
  linha("latencia_prever_us_pior", (long)pior);

  // ---- 5. Memória ----------------------------------------------------------
  const uint32_t heap_depois = ESP.getFreeHeap();
  linha("heap_livre_antes", (long)heap_antes);
  linha("heap_livre_depois", (long)heap_depois);
  linha("heap_consumido", (long)heap_antes - (long)heap_depois);

  // ---- 6. Veredito ---------------------------------------------------------
  const bool ok_equiv = erro_p_max < TOL_P && falhas_inteiras == 0 && invalidos == 0 && erro_feat_max <= 1e-6f;
  const bool ok_lat = us_prever < LIMITE_LATENCIA_US && (float)pior < LIMITE_LATENCIA_US;
  const bool ok_heap = heap_antes == heap_depois;
  linha("criterio_equivalencia", ok_equiv ? "APROVADO" : "REPROVADO");
  linha("criterio_latencia", ok_lat ? "APROVADO" : "REPROVADO");
  linha("criterio_sem_alocacao", ok_heap ? "APROVADO" : "REPROVADO");
  linha("resultado", (ok_equiv && ok_lat && ok_heap) ? "APROVADO" : "REPROVADO");
  linha("fim", "ok");
}

void loop() { delay(1000); }
