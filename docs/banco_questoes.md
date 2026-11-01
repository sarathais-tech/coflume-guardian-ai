# Plano do banco de questões para a v0.8

**Situação:** planejamento. O banco da **v0.7 não é alterado**.

## 1. Situação atual (v0.7)

- 9 perguntas, 3 por nível, em ordem fixa.
- A distribuição por categoria das 9 perguntas ainda **não foi levantada**; ela define quantas podem ser reaproveitadas (seção 4).

## 2. Por que o fluxo-0.8 precisa de outro banco

No fluxo-0.8, cada pergunta é definida por **nível × categoria**:

- A pergunta 1 usa o nível escolhido com qualquer uma das 4 categorias.
- As perguntas 2 e 3 podem usar qualquer nível da faixa ± 1. Para Desafiante, isso inclui os 3 níveis.
- Portanto, **todas as 12 células** (3 níveis × 4 categorias) podem ser pedidas.

Como as 3 categorias de uma partida são distintas, cada célula é usada no máximo uma vez por partida. Uma pergunta por célula já evita repetição **dentro** da partida. A repetição **entre** partidas importa na feira, porque crianças assistem às partidas de outras e decoram respostas.

## 3. Tamanho recomendado

| Cenário | Perguntas por célula | Total | Uso |
|---|---|---|---|
| Mínimo funcional | 1 | 12 | Só para testes; a mesma pergunta se repete a cada partida que usa a célula |
| **Mínimo para a feira** | 3 | **36** | Rotação curta; aceitável com fila pequena |
| **Recomendado** | 5 | **60** | Repetição bem menos perceptível para quem assiste |

## 4. Quantas perguntas adicionais

`adicionais = 12 × k − (perguntas da v0.7 que podem ser reaproveitadas, até k por célula)`

| Cenário | Se as 9 da v0.7 forem reaproveitáveis | Se nenhuma for reaproveitável |
|---|---|---|
| k = 1 | 3 (no melhor caso, com as 9 cobrindo 9 células diferentes) | 12 |
| k = 3 | **27** | 36 |
| k = 5 | **51** | 60 |

Para fechar esse número, é preciso classificar as 9 perguntas da v0.7 por categoria e conferir se a dificuldade de cada uma condiz com o nível.

## 5. Campos de cada pergunta

| Campo | Regra |
|---|---|
| `id` | Único e estável (ex.: `MAT-1-03`) |
| `nivel` | 0 Explorador, 1 Desafiante, 2 Mestre |
| `categoria` | 0 Matemática, 1 Português, 2 Lógica, 3 Conhecimentos gerais |
| `enunciado` | Cabe no TFT 128×160 (cerca de 4 linhas de 21 caracteres) |
| `alternativas` A–D | 4 alternativas; o piso de 25% de acerto ao acaso do simulador supõe isso |
| `correta` | A, B, C ou D |
| `dica` | Curta; exibida com `*` |
| `revisado_por` | Quem conferiu conteúdo e nível |

## 6. Regras de uso no firmware v0.8

1. Selecionar dentro da célula (nível, categoria) sem repetir na partida. Um rodízio por célula entre partidas reduz a repetição na feira.
2. Se uma célula estiver vazia, o firmware deve usar o nível permitido mais próximo do escolhido, na mesma categoria, e registrar isso no log.

## 7. Relação com a Guardiã

O modelo **não** usa o identificador da pergunta. Ele estima a chance de acerto por nível e categoria. Por isso:

- o tamanho do banco não muda o modelo;
- **a dificuldade das perguntas precisa ser coerente com o nível.** Uma pergunta "Explorador" difícil demais faz a previsão errar. O simulador representa essa variação com desvio de 0,3 na dificuldade dentro do nível. Com dados reais, o piloto pode estimar a taxa de acerto de cada pergunta e apontar perguntas fora do nível.
