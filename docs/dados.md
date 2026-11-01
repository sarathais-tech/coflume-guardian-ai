# Dados: sintéticos × reais

## Regra geral

Dados sintéticos e reais **nunca** são misturados sem rótulo, e seus resultados ficam em pastas, tabelas e gráficos separados.

| | Sintéticos | Reais |
|---|---|---|
| Origem | `simulador.py`, com semente fixa | Logs do piloto, exportados pela Serial do cofre |
| Coluna `fonte` | `SINTETICO` | `REAL` |
| Pasta de dados | `dados/sinteticos/` (não versionada, regenerável) | `dados/reais/` (**nunca** versionada) |
| Pasta de resultados | `resultados/sinteticos/` | `resultados/reais/` |
| Prefixo em títulos de tabelas e gráficos | `[SINTÉTICO]` | `[REAL, n = <sessões>]` |
| Prefixo do id do modelo | `sint` | `real` |
| O que permite afirmar | O pipeline funciona; comparação de modelos em ambiente controlado | Desempenho preditivo numa amostra pequena e específica |
| O que **não** permite afirmar | Eficácia educacional; desempenho com crianças reais | Eficácia educacional (amostra pequena, sem grupo de controle) |

Nos dados sintéticos, os níveis são gerados pela **política exploratória** (sorteio). Nos dados reais do cofre v0.8, eles serão escolhidos pela **política adaptativa** da Guardiã. As duas distribuições são diferentes e nunca devem ser comparadas sem essa ressalva (ver [`fluxo_partida.md`](fluxo_partida.md), seção 3).

Um modelo treinado com dados misturados recebe o prefixo `misto` e deve ser avaliado **separadamente** em teste sintético e em teste real.

## Dados reais: condições

1. Participação somente com autorização dos responsáveis, no caso de menores.
2. Nenhum dado pessoal: sem nome, idade, foto, escola ou texto livre.
3. `participante_id` é um número aleatório gerado pelo cofre no início da sessão, sem relação com a pessoa.
4. Os arquivos ficam apenas nos computadores da equipe e não entram no Git.
5. Publicar dados reais, mesmo anonimizados, exige decisão explícita da equipe e autorização de quem participou.

## Esquema de uma linha

Uma linha corresponde a uma questão respondida. As colunas aparecem nesta ordem, que é verificada por `guardia.dados.carregar`.

| Coluna | Tipo | Uso no treino |
|---|---|---|
| `fonte` | `SINTETICO` \| `REAL` | — |
| `versao_simulador` | texto (ex.: `sim-1.0`); vazio em dados reais | — |
| `participante_id` | inteiro; grupo da divisão treino/validação/teste | grupo |
| `ordem` | inteiro, posição da questão na sessão (0 = primeira) | **proibido** |
| `tipo` | `principal` \| `reforco` | **proibido** |
| `nivel_inicial`, `categoria`, `nivel_candidato`, `n_respondidas`, `taxa_acerto_sessao`, `taxa_acerto_categoria`, `tempo_medio_norm`, `dicas_por_questao`, `resultado_ultima`, `sequencia` | as 9 features e a categoria, calculadas com o histórico **anterior** à questão (ver [features.md](features.md)) | **features** |
| `acertou` | 0 \| 1; tempo esgotado conta como 0 | **rótulo** |
| `resp_usou_dica`, `resp_tempo_gasto_s`, `resp_tempo_limite_s`, `resp_esgotou` | registro bruto da resposta **desta** questão | **proibido** (vazamento) |
| `p_real` | real, **somente sintético**: probabilidade verdadeira do simulador; vazio em dados reais | **proibido** (oráculo) |

As colunas `resp_*` existem para reconstruir o histórico e verificar que as features foram calculadas corretamente. Como descrevem a própria resposta que se quer prever, usá-las como entrada seria vazamento. `guardia.dados.matriz()` só usa as colunas marcadas como features.

## Divisão treino/validação/teste

Implementada em `guardia/dados.py`, conforme o [protocolo](protocolo_avaliacao.md), seção 3:

- A divisão é por `participante_id`: 70% / 15% / 15% dos **participantes**, semente 2026.
- Como o `GroupShuffleSplit` faz uma divisão por vez, ela é feita em duas etapas: primeiro o teste, depois a validação dentro do restante. Os tamanhos são inteiros (2.100 / 450 / 450 para 3.000 participantes).
- O resultado fica versionado em `splits/`, com o SHA-256 dos IDs e do CSV:
  - `split_v2.json` → `sessoes_v2` (`sim-1.1`, fluxo-0.8): 2.800 / 600 / 600. **Atual.**
  - `split_v1.json` → `sessoes_v1` (`sim-1.0`): 2.100 / 450 / 450. Histórico.
- O teste é lacrado: `conjunto(df, split, "teste")` lança `ConjuntoLacradoError` sem `abrir_teste=True`.
- O split só se aplica a dados com exatamente os mesmos participantes e a mesma fonte.
