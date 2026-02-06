"""
=============================================================================
ADAPTER: ISOLATION FOREST TRAINER
=============================================================================

Entrena modelos Isolation Forest usando sklearn.

LECCION DE ML #11: Como funciona Isolation Forest
--------------------------------------------------
Imagina que tienes puntos en un plano 2D:
    - La mayoria estan agrupados en el centro
    - Unos pocos estan lejos del grupo (anomalias)

Isolation Forest:
1. Selecciona un feature al azar (ej: X)
2. Selecciona un valor al azar entre min(X) y max(X)
3. Divide los puntos: izquierda si X < valor, derecha si X >= valor
4. Repite recursivamente hasta aislar cada punto

CLAVE: Los puntos anomalos se aislan con MENOS divisiones
       porque estan lejos del grupo.

Ejemplo:
    Punto normal (en el centro del cluster):
    - Division 1: queda con 500 puntos
    - Division 2: queda con 200 puntos
    - Division 3: queda con 80 puntos
    - ... 10 divisiones para aislarlo

    Punto anomalo (lejos del cluster):
    - Division 1: queda con 5 puntos
    - Division 2: queda solo!
    - Solo 2 divisiones para aislarlo

El "anomaly score" es proporcional a la profundidad promedio.
Menos profundidad = mas anomalo.


LECCION DE PYTHON #12: Type Hints con Any
-----------------------------------------
A veces necesitas aceptar "cualquier tipo":

    from typing import Any

    def guardar(objeto: Any) -> None:
        # objeto puede ser cualquier cosa
        joblib.dump(objeto, path)

En Go seria como interface{}:

    func guardar(objeto interface{}) {
        ...
    }

Usamos Any cuando trabajamos con librerias externas
que devuelven tipos complejos (como sklearn models).
"""

from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

from ml.config import MLConfig
from ml.domain.entities import Dataset, ModelInfo


class IsolationForestTrainer:
    """
    Entrena modelos Isolation Forest.

    Implementa ModelTrainerPort.
    """

    def __init__(self, ml_config: MLConfig) -> None:
        """
        Inicializa el trainer.

        El modelo se crea durante train(), no aqui.
        Esto permite reusar el trainer para entrenar
        multiples modelos con diferentes datasets.
        """
        self.ml_config = ml_config
        self._model: IsolationForest | None = None
        self._feature_names: list[str] = []

    def train(
        self,
        dataset: Dataset,
        hyperparameters: dict[str, Any] | None = None,
    ) -> ModelInfo:
        """
        Entrena Isolation Forest con el dataset.

        Args:
            dataset: Dataset transformado (ya paso por FeatureEngineer)
            hyperparameters: Override de hiperparametros (opcional)

        Returns:
            ModelInfo con metadata del modelo
        """
        # Obtener hiperparametros
        config = self.ml_config.isolation_forest
        contamination = hyperparameters.get("contamination", config.contamination) if hyperparameters else config.contamination
        n_estimators = hyperparameters.get("n_estimators", config.n_estimators) if hyperparameters else config.n_estimators
        random_state = hyperparameters.get("random_state", config.random_state) if hyperparameters else config.random_state

        # Convertir dataset a numpy array
        X = self._dataset_to_array(dataset)
        self._feature_names = list(dataset.features.keys())

        # Crear modelo
        self._model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,  # Usar todos los cores
        )

        # Entrenar
        # fit() aprende la estructura de los datos
        # No retorna nada, modifica el modelo in-place
        self._model.fit(X)

        # Crear metadata
        model_info = ModelInfo(
            model_id="isolation_forest",
            model_type="isolation_forest",
            version="",  # Se asigna en el use case
            trained_at=datetime.now(timezone.utc),
            n_samples_trained=dataset.n_samples,
            hyperparameters={
                "contamination": contamination,
                "n_estimators": n_estimators,
                "random_state": random_state,
            },
            feature_names=tuple(self._feature_names),
        )

        return model_info

    def predict(self, dataset: Dataset) -> np.ndarray:
        """
        Predice anomaly scores para el dataset.

        NOTA: Este metodo es usado internamente y por el use case
        de prediccion. El ModelStore guarda el trainer completo,
        asi que puede llamar predict() despues de cargar.

        Returns:
            Array de scores normalizados (0 a 1, donde 1 = muy anomalo)
        """
        if self._model is None:
            raise ValueError("Modelo no entrenado. Llama train() primero.")

        X = self._dataset_to_array(dataset)

        # decision_function retorna scores donde:
        # - Valores MAS NEGATIVOS = MAS ANOMALOS
        # - Valores positivos = normales
        raw_scores = self._model.decision_function(X)

        # Convertir a escala 0-1 donde 1 = anomalo
        # Usamos sigmoid: 1 / (1 + exp(x))
        # Negamos porque sklearn usa convencion opuesta
        normalized = 1.0 / (1.0 + np.exp(2.0 * raw_scores))

        return normalized

    def evaluate(self, dataset: Dataset) -> dict[str, float]:
        """
        Evalua el modelo.

        NOTA: Isolation Forest es unsupervised, no tenemos labels.
        Solo podemos calcular metricas "internas":
        - Porcentaje de muestras marcadas como anomalias
        - Score promedio

        Para metricas reales (precision, recall), necesitarias
        datos etiquetados y usarias XGBoost.
        """
        if self._model is None:
            raise ValueError("Modelo no entrenado.")

        X = self._dataset_to_array(dataset)

        # predict() retorna -1 para anomalias, 1 para normales
        predictions = self._model.predict(X)
        n_anomalies = np.sum(predictions == -1)
        anomaly_rate = n_anomalies / len(predictions)

        # Scores
        scores = self.predict(dataset)
        avg_score = float(np.mean(scores))
        std_score = float(np.std(scores))

        return {
            "anomaly_rate": anomaly_rate,
            "avg_score": avg_score,
            "std_score": std_score,
            "n_samples": len(predictions),
            "n_anomalies": int(n_anomalies),
        }

    def get_model(self) -> IsolationForest | None:
        """
        Retorna el modelo sklearn interno.

        Usado por ModelStore para serializar.
        """
        return self._model

    def set_model(self, model: IsolationForest, feature_names: list[str]) -> None:
        """
        Establece el modelo (despues de cargar de disco).
        """
        self._model = model
        self._feature_names = feature_names

    def _dataset_to_array(self, dataset: Dataset) -> np.ndarray:
        """
        Convierte Dataset a numpy array.

        Asegura que las columnas esten en el mismo orden
        que durante training.
        """
        if self._feature_names:
            feature_order = self._feature_names
        else:
            feature_order = list(dataset.features.keys())

        n_samples = dataset.n_samples
        n_features = len(feature_order)

        X = np.zeros((n_samples, n_features))

        for j, name in enumerate(feature_order):
            values = dataset.features.get(name, [0.0] * n_samples)
            X[:, j] = values

        return X
