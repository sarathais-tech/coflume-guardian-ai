# Especificação das features

**Versão:** 1.0 (contrato 1.0.0)
**Fonte da verdade:** este documento. As implementações em `guardia/features.py` (Python) e `guardia::montar_entrada()` em `embarcado/runtime/guardia_runtime.h` (C++) devem segui-lo, e o teste `tests/test_equivalencia_cpp.py` verifica que as duas produzem os mesmos valores.

## 1. Registro de uma resposta

O firmware registra cada questão respondida com estes campos:

| Campo | Tipo | Faixa | Observação |
|---|---|---|---|
| `categoria` | inteiro | 0 a 3 | 0 Matemática, 1 Português, 2 Lógica, 3 Conhecimentos gerais |
| `nivel` | inteiro | 0 a 2 | 0 Explorador, 1 Desafiante, 2 Mestre |
| `acertou` | booleano | | Tempo esgotado conta como erro |
| `tempo_gasto_s` | real | ≥ 0 | Segundos até a resposta ou até esgotar |
| `tempo_limite_s` | real | > 0 | Limite daquela questão (pode ser adaptado) |
| `usou_dica` | booleano | | Pelo menos uma dica exibida |

Nenhum campo identifica a pessoa.

## 2. Features calculadas

`H` é o histórico da sessão (respostas anteriores, em ordem) e `n = |H|`.

| # | Nome | Definição | Valor quando não há histórico |
|---|---|---|---|
| 0 | `nivel_candidato` | Nível da questão sendo avaliada | (sempre definido) |
| 1 | `nivel_inicial` | Nível escolhido pela criança no início | (sempre definido) |
| 2 | `n_respondidas` | `min(n, 8)` | 0 |
| 3 | `taxa_acerto_sessao` | acertos em H ÷ n | **0,5** |
| 4 | `taxa_acerto_categoria` | acertos na categoria candidata ÷ respostas nessa categoria | `taxa_acerto_sessao` (portanto **0,5** sem histórico) |
| 5 | `tempo_medio_norm` | média de `clamp(tempo_gasto_s ÷ tempo_limite_s, 0, 1)` | **0,5** |
| 6 | `dicas_por_questao` | respostas com dica ÷ n | **0,0** |
| 7 | `resultado_ultima` | +1 acertou, −1 errou | **0** |
| 8 | `sequencia` | tamanho da sequência final de resultados iguais, positivo para acertos e negativo para erros, limitado a [−3, +3] | **0** |
| 9–12 | `categoria_onehot` | 1 na posição da categoria candidata, 0 nas demais | (sempre definido) |

Regras numéricas:

- Somas e médias são acumuladas em `float32`, na ordem do histórico.
- Se `tempo_limite_s ≤ 0`, a razão daquela resposta é tratada como 1,0 (tempo esgotado).
- O histórico considerado tem no máximo 16 respostas (`GUARDIA_HIST_MAX`); respostas além disso são ignoradas, o que não ocorre numa partida normal.

### Por que `resultado_ultima` é ternária

Na Etapa 1 a feature era `acertou_ultima ∈ {0, 1}`. Isso tornava "ainda não respondeu" igual a "errou a última", o que ensinaria ao modelo uma informação falsa na primeira questão. O valor 0 agora significa explicitamente "sem histórico". Ver [ADR 0007](adr/0007-features-calculadas-no-runtime.md).

## 3. Vetor de entrada da MLP

Ordem fixa, 13 posições:

```
[ nivel_candidato, nivel_inicial, n_respondidas, taxa_acerto_sessao,
  taxa_acerto_categoria, tempo_medio_norm, dicas_por_questao,
  resultado_ultima, sequencia, cat0, cat1, cat2, cat3 ]
```

As posições 0 a 8 são padronizadas: `(x − média) ÷ desvio`, com média e desvio calculados **apenas no conjunto de treino** e exportados junto com os pesos. Se um desvio for menor que 1e-6, o exportador grava 1,0. As posições 9 a 12 entram como 0 ou 1.

## 4. Primeira questão (partida a frio)

### O problema
Na primeira questão não existe histórico. Um modelo que dependa apenas do histórico não teria o que dizer.

### O que o modelo recebe
Os valores neutros da tabela acima, com `n_respondidas = 0` e `resultado_ultima = 0`. As únicas informações reais são `nivel_inicial`, `nivel_candidato` e `categoria`.

### O que o modelo responde
Uma estimativa **populacional**: a chance de acerto típica de quem escolheu aquele nível inicial, numa questão daquele nível e categoria. Isso é aprendido dos dados, já que todas as sessões de treino contêm a sua primeira questão (com `n_respondidas = 0`). Ou seja, a primeira questão é uma situação **dentro da distribuição de treino**, não um caso especial que o modelo nunca viu.

**Requisito para o simulador e para o piloto:** toda sessão registrada deve incluir a primeira questão. O teste `test_dados_incluem_partida_a_frio` (a ser criado com o simulador) vai verificar isso.

### O que o firmware faz (política, lógica tradicional)
1. **Categoria:** sorteada entre as 4, usando `esp_random()`. As 3 questões principais terão categorias diferentes.
2. **Níveis candidatos:** apenas `nivel_inicial − 1` e `nivel_inicial` (limitados a 0–2). Na primeira questão nunca se oferece um nível acima do escolhido pela criança, para que a sessão não comece com frustração. Essa trava vale só para a primeira questão.
3. **Escolha:** chamar `guardia::prever()` para cada candidato e escolher o de probabilidade mais próxima de 0,70. Em empate, fica o `nivel_inicial`.
4. **Fallback:** se a previsão for `INVALIDO`, usar `nivel_inicial`.

### Limitação honesta
Na primeira questão a Guardiã só conhece a população, não a criança. A adaptação individual começa na segunda questão, quando há pelo menos um resultado observado. Isso deve ser dito na apresentação.

## 5. Mudanças nesta especificação

Qualquer mudança nesta tabela altera o significado das entradas e exige:
1. nova versão **MAJOR** do contrato;
2. novo ADR;
3. retreino de todos os modelos;
4. atualização simultânea de `features.py` e `guardia_runtime.h`, com os testes de equivalência passando.
