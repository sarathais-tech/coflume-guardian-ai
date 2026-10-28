# Dados: sintéticos × reais

## Regra geral

Dados sintéticos e reais **nunca** são misturados sem rótulo, e seus resultados ficam em pastas, tabelas e gráficos separados.

| | Sintéticos | Reais |
|---|---|---|
| Origem | `simulador.py`, com semente fixa | Logs do piloto, exportados pela Serial do cofre |
| Coluna `fonte` | `SINTETICO` | `REAL` |
| Pasta de dados | `dados/sinteticos/` (não versionada, regenerável) | `dados/reais/` (**nunca** versionada) |
| Pasta de resultados | `resultados/sinteticos/` | `resultados/reais/` |
| Prefixo em títulos de tabelas e gráficos | `[SINTÉTICO]` | `[REAL, n = <sessões>]` |
| Prefixo do id do modelo | `sint` | `real` |
| O que permite afirmar | O pipeline funciona; comparação de modelos em ambiente controlado | Desempenho preditivo numa amostra pequena e específica |
| O que **não** permite afirmar | Eficácia educacional; desempenho com crianças reais | Eficácia educacional (amostra pequena, sem grupo de controle) |

Um modelo treinado com dados misturados recebe o prefixo `misto` e deve ser avaliado **separadamente** em teste sintético e em teste real.

## Dados reais: condições

1. Participação somente com autorização dos responsáveis, no caso de menores.
2. Nenhum dado pessoal: sem nome, idade, foto, escola ou texto livre.
3. `participante_id` é um número aleatório gerado pelo cofre no início da sessão, sem relação com a pessoa.
4. Os arquivos ficam apenas nos computadores da equipe e não entram no Git.
5. Publicar dados reais, mesmo anonimizados, exige decisão explícita da equipe e autorização de quem participou.

## Esquema de uma linha

| Coluna | Tipo |
|---|---|
| `fonte` | `SINTETICO` \| `REAL` |
| `participante_id` | inteiro |
| `ordem` | inteiro, posição da questão na sessão (0 = primeira) |
| as 9 features e `categoria` | ver [features.md](features.md) |
| `acertou` | 0 \| 1 (rótulo) |
| `p_real` | real, **somente sintético**: probabilidade verdadeira do simulador |
