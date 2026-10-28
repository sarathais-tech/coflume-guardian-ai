# ADR 0007: Features calculadas no runtime e `resultado_ultima` ternária

- **Status:** aceito
- **Data:** 2026-10-28

## Contexto
1. Se o firmware calculasse as features por conta própria, qualquer diferença em relação ao Python (por exemplo, no tratamento do tempo esgotado) degradaria o modelo sem gerar erro visível (*training-serving skew*).
2. A feature `acertou_ultima ∈ {0,1}` da Etapa 1 confundia "ainda não respondeu" com "errou".

## Decisão
1. O runtime fornece `guardia::montar_entrada(historico, ...)`. O firmware apenas registra respostas; o cálculo das features fica no código da Guardiã e é testado contra `guardia/features.py`.
2. A feature passa a ser `resultado_ultima ∈ {−1, 0, +1}`, com 0 para "sem histórico".

## Consequências
- Uma única especificação (`docs/features.md`) e duas implementações verificadas automaticamente.
- O firmware fica mais simples.
- A primeira questão (partida a frio) tem representação explícita e aparece nos dados de treino.
