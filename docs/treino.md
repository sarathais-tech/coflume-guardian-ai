# Treino e avaliação em validação (Etapa 2)

**Código:** `guardia/treino.py`, `guardia/metricas.py`, `ferramentas/treinar.py`, `ferramentas/relatorio_treino.py`
**Protocolo:** [`protocolo_avaliacao.md`](protocolo_avaliacao.md) e [adendo 01](protocolo_adendo_01.md), sem alteração de critérios
**Resultados:** `resultados/sinteticos/treino_v2/` · **Decisão sobre onde treinar:** [ADR 0010](adr/0010-treino-oficial-no-ci.md)

> Nesta etapa só **treino** e **validação** são usados. O **teste continua lacrado** e nenhum modelo foi exportado para o ESP32. Os dados são **sintéticos** (`sessoes_v2`, `sim-1.1`).

## 1. O que é treinado

| Modelo | Entradas | Busca (protocolo, seção 4) | Desempate |
|---|---|---|---|
| Baseline ingênuo | `nivel_inicial`, `nivel_candidato` | Nenhuma: taxa de acerto do treino por par; par não visto usa a taxa geral | — |
| Árvore de decisão | 13 entradas do contrato (sem padronizar) | `max_depth` ∈ {3, 4, 5, 6} × `min_samples_leaf` ∈ {20, 50, 100} | Árvore mais simples |
| Regressão logística | 13 entradas, posições 0..8 padronizadas | `C` ∈ {0,01; 0,1; 1; 10} | `C` menor (mais regularização) |
| MLP (Keras) | 13 entradas, posições 0..8 padronizadas | Ocultas ∈ {[8], [16], [16, 8], [32, 16]}; Adam (lr 1e-3), batch 64, L2 1e-4, paciência 20, até 300 épocas | Menor arquitetura a até 1% da melhor |

Métricas (seção 5): log loss (principal), Brier, ROC-AUC, ECE com 10 faixas de largura igual, diagrama de confiabilidade e erro absoluto médio contra `p_real`. Previsões são limitadas a [1e-15; 1 − 1e-15] no cálculo da log loss, igualmente para todos os modelos.

## 2. Interpretações do protocolo

Registradas **antes** de ver qualquer resultado de MLP. Nenhum critério foi alterado.

1. **Seleção de hiperparâmetros.** A seção 3.4 manda escolher com `GroupKFold` (5 folds) no treino; a seção 4 fala em "log loss de validação" para a MLP. Aplicamos a regra geral a **todos** os modelos: o critério de escolha é a log loss média nas 5 dobras do treino. O conjunto de validação serve só para o *early stopping* da MLP e para relatar métricas.
2. **Padronização sem vazamento.** Média e desvio são ajustados no subconjunto de ajuste de cada dobra e, no ajuste final, no treino inteiro. Nunca na validação.
3. **Sementes da MLP.** As 5 sementes (2026 a 2030) são usadas nas 5 execuções finais, relatadas como média ± desvio. Na validação cruzada, a dobra *k* usa a semente 2026 + *k*.
4. **Modelo candidato para o teste.** Para não escolher a "melhor semente" olhando a validação, **a candidata é a execução com semente 2026**, fixada antes dos resultados. É ela que será avaliada no teste lacrado e comparada com a árvore.
5. **Viés declarado.** A MLP usa a validação no *early stopping*, então suas métricas de validação são levemente otimistas em relação às da árvore e da regressão logística. A regra de decisão da seção 6 só é aplicada no **teste**.
6. **Comparações em validação são preliminares.** O bootstrap por participante (2.000 reamostragens, semente 2026) é calculado também na validação, apenas como indicação.

## 3. Como rodar

```bash
# Dados e divisão (sim-1.1, semente 2026)
python -m ferramentas.gerar_sinteticos --semente 2026
python -m ferramentas.dividir

# Modelos scikit-learn (não precisa de TensorFlow; segundos)
python -m ferramentas.treinar --modelos baseline arvore logistica --saida /tmp/treino_local

# Todos os modelos, incluindo a MLP (precisa de TensorFlow)
pip install -r requirements-treino.txt
python -m ferramentas.treinar --salvar-modelos modelos/treino_v2

# Relatório e diagrama de confiabilidade
python -m ferramentas.relatorio_treino resultados/sinteticos/treino_v2/validacao.json
```

## 4. Treino oficial

O resultado oficial vem do workflow `treino` do GitHub Actions ([ADR 0010](adr/0010-treino-oficial-no-ci.md)):

1. instala `requirements-treino.txt`, incluindo o TensorFlow, e registra `pip freeze`;
2. gera `sessoes_v2` com a semente 2026 e confere o SHA-256 com o registrado em `split_v2.json`;
3. treina **todos** os modelos no mesmo ambiente e com os mesmos dados;
4. publica `validacao.json` como artefato e como anotações compactadas, com SHA-256.

`python -m ferramentas.ler_resultado_ci --run <id> --saida resultados/sinteticos/treino_v2/validacao.json` remonta o arquivo a partir das anotações e recusa qualquer conteúdo cujo SHA-256 não confira.

## 5. O que fica registrado em `validacao.json`

- versão do pipeline, commit e identificador da execução do CI;
- arquivo de dados, SHA-256 e se é idêntico ao registrado no split;
- conjuntos carregados (`treino`, `validacao`) e a marca de teste lacrado;
- versões de Python, NumPy, pandas, scikit-learn e TensorFlow;
- sementes, configuração da MLP e grades completas com a log loss de cada dobra;
- métricas de validação, diagramas, épocas de parada e comparações por bootstrap;
- o oráculo `p_real` como referência do melhor desempenho possível.

## 6. Resultados em validação (execução 41329660286)

Relatório completo: [`resultados/sinteticos/treino_v2/relatorio_validacao.md`](../resultados/sinteticos/treino_v2/relatorio_validacao.md). Origem e hashes: [`ORIGEM.json`](../resultados/sinteticos/treino_v2/ORIGEM.json).

| Modelo | Log loss | Brier | ROC-AUC | ECE |
|---|---|---|---|---|
| Baseline ingênuo | 0,6386 | 0,2238 | 0,6218 | 0,0112 |
| Árvore (`max_depth` 6, `min_samples_leaf` 100) | 0,6359 | 0,2227 | 0,6261 | 0,0199 |
| Regressão logística (`C` 0,1) | 0,6335 | 0,2217 | 0,6368 | 0,0257 |
| MLP [8], 121 parâmetros: média ± dp de 5 sementes | 0,6351 ± 0,0009 | 0,2224 ± 0,0004 | 0,6350 ± 0,0027 | 0,0231 ± 0,0051 |
| MLP [8]: semente candidata 2026 | 0,6346 | 0,2222 | 0,6340 | 0,0129 |
| *Oráculo `p_real`* | *0,5794* | *0,1976* | *0,7342* | *0,0216* |

- Na validação, **todas as comparações por bootstrap cruzam zero**: nenhum modelo se distingue dos demais.
- A arquitetura [8] teve a melhor log loss média na validação cruzada (0,6383) e também é a menor.
- O *early stopping* parou a semente 2026 na época 18 de 38; nas dobras, entre as épocas 19 e 69.
- O ECE da semente candidata (0,013) está abaixo da média das 5 sementes (0,023). Diferenças de ECE abaixo de cerca de 0,02 estão dentro do ruído de amostragem com 1.800 linhas (o oráculo tem 0,022).
- **[SINTÉTICO]**: estes resultados não comprovam eficácia educacional. A decisão entre MLP e árvore será tomada no teste lacrado ([adendo 02](protocolo_adendo_02.md)).
