# ADR 0006: Divisão treino/validação/teste por participante

- **Status:** aceito
- **Data:** 2026-10-28

## Contexto
Cada participante gera várias linhas (uma por questão). Se linhas do mesmo participante caírem no treino e no teste, o modelo é avaliado em alguém que já conhece, e as métricas ficam otimistas.

## Decisão
Divisão por `participante_id` com `GroupShuffleSplit` (70/15/15, semente 2026), salva em `splits/split_v1.json` e compartilhada por todos os modelos. Hiperparâmetros com `GroupKFold`. Teste lacrado, avaliado uma única vez.

## Consequências
- Métricas representam o caso real: um participante novo diante do cofre.
- Um teste automático impede vazamento acidental.
