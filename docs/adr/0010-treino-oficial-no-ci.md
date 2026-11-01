# ADR 0010: Treino oficial no GitHub Actions

- **Status:** aceito (aguardando revisão da equipe)
- **Data:** 2026-11-01

## Contexto

A MLP é treinada com Keras/TensorFlow. O ambiente de desenvolvimento usado nesta etapa não tem acesso ao PyPI e não consegue instalar o TensorFlow. O CI do repositório instala e executa o TensorFlow normalmente (job "MLP Keras").

Para a comparação ser justa, todos os modelos precisam ser treinados com **os mesmos dados** e, de preferência, **no mesmo ambiente**.

## Opções avaliadas

1. Treinar a MLP com o `MLPClassifier` do scikit-learn, localmente. Contraria a decisão da equipe de usar Keras.
2. Treinar cada modelo onde for possível (scikit-learn local, MLP no CI). Mistura ambientes e versões numa mesma comparação.
3. **Treinar todos os modelos no CI**, num único job, e publicar o resultado com verificação de integridade.

## Decisão

Opção 3. O workflow `treino` gera os dados, treina os quatro modelos e publica `validacao.json` como artefato e como anotações compactadas com SHA-256. O arquivo versionado em `resultados/sinteticos/treino_v2/` é **remontado dessas anotações** por `ferramentas/ler_resultado_ci.py`, que confere o SHA-256. Ele não é digitado nem editado à mão.

## Consequências

- Resultados rastreáveis até o commit e a execução do CI.
- Os modelos do scikit-learn também podem ser treinados localmente em segundos, para desenvolvimento. Os números oficiais, porém, são os do CI.
- A versão do NumPy no CI pode diferir da local. O `validacao.json` registra se o CSV gerado no CI é idêntico ao registrado no `split_v2`. A divisão por participante continua válida de qualquer forma, porque depende só dos IDs e da semente.
- O TensorFlow pode variar entre versões e CPUs. Por isso a MLP é relatada como média ± desvio em 5 sementes, e o `pip freeze` da execução fica no artefato.
