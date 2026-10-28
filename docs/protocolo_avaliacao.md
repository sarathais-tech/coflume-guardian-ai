# Protocolo de avaliação (pré-registrado)

**Registrado em:** 28/10/2026, **antes** de qualquer treino ou contato com o conjunto de teste.
Qualquer alteração depois desta data deve ser feita em um novo commit, com justificativa, e mencionada no relatório final.

## 1. Pergunta

A MLP estima a probabilidade de acerto melhor que a árvore de decisão e que o baseline ingênuo, em participantes que ela nunca viu?

## 2. Dados

- Toda linha tem a coluna `fonte ∈ {SINTETICO, REAL}`. As avaliações são feitas **separadamente** por fonte.
- Toda linha tem `participante_id`. No caso sintético é o índice do aluno simulado; no caso real é um identificador aleatório de sessão, sem relação com a pessoa.

## 3. Divisão sem vazamento

1. Divisão por participante (`GroupShuffleSplit`): **70% treino, 15% validação, 15% teste**, semente 2026.
2. O resultado é salvo em `splits/split_v1.json` e usado por **todos** os modelos.
3. A padronização das features é ajustada apenas no treino.
4. Hiperparâmetros são escolhidos com `GroupKFold` (5 folds) no treino, usando a validação para *early stopping*.
5. O **conjunto de teste é lacrado**: é avaliado uma única vez, ao final, com os modelos já escolhidos.

O teste automático `test_divisao_sem_vazamento` (a ser criado na etapa de treino) falha se qualquer `participante_id` aparecer em mais de um conjunto.

## 4. Modelos comparados

| Modelo | Busca de hiperparâmetros |
|---|---|
| Baseline ingênuo | Taxa de acerto por (`nivel_inicial`, `nivel_candidato`) no treino |
| Árvore de decisão | `max_depth ∈ {3,4,5,6}`, `min_samples_leaf ∈ {20,50,100}` |
| Regressão logística | `C ∈ {0.01, 0.1, 1, 10}` |
| MLP | camadas ocultas `∈ {[8], [16], [16,8], [32,16]}`; a menor arquitetura a até 1% da melhor log loss de validação é escolhida |

MLP: Adam (lr 1e-3), *binary cross-entropy*, batch 64, L2 1e-4, *early stopping* com paciência 20, máximo de 300 épocas, **5 sementes** (resultados como média ± desvio).

## 5. Métricas

| Métrica | Papel |
|---|---|
| **Log loss** | Principal |
| Brier score | Secundária |
| ROC-AUC | Secundária |
| ECE (10 faixas) + diagrama de confiabilidade | Calibração (obrigatória, porque a política usa o valor da probabilidade) |
| Erro absoluto médio contra a probabilidade verdadeira do simulador | **Somente para dados sintéticos** |

Comparação MLP × árvore: diferença de log loss com **intervalo de confiança de 95% por bootstrap sobre participantes** (2.000 reamostragens).

## 6. Regra de decisão

A MLP passa a ser o modelo padrão do firmware **somente se**:

1. a log loss da MLP for menor que a da árvore com o IC 95% da diferença sem cruzar zero, **ou** as duas forem estatisticamente empatadas e a MLP tiver ECE menor; **e**
2. a MLP passar nos critérios de [viabilidade embarcada](viabilidade_embarcada.md).

Caso contrário, a árvore é o padrão e a MLP é apresentada como experimento, e **o resultado negativo é reportado normalmente**.

## 7. Avaliação da política (simulação)

Com cada modelo no circuito, 1.000 partidas simuladas por modelo, medindo:
- taxa de desbloqueio e número médio de questões por partida;
- porcentagem de questões cuja probabilidade **real** (do simulador) ficou entre 0,50 e 0,85;
- número de repetições de questão (deve ser zero).

Esses números são sempre rotulados **[SINTÉTICO — simulação]**.

## 8. O que este protocolo não permite afirmar

- Que crianças aprendem mais com o Coflume.
- Que a MLP funcionaria igualmente bem com crianças reais, se avaliada só com dados sintéticos.
- Que o simulador representa fielmente o comportamento infantil.

Observação registrada antes dos resultados: se o simulador gerar acertos com uma fórmula logística, a regressão logística pode empatar com a MLP ou superá-la. O simulador **não** será ajustado para favorecer nenhum modelo.
