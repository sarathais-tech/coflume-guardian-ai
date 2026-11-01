# Plano do banco de questões para a v0.8

**Situação:** as 9 perguntas da v0.7 foram transcritas para `questoes/banco_v07.csv` (texto original preservado) e classificadas (seção 8). O banco da **v0.7 não é alterado**. A interface proposta para a ST7735 está em [`interface_st7735.md`](interface_st7735.md).

**Ferramenta:** `python -m ferramentas.validar_banco <arquivo.csv>` (código em `guardia/banco.py`)
**Modelo do arquivo:** `questoes/banco_modelo.csv`

## 1. Situação atual (v0.7)

- 9 perguntas, 3 por nível, em ordem fixa, extraídas de `coflume/simulations/wokwi/v0.7/sketch.ino`.
- Cobrem **8 das 12 células**. Detalhes na seção 8.

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

## 8. Classificação das perguntas da v0.7 (01/11/2026)

Arquivo: `questoes/banco_v07.csv`. **A classificação precisa ser revisada pela equipe**; o campo `revisado_por` está vazio de propósito.

### Classificação

| id | Pergunta | Nível | Categoria | Justificativa da categoria |
|---|---|---|---|---|
| V07-EXP-1 | Quanto e 6 x 7? | Explorador | Matemática | Tabuada |
| V07-EXP-2 | Qual e um planeta? | Explorador | Conhecimentos gerais | Astronomia |
| V07-EXP-3 | Qual palavra esta correta? | Explorador | Português | Ortografia |
| V07-DES-1 | Quanto e 12 x 8? | Desafiante | Matemática | Multiplicação |
| V07-DES-2 | Qual e um mamifero? | Desafiante | Conhecimentos gerais | Ciências |
| V07-DES-3 | Proximo: 2,4,8,16... | Desafiante | Lógica | Padrão em sequência |
| V07-MES-1 | Binario 1010 = decimal? | Mestre | Matemática ⚠ | Sistema de numeração posicional. **Alternativa defensável: Lógica** (pensamento computacional) |
| V07-MES-2 | O que e phishing? | Mestre | Conhecimentos gerais | Cidadania digital |
| V07-MES-3 | Qual senha e melhor? | Mestre | Conhecimentos gerais | Cidadania digital |

Se a equipe preferir Lógica para a V07-MES-1, a célula Mestre × Lógica passa a ser coberta e Mestre × Matemática fica vazia. As contagens de perguntas adicionais não mudam.

### Cobertura (perguntas aptas no validador)

| Nível \ categoria | Matemática | Português | Lógica | Conhecimentos gerais |
|---|---|---|---|---|
| Explorador | 1 | 1 | **0** | 1 |
| Desafiante | 1 | **0** | 1 | 1 |
| Mestre | 1 | **0** | **0** | 2 |

- **Células vazias:** Explorador × Lógica, Desafiante × Português, Mestre × Português e Mestre × Lógica.
- **Todas as partidas são viáveis**, graças à substituição de categoria. Porém, **quem escolhe Mestre nunca vê Português**, porque não há pergunta de Português nos níveis Desafiante e Mestre.

### Reaproveitamento

| Situação | Perguntas |
|---|---|
| Reaproveitáveis como estão | V07-EXP-1, V07-EXP-2, V07-DES-1, V07-DES-2, V07-DES-3, V07-MES-3 |
| Reaproveitável, com folga de tela a resolver | V07-MES-2 (ocupa os 128 px inteiros no layout proposto) |
| **Precisam de ajuste de conteúdo** | V07-EXP-3 e V07-MES-1 (abaixo) |
| Todas, na versão da v0.8 | Revisão de acentos, depois de resolvida a fonte ([`interface_st7735.md`](interface_st7735.md), seção 4) |

O validador aprova as 9 automaticamente: ele confere formato e espaço, mas não confere conteúdo.

### Problemas de conteúdo e dificuldade (revisão manual)

| id | Problema | Sugestão para a versão v0.8 |
|---|---|---|
| **V07-EXP-3** | **"Cassa" também é palavra correta** (verbo *cassar*; também nome de tecido). A pergunta tem duas respostas válidas. A dica "Tem a letra S" vale para "Casa" e para "Cassa". | Trocar a alternativa D por uma grafia inexistente e rever a dica |
| **V07-MES-1** | A dica "8 + 2" **entrega a resposta**: a conta dá 10 diretamente | Dica sobre o método, sem o resultado (por exemplo, o valor de cada posição) |
| V07-EXP-1 | A tabuada do 7 pode ser difícil para o público mais novo do nível Explorador | Conferir no piloto pela taxa de acerto da pergunta |
| V07-MES-2, V07-MES-3 | Conhecimento de segurança digital; podem ser **mais fáceis** que perguntas do nível Desafiante, e a alternativa correta de V07-MES-3 é visualmente diferente das demais, o que permite acertar por eliminação | Conferir no piloto; o `id` registrado no log permite medir |
| V07-MES-2 | Termo em inglês ("phishing") | Aceitável no nível Mestre; manter a dica |
| Todas | Sem acentos ("Quanto e", "Tubarao", "mamifero", "Proximo", "Binario", "Antivirus", "usuario", "Unica") | Reescrever com acentos quando a fonte permitir. **"Tubarão" exige `ã`, ausente da fonte padrão** |

### Quantas perguntas faltam

| Meta | Se as 9 forem aproveitadas | Se V07-EXP-3 e V07-MES-1 ficarem de fora até o ajuste |
|---|---|---|
| 1 por célula (12) | 4 | 6 |
| **3 por célula (36)** | **27** | 29 |
| **5 por célula (60)** | **51** | 53 |

São 4 e não 3 para a meta de 12 porque duas perguntas da v0.7 (V07-MES-2 e V07-MES-3) estão na mesma célula. **Nenhuma pergunta nova foi criada nesta etapa.**

Relatórios gerados pelo validador:
- `resultados/banco/banco_v07_st7735_retrato_t1.md`: configuração padrão da ferramenta.
- `resultados/banco/banco_v07_st7735_paisagem_t2.md`: paisagem, letra tamanho 2, com rodapé (8 de 9 cabem).
- `resultados/banco/banco_v07_st7735_paisagem_t2_proposta.md`: layout proposto (9 de 9 cabem).
