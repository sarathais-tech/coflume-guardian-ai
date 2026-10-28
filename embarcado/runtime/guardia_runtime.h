// =============================================================================
//  guardia_runtime.h — Guardiã IA · Coflume — O Conhecimento Abre Portas
//
//  Runtime de inferência da MLP (float32) e cálculo das features.
//  Contrato de integração 1.0.0 (docs/contrato_integracao.md).
//
//  - Header-only, sem alocação dinâmica, sem estado global, sem acesso a hardware.
//  - Compila no ESP32-S3 (Arduino-ESP32 3.x) e no PC (g++ / clang++, C++17).
//  - NÃO EDITAR no repositório do firmware: mudanças passam pelo repositório
//    coflume-guardian-ai e pelos testes de equivalência.
//
//  Uso: inclua guardia_modelo.h ANTES deste arquivo.
// =============================================================================
#pragma once

#include <stdint.h>
#include <cmath>

#ifndef GUARDIA_MODELO_H_INCLUIDO
#error "Inclua guardia_modelo.h antes de guardia_runtime.h"
#endif

#define GUARDIA_CONTRATO_MAJOR 1
#define GUARDIA_CONTRATO_MINOR 0
#define GUARDIA_CONTRATO_PATCH 0
#define GUARDIA_CONTRATO_VERSAO "1.0.0"

static_assert(GUARDIA_MODELO_CONTRATO_MAJOR == GUARDIA_CONTRATO_MAJOR,
              "guardia_modelo.h foi exportado para outra versao MAJOR do contrato");

#define GUARDIA_HIST_MAX 16

namespace guardia {

constexpr int N_CATEGORIAS = 4;
constexpr int N_NIVEIS = 3;
constexpr int N_NUMERICAS = 9;
constexpr int N_ENTRADAS = N_NUMERICAS + N_CATEGORIAS;
constexpr int N_RESPONDIDAS_MAX = 8;
constexpr int SEQUENCIA_MAX = 3;
constexpr float FRIO_TAXA = 0.5f;
constexpr float FRIO_TEMPO = 0.5f;
constexpr float FRIO_DICAS = 0.0f;
constexpr float INVALIDO = -1.0f;

static_assert(GUARDIA_N_ENTRADAS == N_ENTRADAS, "Numero de entradas do modelo incompativel");

// Uma questão respondida. Nenhum dado pessoal.
struct Resposta {
  uint8_t categoria;      // 0..3
  uint8_t nivel;          // 0..2
  bool acertou;           // tempo esgotado conta como erro
  float tempo_gasto_s;    // >= 0
  float tempo_limite_s;   // > 0
  bool usou_dica;
};

struct Historico {
  Resposta itens[GUARDIA_HIST_MAX];
  uint8_t n;
};

// Features calculadas (ainda não padronizadas). Ver docs/features.md.
struct Entrada {
  uint8_t nivel_candidato;
  uint8_t nivel_inicial;
  uint8_t n_respondidas;
  uint8_t categoria;
  float taxa_acerto_sessao;
  float taxa_acerto_categoria;
  float tempo_medio_norm;
  float dicas_por_questao;
  int8_t resultado_ultima;  // -1 errou, 0 sem histórico, +1 acertou
  int8_t sequencia;         // -3..+3
};

inline void historico_limpar(Historico& h) { h.n = 0; }

// Retorna false se o histórico estiver cheio (não ocorre numa partida normal).
inline bool historico_adicionar(Historico& h, const Resposta& r) {
  if (h.n >= GUARDIA_HIST_MAX) return false;
  h.itens[h.n++] = r;
  return true;
}

namespace detail {

inline float razao_tempo(const Resposta& r) {
  if (!std::isfinite(r.tempo_gasto_s) || !std::isfinite(r.tempo_limite_s) || r.tempo_limite_s <= 0.0f) {
    return 1.0f;  // tratado como tempo esgotado
  }
  float razao = r.tempo_gasto_s / r.tempo_limite_s;
  if (razao < 0.0f) return 0.0f;
  if (razao > 1.0f) return 1.0f;
  return razao;
}

inline bool no_intervalo(float v, float lo, float hi) {
  return std::isfinite(v) && v >= lo && v <= hi;
}

inline float sigmoide(float z) {
  if (z >= 0.0f) return 1.0f / (1.0f + std::exp(-z));
  float e = std::exp(z);
  return e / (1.0f + e);
}

}  // namespace detail

// Calcula as features para avaliar uma questão candidata.
// Histórico vazio => valores neutros da partida a frio (docs/features.md, seção 4).
inline Entrada montar_entrada(const Historico& h, uint8_t nivel_inicial, uint8_t categoria,
                              uint8_t nivel_candidato) {
  const int n = h.n < GUARDIA_HIST_MAX ? h.n : GUARDIA_HIST_MAX;
  float acertos = 0.0f, acertos_cat = 0.0f, n_cat = 0.0f, soma_tempo = 0.0f, dicas = 0.0f;
  for (int i = 0; i < n; ++i) {
    const Resposta& r = h.itens[i];
    if (r.acertou) acertos += 1.0f;
    if (r.categoria == categoria) {
      n_cat += 1.0f;
      if (r.acertou) acertos_cat += 1.0f;
    }
    soma_tempo += detail::razao_tempo(r);
    if (r.usou_dica) dicas += 1.0f;
  }

  Entrada e;
  e.nivel_candidato = nivel_candidato;
  e.nivel_inicial = nivel_inicial;
  e.n_respondidas = static_cast<uint8_t>(n < N_RESPONDIDAS_MAX ? n : N_RESPONDIDAS_MAX);
  e.categoria = categoria;

  if (n > 0) {
    const float nf = static_cast<float>(n);
    e.taxa_acerto_sessao = acertos / nf;
    e.tempo_medio_norm = soma_tempo / nf;
    e.dicas_por_questao = dicas / nf;
    e.resultado_ultima = h.itens[n - 1].acertou ? 1 : -1;
  } else {
    e.taxa_acerto_sessao = FRIO_TAXA;
    e.tempo_medio_norm = FRIO_TEMPO;
    e.dicas_por_questao = FRIO_DICAS;
    e.resultado_ultima = 0;
  }
  e.taxa_acerto_categoria = n_cat > 0.0f ? acertos_cat / n_cat : e.taxa_acerto_sessao;

  int8_t seq = 0;
  if (n > 0) {
    const bool ultimo = h.itens[n - 1].acertou;
    int tamanho = 0;
    for (int i = n - 1; i >= 0 && tamanho < SEQUENCIA_MAX && h.itens[i].acertou == ultimo; --i) ++tamanho;
    seq = static_cast<int8_t>(ultimo ? tamanho : -tamanho);
  }
  e.sequencia = seq;
  return e;
}

inline bool entrada_valida(const Entrada& e) {
  return e.nivel_candidato < N_NIVEIS && e.nivel_inicial < N_NIVEIS && e.categoria < N_CATEGORIAS &&
         e.n_respondidas <= N_RESPONDIDAS_MAX &&
         detail::no_intervalo(e.taxa_acerto_sessao, 0.0f, 1.0f) &&
         detail::no_intervalo(e.taxa_acerto_categoria, 0.0f, 1.0f) &&
         detail::no_intervalo(e.tempo_medio_norm, 0.0f, 1.0f) &&
         detail::no_intervalo(e.dicas_por_questao, 0.0f, 1.0f) &&
         e.resultado_ultima >= -1 && e.resultado_ultima <= 1 &&
         e.sequencia >= -SEQUENCIA_MAX && e.sequencia <= SEQUENCIA_MAX;
}

// Vetor de 13 posições na ordem de docs/features.md (sem padronização).
inline void vetorizar(const Entrada& e, float x[N_ENTRADAS]) {
  x[0] = static_cast<float>(e.nivel_candidato);
  x[1] = static_cast<float>(e.nivel_inicial);
  x[2] = static_cast<float>(e.n_respondidas);
  x[3] = e.taxa_acerto_sessao;
  x[4] = e.taxa_acerto_categoria;
  x[5] = e.tempo_medio_norm;
  x[6] = e.dicas_por_questao;
  x[7] = static_cast<float>(e.resultado_ultima);
  x[8] = static_cast<float>(e.sequencia);
  for (int c = 0; c < N_CATEGORIAS; ++c) x[N_NUMERICAS + c] = (c == e.categoria) ? 1.0f : 0.0f;
}

// P(acerto) em [0, 1], ou INVALIDO se a entrada estiver fora da faixa.
inline float prever(const Entrada& e) {
  if (!entrada_valida(e)) return INVALIDO;

  float x[N_ENTRADAS];
  vetorizar(e, x);
  for (int i = 0; i < N_NUMERICAS; ++i) x[i] = (x[i] - GUARDIA_MEDIA[i]) / GUARDIA_DESVIO[i];

  float o1[GUARDIA_H1];
  for (int i = 0; i < GUARDIA_H1; ++i) {
    float s = GUARDIA_B_O1[i];
    for (int j = 0; j < N_ENTRADAS; ++j) s += GUARDIA_W_O1[i][j] * x[j];
    o1[i] = s > 0.0f ? s : 0.0f;
  }

#if GUARDIA_H2 > 0
  float o2[GUARDIA_H2];
  for (int i = 0; i < GUARDIA_H2; ++i) {
    float s = GUARDIA_B_O2[i];
    for (int j = 0; j < GUARDIA_H1; ++j) s += GUARDIA_W_O2[i][j] * o1[j];
    o2[i] = s > 0.0f ? s : 0.0f;
  }
  const float* ultima = o2;
  constexpr int n_ultima = GUARDIA_H2;
#else
  const float* ultima = o1;
  constexpr int n_ultima = GUARDIA_H1;
#endif

  float z = GUARDIA_B_SAIDA;
  for (int j = 0; j < n_ultima; ++j) z += GUARDIA_W_SAIDA[j] * ultima[j];

  float p = detail::sigmoide(z);
  if (!std::isfinite(p)) return INVALIDO;
  if (p < 0.0f) p = 0.0f;
  if (p > 1.0f) p = 1.0f;
  return p;
}

}  // namespace guardia
