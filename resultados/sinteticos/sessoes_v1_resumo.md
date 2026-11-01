# [SINTÉTICO] Resumo do conjunto `sessoes_v1`

> Estatísticas descritivas de dados **gerados pelo simulador**. Não representam crianças reais e não comprovam eficácia educacional.

- **Versão do simulador:** sim-1.0
- **Semente:** 2026
- **SHA-256 do CSV:** `af270466b1b6696e7f2777c91502c9806dc438e634889648ce44959f510b5e00`
- **Ambiente:** Python 3.13.18, numpy 2.5.3

## Tamanho

| Medida | Valor |
|---|---|
| Participantes | 3000 |
| Linhas (questões respondidas) | 12248 |
| Questões por participante (mín. / média / máx.) | 3 / 4.08 / 6 |
| Questões principais / de reforço | 9000 / 3248 |
| Linhas de partida a frio (1ª questão) | 3000 |

## Respostas

| Medida | Valor |
|---|---|
| Taxa de acerto observada | 63.7% |
| Média de `p_real` (probabilidade verdadeira) | 63.6% |
| Uso de dica | 28.5% |
| Tempo esgotado | 6.8% |
| Tempo gasto (mediana / p90), em s | 10.8 / 25.8 |

## Participantes por nível inicial

| Nível inicial | Participantes |
|---|---|
| Explorador | 1184 (39.5%) |
| Desafiante | 1053 (35.1%) |
| Mestre | 763 (25.4%) |

## Taxa de acerto observada por nível inicial × nível da questão

Entre parênteses: número de linhas.

| Nível inicial \ questão | Explorador | Desafiante | Mestre |
|---|---|---|---|
| Explorador | 69.2% (2785) | 51.2% (1229) | 33.9% (1037) |
| Desafiante | 78.1% (1708) | 63.9% (1663) | 43.6% (876) |
| Mestre | 88.2% (702) | 74.7% (1208) | 56.7% (1040) |

## Taxa de acerto por categoria

| Categoria | Acerto | Linhas |
|---|---|---|
| Matemática | 64.2% | 3062 |
| Português | 62.8% | 3109 |
| Lógica | 64.0% | 3029 |
| Conhecimentos gerais | 63.6% | 3048 |

## Consistência do oráculo (`p_real` × acerto observado)

Se `p_real` é a probabilidade verdadeira, a taxa de acerto em cada faixa deve ficar próxima da média de `p_real`.

| Faixa de `p_real` | Linhas | Média de `p_real` | Acerto observado |
|---|---|---|---|
| 0.0–0.1 | 62 | 0.077 | 0.081 |
| 0.1–0.2 | 304 | 0.159 | 0.105 |
| 0.2–0.3 | 666 | 0.255 | 0.240 |
| 0.3–0.4 | 1050 | 0.352 | 0.355 |
| 0.4–0.5 | 1340 | 0.452 | 0.451 |
| 0.5–0.6 | 1648 | 0.550 | 0.558 |
| 0.6–0.7 | 1739 | 0.650 | 0.639 |
| 0.7–0.8 | 1982 | 0.751 | 0.764 |
| 0.8–0.9 | 2014 | 0.852 | 0.857 |
| 0.9–1.0 | 1443 | 0.941 | 0.933 |
