# [SINTÉTICO] Resumo do conjunto `sessoes_v2`

> Estatísticas descritivas de dados **gerados pelo simulador**. Não representam crianças reais e não comprovam eficácia educacional.

- **Versão do simulador:** sim-1.1 (fluxo da partida: fluxo-0.8)
- **Política de geração dos níveis:** exploratoria-uniforme (sorteio entre os níveis permitidos; **não** é a política adaptativa do cofre)
- **Semente:** 2026
- **SHA-256 do CSV:** `1146439e6096f9bf56cb7fdbcad865430d391864192571519cd8e8410d3688dd`
- **Ambiente:** Python 3.13.18, numpy 2.5.3

## Tamanho

| Medida | Valor |
|---|---|
| Participantes | 4000 |
| Linhas (questões respondidas) | 12000 |
| Questões por participante (mín. / média / máx.) | 3 / 3.00 / 3 |
| Questões principais / de reforço | 12000 / 0 |
| Linhas de partida a frio (1ª questão) | 4000 |

## Respostas

| Medida | Valor |
|---|---|
| Taxa de acerto observada | 62.7% |
| Média de `p_real` (probabilidade verdadeira) | 63.1% |
| Uso de dica | 28.8% |
| Tempo esgotado | 6.0% |
| Tempo gasto (mediana / p90), em s | 10.9 / 25.0 |

## Participantes por nível inicial

| Nível inicial | Participantes |
|---|---|
| Explorador | 1591 (39.8%) |
| Desafiante | 1416 (35.4%) |
| Mestre | 993 (24.8%) |

## Taxa de acerto observada por nível inicial × nível da questão

Entre parênteses: número de linhas.

| Nível inicial \ questão | Explorador | Desafiante | Mestre |
|---|---|---|---|
| Explorador | 70.4% (3199) | 49.0% (1574) | — |
| Desafiante | 77.5% (969) | 61.4% (2342) | 44.9% (937) |
| Mestre | — | 74.0% (1002) | 58.2% (1977) |

## Taxa de acerto por categoria

| Categoria | Acerto | Linhas |
|---|---|---|
| Matemática | 63.2% | 2999 |
| Português | 62.7% | 3062 |
| Lógica | 62.5% | 2976 |
| Conhecimentos gerais | 62.5% | 2963 |

## Nível sorteado por posição na partida

Distribuição gerada pela política **exploratória** de coleta. No cofre, a Guardiã escolherá o nível.

| Pergunta | Nível inicial | Explorador | Desafiante | Mestre |
|---|---|---|---|---|
| 1 | Explorador | 100.0% | — | — |
| 1 | Desafiante | — | 100.0% | — |
| 1 | Mestre | — | — | 100.0% |
| 2 | Explorador | 50.8% | 49.2% | — |
| 2 | Desafiante | 34.5% | 31.9% | 33.5% |
| 2 | Mestre | — | 51.3% | 48.7% |
| 3 | Explorador | 50.2% | 49.8% | — |
| 3 | Desafiante | 33.9% | 33.5% | 32.6% |
| 3 | Mestre | — | 49.6% | 50.4% |

## Partidas

| Medida | Valor |
|---|---|
| Categorias distintas nas 3 perguntas | 100.0% |
| Linhas com `taxa_acerto_categoria` = `taxa_acerto_sessao` | 100.0% |
| Partidas com ≥ 2 acertos sob a política exploratória | 67.3% |

> A taxa de partidas com 2 ou mais acertos acima vem do **sorteio** de níveis usado para gerar dados. Ela **não** é a taxa de desbloqueio esperada da v0.8 nem da v0.7; essas serão estimadas na simulação de políticas (protocolo, seção 7), também com dados sintéticos.

## Consistência do oráculo (`p_real` × acerto observado)

Se `p_real` é a probabilidade verdadeira, a taxa de acerto em cada faixa deve ficar próxima da média de `p_real`.

| Faixa de `p_real` | Linhas | Média de `p_real` | Acerto observado |
|---|---|---|---|
| 0.0–0.1 | 35 | 0.076 | 0.114 |
| 0.1–0.2 | 169 | 0.164 | 0.118 |
| 0.2–0.3 | 547 | 0.258 | 0.230 |
| 0.3–0.4 | 1047 | 0.355 | 0.363 |
| 0.4–0.5 | 1470 | 0.452 | 0.432 |
| 0.5–0.6 | 1858 | 0.551 | 0.553 |
| 0.6–0.7 | 1953 | 0.651 | 0.660 |
| 0.7–0.8 | 2026 | 0.750 | 0.742 |
| 0.8–0.9 | 1853 | 0.849 | 0.852 |
| 0.9–1.0 | 1042 | 0.936 | 0.921 |
