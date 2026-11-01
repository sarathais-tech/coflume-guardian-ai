// =============================================================================
//  bancada_ia.ino — Teste de viabilidade da Guardiã IA no ESP32-S3 (v2)
//  Coflume — O Conhecimento Abre Portas
//
//  Sketch ISOLADO: não faz parte do firmware do cofre e não usa TFT, teclado,
//  servo nem LEDs. Não altera a v0.7.
//
//  Cabeçalhos necessários na mesma pasta:
//      guardia_modelo.h  guardia_runtime.h  vetores_teste.h
//  Gerados por:
//      python -m ferramentas.gerar_bancada --semente 2026          (pesos ALEATÓRIOS)
//      python -m ferramentas.exportar_bancada ...                  (MLP treinada; ver docs/bancada_wokwi.md)
//
//  Ambiente: defina BANCADA_AMBIENTE como "wokwi" ou "placa" antes dos includes.
//  No Wokwi a CPU é simulada mais devagar: a latência é registrada só como
//  indicação e NÃO entra no veredito. A latência vale apenas na placa física.
//
//  Monitor serial: 115200 baud. Leia o log com
//      python -m ferramentas.ler_bancada <arquivo.txt>
// =============================================================================
#ifndef BANCADA_AMBIENTE
#define BANCADA_AMBIENTE "placa"
#endif

#include <Arduino.h>
#include <esp_timer.h>
#include <math.h>
#include <string.h>

#include "guardia_modelo.h"
#include "guardia_runtime.h"
#include "vetores_teste.h"

#ifndef GUARDIA_N_VETORES_ALEATORIOS
#define GUARDIA_N_VETORES_ALEATORIOS GUARDIA_N_VETORES
#endif
#ifndef GUARDIA_MODELO_USO
#define GUARDIA_MODELO_USO "bancada"
#endif

static const int N_REPETICOES = 10000;
static const int N_AMOSTRAS_PIOR_CASO = 1000;
static const float TOL_P = 1e-5f;  // contrato, seção 4, item 6
static const float TOL_FEATURES = 1e-6f;
static const float LIMITE_LATENCIA_US = 1000.0f;

volatile float sumidouro = 0.0f;  // impede o compilador de descartar as chamadas

// Tipos usados nas funções abaixo vêm ANTES da primeira função: o Arduino gera
// protótipos automáticos e os insere antes da primeira definição de função.
struct Grupo {
  float erro_p_max = 0.0f;
  float erro_feat_max = 0.0f;
  long falhas_inteiras = 0;
  long invalidos = 0;
  long n = 0;
};

static guardia::Entrada entradas[GUARDIA_N_VETORES];

static void linha(const char* chave, const char* valor) { Serial.printf("BANCADA,%s,%s\n", chave, valor); }
static void linha(const char* chave, long valor) { Serial.printf("BANCADA,%s,%ld\n", chave, valor); }
static void linha(const char* chave, float valor) { Serial.printf("BANCADA,%s,%.9g\n", chave, (double)valor); }

static void montar_historico(const GuardiaVetorTeste& v, guardia::Historico& h) {
  guardia::historico_limpar(h);
  for (int i = 0; i < v.n_historico; ++i) guardia::historico_adicionar(h, v.historico[i]);
}

static bool equivalencia(int ini, int fim, Grupo& g) {
  guardia::Historico h;
  for (int k = ini; k < fim; ++k) {
    const GuardiaVetorTeste& v = GUARDIA_VETORES[k];
    montar_historico(v, h);
    const guardia::Entrada e = guardia::montar_entrada(h, v.nivel_inicial, v.categoria, v.nivel_candidato);
    entradas[k] = e;
    const guardia::Entrada& x = v.entrada_esperada;
    if (e.nivel_candidato != x.nivel_candidato || e.nivel_inicial != x.nivel_inicial ||
        e.n_respondidas != x.n_respondidas || e.categoria != x.categoria ||
        e.resultado_ultima != x.resultado_ultima || e.sequencia != x.sequencia) {
      ++g.falhas_inteiras;
    }
    const float d[4] = {fabsf(e.taxa_acerto_sessao - x.taxa_acerto_sessao),
                        fabsf(e.taxa_acerto_categoria - x.taxa_acerto_categoria),
                        fabsf(e.tempo_medio_norm - x.tempo_medio_norm),
                        fabsf(e.dicas_por_questao - x.dicas_por_questao)};
    for (float di : d) g.erro_feat_max = di > g.erro_feat_max ? di : g.erro_feat_max;
    const float p = guardia::prever(e);
    if (p == guardia::INVALIDO) ++g.invalidos;
    const float dp = fabsf(p - v.p_esperado);
    g.erro_p_max = dp > g.erro_p_max ? dp : g.erro_p_max;
    ++g.n;
  }
  return g.erro_p_max < TOL_P && g.erro_feat_max <= TOL_FEATURES && g.falhas_inteiras == 0 && g.invalidos == 0;
}

// Entradas fora da faixa devem retornar INVALIDO (contrato, seção 4, item 2).
static long casos_invalidos(long& total) {
  guardia::Historico h;
  guardia::historico_limpar(h);
  const guardia::Entrada base = guardia::montar_entrada(h, 1, 0, 1);
  guardia::Entrada c[10];
  for (int i = 0; i < 10; ++i) c[i] = base;
  c[0].nivel_candidato = 3;
  c[1].nivel_inicial = 7;
  c[2].categoria = 4;
  c[3].n_respondidas = 9;
  c[4].taxa_acerto_sessao = 1.5f;
  c[5].taxa_acerto_categoria = NAN;
  c[6].tempo_medio_norm = -0.1f;
  c[7].dicas_por_questao = 2.0f;
  c[8].resultado_ultima = 2;
  c[9].sequencia = -4;
  long ok = 0;
  total = 10;
  for (int i = 0; i < 10; ++i) ok += guardia::prever(c[i]) == guardia::INVALIDO ? 1 : 0;
  // Partida a frio válida: probabilidade em [0, 1] para os 36 candidatos.
  for (uint8_t ini = 0; ini < 3; ++ini)
    for (uint8_t cat = 0; cat < 4; ++cat)
      for (uint8_t niv = 0; niv < 3; ++niv) {
        const float p = guardia::prever(guardia::montar_entrada(h, ini, cat, niv));
        ++total;
        ok += (p >= 0.0f && p <= 1.0f) ? 1 : 0;
      }
  return ok;
}

void setup() {
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 5000) delay(10);
  delay(1000);
  const bool na_placa = strcmp(BANCADA_AMBIENTE, "placa") == 0;

  linha("inicio", "guardia_bancada_v2");
  linha("ambiente", BANCADA_AMBIENTE);
  linha("modelo_id", GUARDIA_MODELO_ID);
  linha("modelo_hash", GUARDIA_MODELO_HASH);
  linha("modelo_fonte", GUARDIA_MODELO_FONTE);
  linha("modelo_uso", GUARDIA_MODELO_USO);
  linha("contrato", GUARDIA_CONTRATO_VERSAO);
  linha("n_parametros", (long)GUARDIA_MODELO_N_PARAMETROS);
  linha("camadas_ocultas", (long)(GUARDIA_H2 > 0 ? 2 : 1));
  linha("chip", ESP.getChipModel());
  linha("cpu_mhz_configurada", (long)getCpuFrequencyMhz());
  linha("sketch_bytes", (long)ESP.getSketchSize());
  linha("pesos_bytes", (long)((GUARDIA_MODELO_N_PARAMETROS + 2 * guardia::N_NUMERICAS) * sizeof(float)));

  // ---- 1. Equivalência com o Python, por grupo de vetores -----------------
  Grupo aleatorios, validacao;
  const bool eq_a = equivalencia(0, GUARDIA_N_VETORES_ALEATORIOS, aleatorios);
  const bool eq_v = equivalencia(GUARDIA_N_VETORES_ALEATORIOS, GUARDIA_N_VETORES, validacao);
  linha("n_vetores", (long)GUARDIA_N_VETORES);
  linha("n_vetores_aleatorios", aleatorios.n);
  linha("n_vetores_validacao", validacao.n);
  linha("erro_p_max_aleatorios", aleatorios.erro_p_max);
  linha("erro_p_max_validacao", validacao.erro_p_max);
  linha("erro_p_max", aleatorios.erro_p_max > validacao.erro_p_max ? aleatorios.erro_p_max : validacao.erro_p_max);
  linha("erro_features_max",
        aleatorios.erro_feat_max > validacao.erro_feat_max ? aleatorios.erro_feat_max : validacao.erro_feat_max);
  linha("falhas_inteiras", aleatorios.falhas_inteiras + validacao.falhas_inteiras);
  linha("invalidos", aleatorios.invalidos + validacao.invalidos);

  // ---- 2. Entradas inválidas e partida a frio ------------------------------
  long casos = 0;
  const long casos_ok = casos_invalidos(casos);
  linha("casos_entrada_testados", casos);
  linha("casos_entrada_corretos", casos_ok);

  // ---- 3. Alocação dinâmica DENTRO de prever() e montar_entrada() ----------
  // Mede o heap livre imediatamente antes e depois de laços que só chamam as
  // funções da Guardiã. Não é o consumo total do firmware (informado à parte).
  guardia::Historico h;
  const uint32_t heap_a = ESP.getFreeHeap();
  float acc = 0.0f;
  for (int i = 0; i < N_REPETICOES; ++i) acc += guardia::prever(entradas[i % GUARDIA_N_VETORES]);
  const uint32_t heap_b = ESP.getFreeHeap();
  for (int i = 0; i < N_REPETICOES; ++i) {
    const GuardiaVetorTeste& v = GUARDIA_VETORES[i % GUARDIA_N_VETORES];
    montar_historico(v, h);
    acc += guardia::montar_entrada(h, v.nivel_inicial, v.categoria, v.nivel_candidato).taxa_acerto_sessao;
  }
  const uint32_t heap_c = ESP.getFreeHeap();
  sumidouro = acc;
  linha("heap_variacao_prever_bytes", (long)heap_a - (long)heap_b);
  linha("heap_variacao_montar_entrada_bytes", (long)heap_b - (long)heap_c);
  linha("heap_livre_total_informativo", (long)heap_c);
  linha("heap_minimo_livre_informativo", (long)ESP.getMinFreeHeap());

  // ---- 4. Latência (válida só na placa física) -----------------------------
  acc = 0.0f;
  int64_t inicio = esp_timer_get_time();
  for (int i = 0; i < N_REPETICOES; ++i) acc += guardia::prever(entradas[i % GUARDIA_N_VETORES]);
  int64_t fim = esp_timer_get_time();
  sumidouro = acc;
  const float us_prever = (float)(fim - inicio) / N_REPETICOES;

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

  int64_t pior = 0;
  for (int i = 0; i < N_AMOSTRAS_PIOR_CASO; ++i) {
    const int64_t a = esp_timer_get_time();
    sumidouro = guardia::prever(entradas[i % GUARDIA_N_VETORES]);
    const int64_t b = esp_timer_get_time();
    if (b - a > pior) pior = b - a;
  }
  linha("latencia_prever_us_media", us_prever);
  linha("latencia_decisao_3_niveis_us_media", us_decisao);
  linha("latencia_prever_us_pior", (long)pior);
  linha("latencia_valida", na_placa ? "sim" : "nao (CPU simulada; apenas indicativa)");

  // ---- 5. Veredito ---------------------------------------------------------
  const bool ok_equiv = eq_a && eq_v;
  const bool ok_entradas = casos_ok == casos;
  const bool ok_alocacao = heap_a == heap_b && heap_b == heap_c;
  const bool ok_funcional = ok_equiv && ok_entradas && ok_alocacao;
  linha("criterio_equivalencia", ok_equiv ? "APROVADO" : "REPROVADO");
  linha("criterio_entradas", ok_entradas ? "APROVADO" : "REPROVADO");
  linha("criterio_sem_alocacao", ok_alocacao ? "APROVADO" : "REPROVADO");
  linha("resultado_funcional", ok_funcional ? "APROVADO" : "REPROVADO");
  if (na_placa) {
    const bool ok_lat = us_prever < LIMITE_LATENCIA_US && (float)pior < LIMITE_LATENCIA_US;
    linha("criterio_latencia", ok_lat ? "APROVADO" : "REPROVADO");
    linha("resultado", (ok_funcional && ok_lat) ? "APROVADO" : "REPROVADO");
  } else {
    linha("criterio_latencia", "NAO_AVALIADO");
    linha("resultado", ok_funcional ? "APROVADO_FUNCIONAL" : "REPROVADO");
  }
  linha("fim", "ok");
}

void loop() { delay(1000); }
