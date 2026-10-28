# Reprodução do treinamento

Este guia permite que qualquer pessoa da equipe reproduza os resultados a partir de um clone limpo. Ele é atualizado a cada etapa; a coluna **Situação** indica o que já existe.

## 1. Ambiente

```bash
git clone git@github.com:<organizacao>/coflume-guardian-ai.git
cd coflume-guardian-ai
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/macOS: source .venv/bin/activate
pip install -r requirements-treino.txt
pip freeze > requirements.lock     # só na primeira vez; versione este arquivo
pytest
```

Para os testes de equivalência C++ é preciso ter `g++` ou `clang++` no PATH. No Windows, instale o MSYS2 (pacote `mingw-w64-ucrt-x86_64-gcc`) ou use o WSL.

## 2. Pipeline

| Passo | Comando | Saída | Situação |
|---|---|---|---|
| 1. Testes do núcleo | `pytest` | relatório no terminal | **Disponível** |
| 2. Bancada com pesos aleatórios | `python -m ferramentas.gerar_bancada --semente 2026` | `embarcado/bancada_ia/*.h` | **Disponível** |
| 3. Gerar dados sintéticos | `python -m ferramentas.gerar_sinteticos --semente 2026` | `dados/sinteticos/sessoes_v1.csv` | Próxima etapa |
| 4. Dividir por participante | `python -m ferramentas.dividir` | `splits/split_v1.json` | Próxima etapa |
| 5. Treinar modelos | `python -m ferramentas.treinar --fonte sint` | `modelos/<id>/` | Próxima etapa |
| 6. Avaliar (teste lacrado) | `python -m ferramentas.avaliar --fonte sint` | `resultados/sinteticos/<id>/` | Próxima etapa |
| 7. Exportar modelo aprovado | `python -m ferramentas.exportar --modelo <id>` | `release/` | Próxima etapa |

## 3. Reprodutibilidade

- Toda aleatoriedade usa sementes explícitas, registradas em `MODELO.json`.
- O TensorFlow pode ter pequenas variações entre CPUs e versões. Por isso relatamos média ± desvio em 5 sementes, e não um único valor.
- Cada execução de treino salva `ambiente.txt` (versões de Python, TensorFlow e numpy) junto aos resultados.
- O hash do modelo exportado (`GUARDIA_MODELO_HASH`) permite verificar que o firmware está usando exatamente o modelo avaliado.
