# Adendo 01 ao protocolo de avaliação: conjunto de dados e divisão da v0.8

**Data:** 01/11/2026, **antes** de qualquer treino ou contato com o conjunto de teste.
**Protocolo original:** [`protocolo_avaliacao.md`](protocolo_avaliacao.md), registrado em 28/10/2026, **sem alterações**.

## O que muda

| | Protocolo original (seção 3, item 2) | Treino da v0.8 |
|---|---|---|
| Arquivo de divisão | `splits/split_v1.json` | **`splits/split_v2.json`** |
| Dados | (não especificados) → `sessoes_v1`, `sim-1.0` | **`sessoes_v2`, `sim-1.1`** |
| Participantes (treino / validação / teste) | 2.100 / 450 / 450 | **2.800 / 600 / 600** |

## Justificativa

1. O `sim-1.0` simulava uma partida que nem o firmware v0.7 nem a v0.8 produzem: reforço após erro, dificuldade livre e ganho de habilidade após erro.
2. O `sim-1.1` segue o [fluxo-0.8](fluxo_partida.md) (ADR 0009). Treinar com ele faz o modelo aprender exatamente as situações que o cofre vai consultar.
3. O `split_v2` é criado pelo **mesmo método** do protocolo: divisão por participante, 70 / 15 / 15, `GroupShuffleSplit`, semente 2026, sem vazamento e com o teste lacrado.
4. O `split_v1` e o `sessoes_v1` continuam no repositório como histórico e **não serão usados** para treinar ou avaliar os modelos da v0.8.

## O que não muda

Todos os critérios pré-registrados continuam valendo exatamente como estão em `protocolo_avaliacao.md`:

- modelos comparados e espaço de hiperparâmetros (seção 4);
- métricas, com log loss como principal (seção 5);
- regra de decisão entre MLP e árvore (seção 6);
- avaliação da política e o que o protocolo não permite afirmar (seções 7 e 8).

O conjunto de teste do `split_v2` nunca foi aberto. Este adendo foi registrado antes de qualquer treino.
