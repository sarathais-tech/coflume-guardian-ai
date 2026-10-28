"""MLP da Guardiã IA em Keras/TensorFlow.

O TensorFlow só é importado dentro das funções, para que o restante do pacote
(features, exportação, testes de equivalência) funcione sem ele.

Fluxo:
    modelo_keras = construir_mlp((16, 8), semente=2026)
    historico = treinar(modelo_keras, X_treino, y_treino, X_val, y_val, semente=2026)
    modelo = para_modelo_mlp(modelo_keras, media, desvio, fonte="SINTETICO")
    guardia.exportar.mlp_cpp.exportar(modelo, pasta)

X deve chegar JÁ padronizado (posições 0..8) com a média e o desvio do treino,
os mesmos que serão passados para `para_modelo_mlp`.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from guardia import contrato as C
from guardia.inferencia_ref import ModeloMLP


def padronizar(X: np.ndarray, media: np.ndarray, desvio: np.ndarray) -> np.ndarray:
    """Aplica a padronização do contrato às posições 0..8 (one-hot intacto)."""
    X = np.asarray(X, dtype=np.float32).copy()
    desvio = np.where(np.asarray(desvio, np.float32) < 1e-6, 1.0, desvio).astype(np.float32)
    X[:, : C.N_NUMERICAS] = (X[:, : C.N_NUMERICAS] - media) / desvio
    return X


def estatisticas_treino(X_treino: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Média e desvio das features numéricas, calculados SOMENTE no treino."""
    num = np.asarray(X_treino, dtype=np.float64)[:, : C.N_NUMERICAS]
    return num.mean(axis=0).astype(np.float32), num.std(axis=0).astype(np.float32)


def construir_mlp(ocultas: Sequence[int] = (16, 8), l2: float = 1e-4, semente: int = 2026):
    import tensorflow as tf

    if not 1 <= len(ocultas) <= 2:
        raise ValueError("O contrato 1.x aceita 1 ou 2 camadas ocultas.")
    tf.keras.utils.set_random_seed(semente)
    reg = tf.keras.regularizers.l2(l2)
    entrada = tf.keras.Input(shape=(C.N_ENTRADAS,), name="features")
    x = entrada
    for i, n in enumerate(ocultas, start=1):
        x = tf.keras.layers.Dense(n, activation="relu", kernel_regularizer=reg, name=f"oculta_{i}")(x)
    saida = tf.keras.layers.Dense(1, activation="sigmoid", name="p_acerto")(x)
    modelo = tf.keras.Model(entrada, saida, name="guardia_mlp")
    modelo.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=[tf.keras.metrics.AUC(name="auc")],
    )
    return modelo


def treinar(
    modelo,
    X_treino: np.ndarray,
    y_treino: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    semente: int = 2026,
    epocas: int = 300,
    paciencia: int = 20,
    batch: int = 64,
):
    """Treina com early stopping na validação (que deve ser separada por participante)."""
    import tensorflow as tf

    tf.keras.utils.set_random_seed(semente)
    parada = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=paciencia, restore_best_weights=True
    )
    return modelo.fit(
        X_treino,
        y_treino,
        validation_data=(X_val, y_val),
        epochs=epocas,
        batch_size=batch,
        callbacks=[parada],
        verbose=0,
        shuffle=True,
    )


def para_modelo_mlp(modelo_keras, media, desvio, fonte: str, **metadados) -> ModeloMLP:
    """Converte o modelo Keras para o formato do contrato (W como [saídas, entradas])."""
    if fonte not in C.FONTES_VALIDAS:
        raise ValueError(f"Fonte inválida: {fonte!r}.")
    camadas = []
    for camada in modelo_keras.layers:
        pesos = camada.get_weights()
        if not pesos:
            continue  # camada de entrada
        kernel, bias = pesos
        camadas.append((np.asarray(kernel, np.float32).T, np.asarray(bias, np.float32)))
    return ModeloMLP(camadas, media, desvio, {"fonte": fonte, **metadados})
