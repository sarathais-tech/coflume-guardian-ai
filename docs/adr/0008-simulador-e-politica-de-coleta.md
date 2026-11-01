# ADR 0008: Modelo do simulador e política de coleta exploratória

- **Status:** aceito; fluxo e faixa de níveis substituídos pelo [ADR 0009](0009-fluxo-v08-e-sim-1-1.md) (o modelo de resposta continua valendo)
- **Data:** 2026-11-01

## Contexto

O treino precisa de dados sintéticos enquanto não há piloto real. A especificação define as features e a primeira questão, mas não define:

1. qual modelo gera os acertos;
2. como o nível de cada questão é escolhido durante a coleta;
3. qual é o fluxo exato da partida.

## Opções avaliadas

### Modelo de resposta
1. **Logístico simples (TRI 1 ou 2 parâmetros).** Mais simples, mas ignora o chute com 4 alternativas, e a regressão logística teria a forma exata da verdade.
2. **TRI com 3 parâmetros (piso de acerto ao acaso).** Justificado pelas 4 alternativas do teclado; continua interpretável.
3. **Modelo não linear inventado** para favorecer a MLP. Rejeitado: viola o protocolo, seção 8.

### Política de coleta (nível das questões após a primeira)
1. **Imitar a política final (alvo de 70%).** Circular, porque precisa de um modelo já treinado, e só gera dados perto de 70%. O modelo não aprenderia o que acontece em níveis que a política evita (viés de seleção).
2. **Nível uniforme entre os 3.** Cobre todas as combinações de nível inicial e nível da questão, sem viés de seleção.
3. **Nível inicial ± 1.** Cobertura parcial: Exploradores nunca veriam Mestre.

### Fluxo da partida
1. **Fixo no código.**
2. **Parametrizado** (`n_principais`, regra de reforço, tempo limite), seguindo a Etapa 1.

## Decisão

- Modelo de resposta: **opção 2 (TRI 3PL)**, com dica, tempo log-normal, tempo esgotado como erro e ganho após feedback de erro.
- Política de coleta: **opção 2 (uniforme)**. Na primeira questão vale a regra de `features.md`, seção 4.
- Fluxo: **opção 2 (parametrizado)**, com os valores da Etapa 1.
- Registrar `p_real` (probabilidade verdadeira, antes de dica e tempo) para o erro contra a verdade previsto no protocolo.

## Consequências

- O modelo aprende sobre todas as combinações que a política do cofre pode consultar.
- A distribuição dos dados sintéticos difere da que o cofre vai produzir. Resultados reais devem ser reportados separadamente.
- O fluxo precisa ser conferido com o firmware v0.7 antes do treino definitivo.
- Qualquer mudança de parâmetro gera nova versão do simulador (`sim-1.x`), novo CSV e novo hash.
