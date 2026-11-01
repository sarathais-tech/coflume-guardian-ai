# Simulador de dados sintéticos

**Versão:** `sim-1.0` · **Código:** `guardia/simulador.py` · **Decisões:** [ADR 0008](adr/0008-simulador-e-politica-de-coleta.md)

> Tudo o que este simulador gera é **SINTÉTICO**. Serve para construir e testar o pipeline e comparar modelos em condições controladas. **Não** representa crianças reais e **não** comprova eficácia educacional.

## 1. Gerar os dados

```bash
python -m ferramentas.gerar_sinteticos --semente 2026     # 3.000 participantes
python -m ferramentas.dividir                              # splits/split_v1.json
```

| Saída | Versionada? |
|---|---|
| `dados/sinteticos/sessoes_v1.csv` | Não (regenerável) |
| `dados/sinteticos/sessoes_v1.manifest.json` | Não (acompanha o CSV) |
| `resultados/sinteticos/sessoes_v1_resumo.md` | Sim |
| `splits/split_v1.json` | Sim |

## 2. Participantes simulados

Cada participante é um "aluno virtual" sem nenhum dado pessoal. Seu identificador é apenas o índice `0, 1, 2, …`.

| Atributo latente (nunca exportado) | Distribuição | Por quê |
|---|---|---|
| Nível inicial escolhido | Explorador 40%, Desafiante 35%, Mestre 25% | Crianças tendem a escolher níveis mais fáceis |
| Habilidade geral | Normal, média −0,7 / 0 / +0,7 conforme o nível inicial, desvio 0,8 | A escolha do nível se relaciona com a habilidade, mas de forma imperfeita |
| Habilidade por categoria | Habilidade geral + Normal(0; 0,5) | Uma criança pode ir bem em Matemática e mal em Português |
| Propensão a pedir dica | Normal(0; 0,8) | Algumas crianças pedem dica mais que outras |
| Velocidade | Log-normal, desvio 0,25 | Algumas crianças são mais rápidas |

O ganho de usar o nível inicial como sinal está nos dados, mas é **parcial**: há Exploradores habilidosos e Mestres com dificuldade.

## 3. Fluxo da partida simulada

Segue o fluxo combinado na Etapa 1 do projeto:

1. **3 questões principais**, cada uma de uma categoria diferente (sorteadas).
2. **Primeira questão:** nível sorteado entre `nivel_inicial − 1` e `nivel_inicial` (limitado a 0), conforme [`features.md`](features.md), seção 4.
3. **Demais questões principais:** nível sorteado uniformemente entre os 3 (política de coleta exploratória; ver [ADR 0008](adr/0008-simulador-e-politica-de-coleta.md)).
4. **Erro numa principal → 1 questão de reforço** na mesma categoria, no mesmo nível ou um abaixo (50% / 50%).
5. Tempo limite de **30 s** em todas as questões.

Cada sessão tem de 3 a 6 questões.

> ⚠ **Pendente:** este fluxo não foi conferido com o firmware v0.7 (repositório `coflume`, fora do escopo deste repositório). Se o v0.7 usar outro fluxo, por exemplo outro limite de tempo, outro número de questões ou outra regra de reforço, os parâmetros devem ser ajustados **antes** do treino, e o simulador deve passar para `sim-1.1`.

## 4. Modelo de resposta

Para uma questão de nível `n` na categoria `c`:

1. **Dificuldade:** `b = [−1, 0, +1][n] + Normal(0; 0,3)`. A variação simula questões mais fáceis ou mais difíceis dentro do mesmo nível.
2. **Dica:** usada com probabilidade `sigmoide(−1,2 + 1,0 · (b − θc) + propensão)`. Quanto mais difícil a questão para a criança, maior a chance de pedir dica.
3. **Tempo:** log-normal com mediana `(10 s · e^(0,3·(b − θc)) + 4 s · dica) · velocidade` e desvio 0,45 no log. Ao passar do limite, o tempo fica em 30 s e a resposta conta como **erro**.
4. **Acerto, se não esgotou:**

   `P = 0,25 + 0,75 · sigmoide(1,2 · (θc − b) + 0,8 · dica)`

   É o modelo de 3 parâmetros da Teoria de Resposta ao Item. O piso de 0,25 representa o chute com 4 alternativas (A–D).
5. **Aprendizagem:** após um erro, o jogo mostra uma explicação, e a habilidade na categoria sobe 0,3. Isso dá sentido à questão de reforço.

Ordem fixa dos sorteios em cada questão: dificuldade, dica, tempo, acerto.

### `p_real`: a probabilidade verdadeira

O modelo da Guardiã precisa prever o acerto **antes** de saber se haverá dica ou tempo esgotado. Por isso o simulador registra:

```
p_real = Σ_dica  P(dica) · (1 − P(esgotar | dica)) · P(correta | dica)
```

Essa probabilidade é calculada no mesmo instante em que as features. Ela permite medir o erro de cada modelo em relação à verdade, como prevê o [protocolo](protocolo_avaliacao.md), seção 5. **É um oráculo: nunca pode ser feature.**

Verificação: em 30.000 participantes simulados (semente 99), a taxa de acerto observada ficou a até 2,1 erros-padrão da média de `p_real` em todas as 10 faixas. No conjunto v1, a diferença global é 63,7% contra 63,6%.

## 5. Features

As 9 features e a categoria de cada linha são calculadas por `guardia.features.montar_entrada`, com o histórico **anterior** à questão. É a mesma especificação que o runtime C++ segue (ver [`features.md`](features.md)). O teste `test_features_recalculadas_a_partir_do_historico_sao_identicas` reconstrói o histórico de cada sessão a partir das colunas `resp_*` e confirma que as features são idênticas bit a bit.

O tempo é registrado com resolução de 0,01 s, e as features usam esse mesmo valor arredondado.

## 6. Reprodutibilidade

- **Semente padrão: 2026**, registrada no manifesto.
- Cada participante tem um gerador próprio, derivado de `SeedSequence(semente, spawn_key=(id,))`. Por isso o participante 17 é idêntico gerando 50 ou 3.000 participantes.
- O CSV usa fim de linha `\n` e formatação fixa, o que dá bytes idênticos no mesmo ambiente.
- O manifesto registra a semente, todos os parâmetros, o SHA-256 do CSV e as versões de Python e numpy.
- **Limite:** o NumPy não garante a mesma sequência aleatória entre versões diferentes. Em outra versão, o CSV pode mudar. A **divisão por participante não muda**, porque depende só dos IDs e da semente. `conferir_hash_dados()` avisa quando o CSV difere do usado na criação do split.

## 7. Limitações

1. **O modelo aprende o simulador.** Os parâmetros foram escolhidos por plausibilidade, não estimados de dados reais de crianças.
2. **A forma da verdade é conhecida.** O acerto segue uma fórmula logística com piso, então modelos com estrutura parecida têm vantagem natural. Isso foi registrado no protocolo **antes** dos resultados, e os parâmetros não serão ajustados para favorecer nenhum modelo.
3. **Política de coleta diferente da de uso.** Os níveis são sorteados uniformemente. No cofre, a Guardiã vai escolher os níveis, e os dados reais terão outra distribuição.
4. **Comportamentos não simulados:** cansaço, distração, chute rápido, crianças que respondem em grupo, dificuldade real de cada questão do banco, leitura lenta de enunciados longos no TFT.
5. **Sessões curtas (3 a 6 questões):** `n_respondidas` nunca passa de 5 nos dados, embora o contrato aceite até 8.
6. **Fluxo não conferido com o firmware v0.7** (seção 3).
