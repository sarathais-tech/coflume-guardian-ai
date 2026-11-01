# Adendo 02 ao protocolo de avaliação: procedimento do teste final da v0.8

**Data:** 01/11/2026, **antes** de qualquer abertura do conjunto de teste.
**Protocolo original:** [`protocolo_avaliacao.md`](protocolo_avaliacao.md), **sem alterações**. **Adendo anterior:** [adendo 01](protocolo_adendo_01.md).
**Situação:** fase A aprovada pela equipe; o teste (fase C) só será aberto depois de nova aprovação.

Este adendo **não muda nenhum critério**. Ele fixa, antes de ver o teste, **quais modelos** serão avaliados e **como** a regra da seção 6 será aplicada, para que nada seja escolhido depois de olhar o resultado.

## 1. Modelos congelados

Origem: execução 41329660286 do CI ([`ORIGEM.json`](../resultados/sinteticos/treino_v2/ORIGEM.json)).

| Modelo | Configuração congelada | Como é obtido na fase C |
|---|---|---|
| Baseline ingênuo | Taxa por (`nivel_inicial`, `nivel_candidato`) no treino | Ajuste no treino (determinístico) |
| Árvore de decisão | `max_depth = 6`, `min_samples_leaf = 100`, `random_state = 2026` | Ajuste no treino (determinístico) |
| Regressão logística | `C = 0,1`, padronização ajustada no treino | Ajuste no treino (determinístico) |
| **MLP candidata** | Arquitetura [8], 121 parâmetros, semente 2026 | **Pesos exatos** de `resultados/sinteticos/treino_v2/mlp_candidata.npz`, SHA-256 dos parâmetros `e6a4cf00…5b9991`, executados pela implementação de referência do contrato |

Nenhuma busca de hiperparâmetros acontece na fase C.

## 2. Conferência obrigatória antes de abrir o teste

O teste **só é aberto** se todas as condições abaixo forem verdadeiras. Caso contrário, a execução é interrompida sem tocar no teste.

1. O `validacao.json` versionado tem o SHA-256 `efba6c58…12aaa5`.
2. Baseline, árvore e regressão logística, ajustados de novo no treino, reproduzem **exatamente** as métricas de validação registradas.
3. A MLP carregada do `.npz` reproduz as métricas de validação registradas com diferença máxima de 1e-5. Na conferência de 01/11/2026 a diferença foi de 7,63e-9.
4. `resultados/sinteticos/teste_v2/teste.json` **não existe**, ou seja, o teste nunca foi aberto antes.

## 3. Abertura única

- O teste é aberto **uma única vez**, por disparo manual, com a confirmação digitada `ABRIR-TESTE-V2`.
- O resultado é gravado em `resultados/sinteticos/teste_v2/teste.json`. A ferramenta se recusa a rodar outra vez se esse arquivo já existir.
- Se a execução falhar depois de abrir o teste, a falha é registrada e informada à equipe. **Não se repete a abertura escolhendo o resultado.**

## 4. O que é calculado no teste

1. Para os 4 modelos: as métricas da seção 5 (log loss, Brier, ROC-AUC, ECE com 10 faixas, diagrama de confiabilidade e erro contra `p_real`).
2. **Bootstrap da diferença de log loss MLP − árvore**: 2.000 reamostragens de participantes, semente 2026, IC de 95%.
3. **Contexto, sem efeito na decisão:** as métricas de teste das outras 4 sementes da MLP. Exigem treinar de novo no CI e só são relatadas se cada semente reproduzir sua log loss de validação registrada com diferença máxima de 1e-5.
4. **Seção 7 do protocolo:** 1.000 partidas simuladas por política, com **alunos novos** (simulador `sim-1.1`, semente 2027, fora do treino, da validação e do teste). São comparadas a política adaptativa do fluxo-0.8 com cada modelo e a política da v0.7 (nível fixo). Resultados rotulados **[SINTÉTICO — simulação]**.

## 5. Aplicação da regra de decisão (seção 6, sem alteração)

A MLP candidata passa a ser o modelo padrão **somente se**:

1. **Desempenho:** o IC 95% de log loss(MLP) − log loss(árvore) estiver **inteiro abaixo de zero**, **ou** o IC cruzar zero e o ECE da MLP no teste for **menor** que o da árvore; **e**
2. **Viabilidade embarcada** ([`viabilidade_embarcada.md`](viabilidade_embarcada.md)): a bancada com os pesos da candidata aprovada na **correção funcional** (Wokwi ou placa) **e** no critério de **latência**, que só vale na **placa física**.

Se a condição 1 for satisfeita e a latência ainda não tiver sido medida na placa, a decisão é registrada como **"MLP aprovada condicionalmente, pendente de latência na placa física"**. Ela só se torna definitiva depois dessa medição.

Caso contrário, a árvore é o padrão, a MLP é apresentada como experimento e **o resultado negativo é relatado normalmente**.

## 6. Observações registradas antes do teste

- Na validação, todas as comparações por bootstrap cruzaram zero.
- O ECE da semente candidata (0,013) ficou abaixo da média das 5 sementes (0,023 ± 0,005). A semente 2026 foi fixada no código **antes** da execução (commit `05bd902`), e não escolhida pelo resultado. Mesmo assim, o desempate por ECE pode ser sensível à semente, e isso será dito no relatório final.
- Todos os resultados são **[SINTÉTICO]** e não comprovam eficácia educacional.
