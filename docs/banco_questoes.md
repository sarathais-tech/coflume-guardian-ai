# Plano do banco de questões para a v0.8

**Situação:** planejamento e ferramenta de validação prontos. **A classificação das 9 perguntas da v0.7 está pendente**, porque elas ficam no firmware (repositório `coflume`) e ainda não foram trazidas para cá. O banco da **v0.7 não é alterado**.

**Ferramenta:** `python -m ferramentas.validar_banco <arquivo.csv>` (código em `guardia/banco.py`)
**Modelo do arquivo:** `questoes/banco_modelo.csv`

## 1. Situação atual (v0.7)

- 9 perguntas, 3 por nível, em ordem fixa.
- Distribuição por categoria: **ainda não levantada**.

## 2. Por que o fluxo-0.8 precisa de outro banco

No fluxo-0.8 cada pergunta é definida por **nível × categoria**:

- A pergunta 1 usa o nível escolhido com qualquer uma das 4 categorias.
- As perguntas 2 e 3 podem usar qualquer nível da faixa ± 1. Para Desafiante, isso inclui os 3 níveis.
- Portanto, **todas as 12 células** (3 níveis × 4 categorias) podem ser pedidas.

As 3 categorias da partida são distintas, então cada célula é usada no máximo uma vez por partida. A repetição **entre** partidas importa na feira, porque crianças assistem às partidas de outras e decoram respostas.

## 3. Como classificar as 9 perguntas da v0.7

1. Copiar as 9 perguntas para `questoes/banco_v07.csv`, no formato de `banco_modelo.csv`, com `origem = v0.7`.
2. Preencher `nivel` com o nível em que cada uma está na v0.7.
3. Preencher `categoria`. Se a pergunta misturar categorias, escolher a habilidade principal exigida.
4. Revisar se a dificuldade condiz com o nível e registrar quem revisou em `revisado_por`.
5. Rodar a validação:
   ```bash
   python -m ferramentas.validar_banco questoes/banco_v07.csv --relatorio resultados/banco/banco_v07.md
   ```
   Use `--orientacao paisagem` ou `--escala 2` se a v0.7 usar outra configuração de tela.

### Situação de cada pergunta

| Situação | Significado | Reaproveitável? |
|---|---|---|
| `apta` | Completa, classificada e cabe em todas as telas | **Sim**, como está |
| `ajustar` | Completa e classificada, mas o texto não cabe ou falta dica | Sim, depois de ajustar |
| `pendente` | Falta nível ou categoria | Depois de classificar |
| `invalida` | Falta alternativa, resposta correta inválida, alternativas repetidas ou id duplicado | Não, até ser corrigida |

Avisos não bloqueiam o uso: acentos (seção 4), revisor ausente, enunciado repetido.

## 4. Restrições da tela ST7735 (128×160)

Premissas da ferramenta, todas ajustáveis em `LayoutTFT`:

| Configuração | Colunas × linhas |
|---|---|
| Fonte padrão da Adafruit GFX (célula 6×8 px), tamanho 1, **retrato** | **21 × 20** (padrão) |
| Mesma fonte, tamanho 1, paisagem (160×128) | 26 × 16 |
| Mesma fonte, tamanho 2, retrato | 10 × 10 |

Telas verificadas, com quebra por palavras:

| Tela | Composição | Limite |
|---|---|---|
| Pergunta | cabeçalho (1) + enunciado + linha em branco (1) + alternativas `A)`…`D)` com recuo de 3 colunas + rodapé (1) | todas as linhas da tela |
| Dica | cabeçalho (1) + `Dica: …` | todas as linhas da tela |
| Resposta correta | cabeçalho (1) + `Resposta: X) …` | todas as linhas da tela |

Uma pergunta curta ocupa 8 das 20 linhas. Como referência prática, um enunciado de até cerca de 6 linhas (≈ 120 caracteres) com alternativas de 1 linha cabe com folga.

**Acentos:** a fonte padrão da GFX não exibe corretamente texto UTF-8 (`é`, `ç`, `ã` ocupam 2 bytes). A ferramenta avisa quando há esses caracteres. O firmware precisa convertê-los para os códigos da fonte ou usar outra fonte. Conferir na tela física o que a v0.7 já faz.

## 5. Tamanho recomendado

| Cenário | Perguntas por célula | Total | Uso |
|---|---|---|---|
| Mínimo funcional | 1 | 12 | Testes; repetição constante |
| **Mínimo para a feira** | 3 | **36** | Rotação curta; aceitável com fila pequena |
| **Recomendado** | 5 | **60** | Repetição bem menos perceptível |

### Perguntas adicionais

`adicionais = Σ por célula de max(0, meta − perguntas aptas)`. A ferramenta calcula isso com o banco real.

| Meta por célula | Se as 9 da v0.7 forem aptas e cobrirem 9 células diferentes | Se nenhuma for aproveitada |
|---|---|---|
| 1 | 3 | 12 |
| 3 | 27 | 36 |
| 5 | 51 | 60 |

Se as 9 perguntas cobrirem 3 categorias diferentes em cada nível, **todas as partidas do fluxo-0.8 já são viáveis** só com elas, graças à substituição de categoria (seção 6). Mesmo assim, haveria muita repetição na feira.

## 6. Regras de uso no firmware v0.8

1. A escolha segue [`fluxo_partida.md`](fluxo_partida.md), seções 2 e 3. A Guardiã só avalia níveis **disponíveis** (permitidos e com pergunta na categoria). Por isso **o nível nunca sai da faixa** e **a previsão registrada é a do nível apresentado**.
2. Se a categoria sorteada não tiver pergunta em nenhum nível permitido, usa-se a próxima categoria não usada. Na pergunta 1, a categoria precisa ter pergunta no nível escolhido.
3. Dentro da célula: sem repetição na partida e com rodízio entre partidas.
4. **Antes da feira**, o banco final precisa passar em `validar_banco` sem perguntas inválidas e com "Todas as partidas possíveis são viáveis". A ferramenta testa as 72 combinações de nível inicial e ordem de categorias.

## 7. Relação com a Guardiã

O modelo **não** usa o identificador da pergunta. Ele estima a chance de acerto por nível e categoria. Por isso:

- o tamanho do banco não muda o modelo;
- **a dificuldade precisa ser coerente com o nível.** Uma pergunta "Explorador" difícil demais faz a previsão errar. O simulador representa essa variação com desvio de 0,3 na dificuldade dentro do nível. No piloto, o `id` registrado no log permite medir a taxa de acerto de cada pergunta e apontar as que estão fora do nível.
