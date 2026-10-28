// Verifica as garantias do contrato para entradas inválidas e a partida a frio.
#include <cmath>
#include <cstdio>
#include <limits>

#include "guardia_modelo.h"
#include "guardia_runtime.h"

static int falhas = 0;
#define CONFERE(cond)                                         \
  do {                                                        \
    if (!(cond)) {                                            \
      std::printf("FALHOU: %s (linha %d)\n", #cond, __LINE__); \
      ++falhas;                                               \
    }                                                         \
  } while (0)

int main() {
  guardia::Historico h;
  guardia::historico_limpar(h);

  // Partida a frio: valores neutros e previsão válida para todos os candidatos.
  for (uint8_t ini = 0; ini < 3; ++ini)
    for (uint8_t cat = 0; cat < 4; ++cat)
      for (uint8_t niv = 0; niv < 3; ++niv) {
        guardia::Entrada e = guardia::montar_entrada(h, ini, cat, niv);
        CONFERE(e.n_respondidas == 0);
        CONFERE(e.taxa_acerto_sessao == 0.5f);
        CONFERE(e.taxa_acerto_categoria == 0.5f);
        CONFERE(e.tempo_medio_norm == 0.5f);
        CONFERE(e.dicas_por_questao == 0.0f);
        CONFERE(e.resultado_ultima == 0);
        CONFERE(e.sequencia == 0);
        float p = guardia::prever(e);
        CONFERE(p >= 0.0f && p <= 1.0f);
      }

  guardia::Entrada base = guardia::montar_entrada(h, 1, 0, 1);
  const float nan = std::numeric_limits<float>::quiet_NaN();

  guardia::Entrada e = base; e.nivel_candidato = 3;        CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.nivel_inicial = 7;                           CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.categoria = 4;                               CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.n_respondidas = 9;                           CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.taxa_acerto_sessao = 1.5f;                   CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.taxa_acerto_categoria = nan;                 CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.tempo_medio_norm = -0.1f;                    CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.dicas_por_questao = 2.0f;                    CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.resultado_ultima = 2;                        CONFERE(guardia::prever(e) == guardia::INVALIDO);
  e = base; e.sequencia = -4;                              CONFERE(guardia::prever(e) == guardia::INVALIDO);

  // Histórico cheio não estoura o buffer.
  guardia::Resposta r{0, 0, true, 5.0f, 30.0f, false};
  for (int i = 0; i < GUARDIA_HIST_MAX; ++i) CONFERE(guardia::historico_adicionar(h, r));
  CONFERE(!guardia::historico_adicionar(h, r));
  e = guardia::montar_entrada(h, 0, 0, 0);
  CONFERE(e.n_respondidas == 8);
  CONFERE(e.sequencia == 3);

  // Tempo com limite inválido conta como esgotado (razão 1).
  guardia::historico_limpar(h);
  guardia::Resposta r2{1, 1, false, 10.0f, 0.0f, true};
  guardia::historico_adicionar(h, r2);
  e = guardia::montar_entrada(h, 1, 1, 1);
  CONFERE(e.tempo_medio_norm == 1.0f);
  CONFERE(e.resultado_ultima == -1);
  CONFERE(e.sequencia == -1);
  CONFERE(e.dicas_por_questao == 1.0f);

  std::printf("FALHAS=%d\n", falhas);
  return 0;
}
