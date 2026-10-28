# ADR 0002: Árvore de decisão como baseline e alternativa

- **Status:** aceito
- **Data:** 2026-10-28

## Contexto
Precisamos de uma referência de ML simples para saber se a MLP traz ganho real, e de uma alternativa caso a MLP falhe nos critérios.

## Decisão
A árvore de decisão (scikit-learn, profundidade 3 a 6) é treinada com os mesmos dados e a mesma divisão da MLP. Ela é o baseline de ML e o modelo padrão caso a MLP não cumpra o protocolo. Sua exportação para C++ entra na versão 1.1 do contrato.

## Consequências
- Comparação honesta entre os modelos.
- A árvore é interpretável e pode ser desenhada no pôster.
- O firmware terá dois caminhos de inferência compilados.
