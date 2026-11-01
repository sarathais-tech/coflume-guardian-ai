# Interface da v0.8 na tela ST7735 (proposta)

**Situação:** proposta para o firmware v0.8, a ser confirmada na tela física. A **v0.7 não é alterada**.
**Verificação:** `ferramentas.validar_banco` (cálculo em pixels, fonte padrão da Adafruit GFX).

## 1. De onde partimos

| | Simulação v0.7 | Tela física do Coflume |
|---|---|---|
| Controlador | ILI9341 | **ST7735, 1,8"** |
| Resolução | 320×240 (`setRotation(1)`, paisagem) | **160×128 em paisagem** (128×160 em retrato) |
| Texto | principalmente tamanho 2 | a definir |
| Colunas × linhas em tamanho 2 | 26 × 15 | **13 × 8 em paisagem**, 10 × 10 em retrato |

A ST7735 tem **cerca de um quarto da área** da ILI9341 da simulação. A interface da v0.7 não cabe nela sem redesenho.

## 2. Legibilidade

Na ST7735 de 1,8", cada pixel mede cerca de 0,22 mm.

| Tamanho do texto | Altura da letra | Para crianças na feira |
|---|---|---|
| 1 (célula 6×8 px) | ≈ 1,6 mm | Difícil de ler a mais de um palmo |
| **2** (célula 12×16 px) | ≈ 3,2 mm | **Recomendado para enunciado e alternativas** |

## 3. Layout proposto: paisagem, corpo em tamanho 2

```
 x: 0                                              160
y=0   ┌────────────────────────────────────────────┐
      │ DESAFIANTE 2/3   27s   *Dica   (tamanho 1)  │   8 px
y=8   │ ██████████████████░░░░░░  (barra de tempo)  │   até 8 px
y=16  │ Qual e um          (tamanho 2, 13 colunas)  │  16 px por linha
y=32  │ mamifero?                                   │
y=48  │ A) Tubarao                                  │
y=64  │ B) Golfinho                                 │
y=80  │ C) Polvo                                    │
y=96  │ D) Sardinha                                 │
y=112 │ (sobra 16 px)                               │
y=128 └────────────────────────────────────────────┘
```

| Elemento | Tamanho | Altura |
|---|---|---|
| Cabeçalho: nível, **progresso** (`2/3`), **temporizador** (`27s`) e lembrete `*Dica` | 1 | 8 px |
| Barra do temporizador (`fillRect`) | — | até 8 px |
| Enunciado + 4 alternativas | 2 | até **7 linhas** (112 px) |
| Rodapé | — | não há; o `*Dica` vai para o cabeçalho |

Teste com as 9 perguntas da v0.7:

```bash
python -m ferramentas.validar_banco questoes/banco_v07.csv --orientacao paisagem \
  --escala 2 --escala-moldura 1 --linhas-cabecalho 2 --linhas-rodape 0 --sem-separador
```

**Resultado: as 9 cabem.** A `V07-MES-2` usa os 128 px inteiros, sem nenhuma folga. Relatório em `resultados/banco/banco_v07_st7735_paisagem_t2_proposta.md`.

**Regra prática para escrever perguntas novas:** enunciado de até 2 linhas de 13 caracteres (cerca de 26 caracteres) e alternativas de até 10 caracteres, para caberem numa linha depois de `A) `.

### Comparação das configurações avaliadas

| Configuração | Cabem (de 9) | Observação |
|---|---|---|
| Retrato, tamanho 1, cabeçalho de 1 linha (padrão da ferramenta) | 9 | Cabe com folga, mas a letra fica pequena demais |
| Retrato, tamanho 1, cabeçalho de 2 linhas | 9 | Idem |
| Retrato, tamanho 2 em tudo | 5 | O cabeçalho `DESAFIANTE 3/3 30s` não cabe em 10 colunas |
| Retrato, corpo tamanho 2, moldura tamanho 1 | 5 a 6 | Apenas 10 colunas: alternativas longas quebram |
| Paisagem, corpo 2, moldura 1, com rodapé | 8 | A `V07-MES-2` passa 8 px |
| **Paisagem, corpo 2, moldura 1, sem rodapé (proposta)** | **9** | Sem folga para a `V07-MES-2` |

### Telas de dica e de resposta

Na configuração proposta, a dica ocupa até 48 px e a resposta correta até 64 px. Cabem com folga.

## 4. Acentos

O texto da v0.7 foi escrito **sem acentos** ("Quanto e", "Tubarao", "mamifero"). Isso evita o problema de fonte, mas é um erro de ortografia num produto educativo, e mais grave nas perguntas de Português.

O problema técnico:

1. A fonte padrão da Adafruit GFX segue a **página de código 437** (com `tft.cp437(true)` para o mapeamento correto). Texto em UTF-8 chega com 2 bytes por letra acentuada e aparece como caracteres errados.
2. A CP437 tem `á é í ó ú â ê ô à ç É Ç`, mas **não tem `ã` nem `õ`** (nem `Á Í Ó Ú Â Ê Ô Ã Õ`). Palavras como "Tubarão" e "não" não podem ser exibidas corretamente com a fonte padrão.

Opções para a v0.8:

| Opção | Vantagem | Custo |
|---|---|---|
| A. Manter sem acentos | Nenhum trabalho | Erro de ortografia visível |
| B. Converter UTF-8 → CP437 e desenhar `ã`/`õ` como glifos próprios de 5×7 (`drawBitmap`) | Mantém a fonte monoespaçada; a verificação de espaço continua válida | Pequena função de conversão e 2 a 4 glifos |
| C. Fonte personalizada GFX gerada com `fontconvert`, incluindo a faixa Latin-1 | Todos os acentos | Fonte proporcional: as medidas mudam e a verificação de espaço precisa ser refeita |

**Recomendação: opção B.** Ela resolve os acentos sem mudar as medidas usadas aqui. Precisa ser confirmada na tela física antes de reescrever as perguntas com acento.

## 5. Pendências para o firmware v0.8

1. Confirmar na ST7735 física a orientação, a legibilidade em tamanho 2 e o desenho dos glifos.
2. Ao reescrever as perguntas com acentos, rodar o validador de novo. A contagem de caracteres não muda com a opção B.
3. ~~Dar folga à `V07-MES-2`~~ Resolvido no `banco_v08.csv`: o enunciado de `V07-MES-2-R1` ("Phishing e...") ocupa 1 linha. **Todas as 13 perguntas da v0.8 deixam 16 px de folga** (`--margem-px 16`).
