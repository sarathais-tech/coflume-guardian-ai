# ADR 0009: fluxo-0.8 e simulador sim-1.1

- **Status:** aceito pela equipe em 01/11/2026 (implementação aguardando revisão)
- **Data:** 2026-11-01
- **Substitui parcialmente:** ADR 0008, na parte de fluxo e faixa de níveis; o modelo de resposta continua o mesmo

## Contexto

A revisão do firmware v0.7 mostrou diferenças em relação ao `sim-1.0`:

| v0.7 | sim-1.0 |
|---|---|
| Exatamente 3 perguntas | 3 principais + até 3 reforços |
| Dificuldade fixa no nível escolhido | Dificuldade livre |
| Erro: mostra a resposta correta e avança | Erro: gera reforço e ganho de +0,3 |
| Dica com `*` | Dica simulada |
| Desbloqueio com ≥ 2 acertos em 3 | (não simulado) |

Com dificuldade fixa, a previsão da Guardiã não altera nada na partida. Os dados do `sim-1.0` também descrevem partidas que nem a v0.7 nem a v0.8 produzem.

## Decisões

1. **Dificuldade adaptativa nas perguntas 2 e 3**, dentro da faixa nível inicial ± 1. Essa é a única mudança essencial para a IA ter papel real.
2. **Pergunta 1 no nível escolhido pela criança.** A escolha é respeitada; a previsão de partida a frio é só registrada.
3. **Sem reforço** na v0.8. A partida continua curta (no máximo cerca de 2 min) e a regra de 2 em 3 continua igual. O reforço fica como candidato para depois da feira.
4. **Sem ganho de habilidade após erro** no cenário principal (`ganho = 0`). O ganho de +0,3 era uma suposição para dar sentido ao reforço. O parâmetro continua disponível para análise de sensibilidade.
5. **Dicas mantidas** no simulador e na v0.8.
6. **Categorias distintas sorteadas pelo jogo**; a IA escolhe só o nível.
7. **Política de coleta exploratória** (sorteio uniforme) restrita aos **mesmos níveis permitidos** no cofre (`politica.niveis_permitidos`). A política adaptativa (alvo de 0,70) **não** é usada para gerar dados de treino, porque isso seria circular e criaria viés de seleção.
8. **Tolerância de empate de 1e-6** na escolha do nível, para que arredondamentos de ponto flutuante não decidam a escolha.
9. **Contrato de integração 1.0.0 inalterado**: as features e a API continuam as mesmas.
10. **Célula vazia no banco** (revisão 2 do fluxo): a Guardiã avalia só os níveis disponíveis (permitidos e com pergunta). Se a categoria não tiver nenhum, usa-se a próxima categoria não usada. O nível nunca sai da faixa, e a previsão registrada é sempre a do nível apresentado. Um banco que não sustente todas as partidas é recusado antes da feira por `ferramentas.validar_banco`.
11. **Dados e divisão do treino da v0.8:** `sessoes_v2` e `split_v2`, registrados no [adendo 01 ao protocolo](../protocolo_adendo_01.md), sem mudança nos critérios de avaliação.

## Consequências

- Novo conjunto `sessoes_v2` (4.000 participantes, 12.000 linhas) e `split_v2` (2.800 / 600 / 600). Os `sessoes_v1` e `split_v1` são mantidos como histórico, e o `sim-1.0` continua reproduzível byte a byte com o mesmo NumPy.
- `taxa_acerto_categoria` = `taxa_acerto_sessao` em 100% das linhas (redundância documentada em `fluxo_partida.md`, seção 4).
- O modelo nunca vê combinações fora da faixa (Explorador × Mestre e Mestre × Explorador), e o cofre também nunca as consulta.
- O firmware v0.8 precisa de um banco por nível e categoria (`banco_questoes.md`).
- Os dados continuam sintéticos. Nada aqui valida a Guardiã com crianças reais.
