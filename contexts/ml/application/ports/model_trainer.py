"""
=============================================================================
PORT: MODEL TRAINER
=============================================================================

Este port define como entrenar modelos ML.

LECCION DE ML #6: El Proceso de Training
-----------------------------------------
Entrenar un modelo es "ensenarle" patrones de los datos.

Pasos tipicos:
1. Cargar datos (DataLoaderPort)
2. Preprocesar (FeatureEngineerPort) - limpiar, normalizar
3. Dividir en train/test (para evaluar)
4. Entrenar el modelo
5. Evaluar metricas
6. Guardar el modelo (ModelStorePort)

Este port se enfoca en el paso 4: el training en si.


LECCION DE ML #7: Unsupervised vs Supervised
--------------------------------------------
Unsupervised (Isolation Forest):
    - NO le dices que es anomalia
    - El modelo "descubre" que es raro por si solo
    - Input: solo features [X]
    - Aprende: "que es normal" y detecta lo diferente

Supervised (XGBoost):
    - LE DICES que es anomalia (label=1) y que no (label=0)
    - El modelo aprende a distinguir entre ambos
    - Input: features [X] + labels [y]
    - Aprende: "cuando veo estos features, es anomalia"

Cual es mejor?
    - Con pocos datos etiquetados: Unsupervised
    - Con muchos datos etiquetados: Supervised (mas preciso)
"""

from typing import Protocol, Any

from contexts.ml.domain.entities import Dataset, ModelInfo


class ModelTrainerPort(Protocol):
    """
    Interface para entrenar modelos.

    IMPLEMENTACIONES POSIBLES:
    - IsolationForestTrainer: Entrena Isolation Forest
    - XGBoostTrainer: Entrena XGBoost
    - EnsembleTrainer: Entrena multiples modelos
    """

    def train(
        self,
        dataset: Dataset,
        hyperparameters: dict[str, Any] | None = None,
    ) -> ModelInfo:
        """
        Entrena un modelo con el dataset dado.

        PROCESO INTERNO TIPICO:
        1. Convertir Dataset a formato del modelo (numpy array)
        2. Crear modelo con hiperparametros
        3. Llamar model.fit(X) o model.fit(X, y)
        4. Generar metadata (ModelInfo)

        Args:
            dataset: Datos de entrenamiento
            hyperparameters: Override de hiperparametros (opcional)

        Returns:
            ModelInfo con metadata del modelo entrenado
        """
        ...

    def evaluate(
        self,
        dataset: Dataset,
    ) -> dict[str, float]:
        """
        Evalua el modelo en un dataset de test.

        METRICAS TIPICAS:
        - Para clasificacion: precision, recall, f1, auc
        - Para anomaly detection: avg_precision, silhouette

        Args:
            dataset: Datos de evaluacion

        Returns:
            Dict con metricas (ej: {"precision": 0.85, "recall": 0.72})
        """
        ...
