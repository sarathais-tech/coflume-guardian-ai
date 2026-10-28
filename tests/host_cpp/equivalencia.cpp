// Teste de equivalência Python × C++ executado no PC.
// Recalcula features e previsões em C++ e compara com os valores do Python.
// Saída: linhas CHAVE=VALOR lidas por tests/test_equivalencia_cpp.py.
#include <cmath>
#include <cstdio>

#include "guardia_modelo.h"
#include "guardia_runtime.h"
#include "vetores_teste.h"

int main() {
  float erro_p_max = 0.0f, erro_feat_max = 0.0f;
  int falhas_inteiras = 0, invalidos = 0;

  for (int k = 0; k < GUARDIA_N_VETORES; ++k) {
    const GuardiaVetorTeste& v = GUARDIA_VETORES[k];
    guardia::Historico h;
    guardia::historico_limpar(h);
    for (int i = 0; i < v.n_historico; ++i) guardia::historico_adicionar(h, v.historico[i]);

    guardia::Entrada e = guardia::montar_entrada(h, v.nivel_inicial, v.categoria, v.nivel_candidato);
    const guardia::Entrada& x = v.entrada_esperada;

    if (e.nivel_candidato != x.nivel_candidato || e.nivel_inicial != x.nivel_inicial ||
        e.n_respondidas != x.n_respondidas || e.categoria != x.categoria ||
        e.resultado_ultima != x.resultado_ultima || e.sequencia != x.sequencia) {
      ++falhas_inteiras;
      std::printf("DIVERGENCIA_INTEIRA=%d\n", k);
    }
    const float d[4] = {
        std::fabs(e.taxa_acerto_sessao - x.taxa_acerto_sessao),
        std::fabs(e.taxa_acerto_categoria - x.taxa_acerto_categoria),
        std::fabs(e.tempo_medio_norm - x.tempo_medio_norm),
        std::fabs(e.dicas_por_questao - x.dicas_por_questao),
    };
    for (float di : d) erro_feat_max = di > erro_feat_max ? di : erro_feat_max;

    const float p = guardia::prever(e);
    if (p == guardia::INVALIDO) ++invalidos;
    const float dp = std::fabs(p - v.p_esperado);
    erro_p_max = dp > erro_p_max ? dp : erro_p_max;
  }

  std::printf("MODELO=%s\n", GUARDIA_MODELO_ID);
  std::printf("N=%d\n", GUARDIA_N_VETORES);
  std::printf("ERRO_P_MAX=%.9g\n", erro_p_max);
  std::printf("ERRO_FEATURES_MAX=%.9g\n", erro_feat_max);
  std::printf("FALHAS_INTEIRAS=%d\n", falhas_inteiras);
  std::printf("INVALIDOS=%d\n", invalidos);
  return 0;
}
