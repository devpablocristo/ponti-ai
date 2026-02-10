"""
=============================================================================
USE CASE: PREDICT ANOMALY
=============================================================================

Este use case hace predicciones con un modelo ya entrenado.

DIFERENCIA VS TRAINING:
-----------------------
Training:                        Prediction:
- Offline (script)               - Online (API)
- Minutos de duracion            - Milisegundos
- Todos los datos                - Un proyecto
- fit_transform (aprende)        - transform (solo aplica)


LECCION DE ML #9: Inference Pipeline
-------------------------------------
La "inference" es cuando usas el modelo para predecir.
El pipeline de inference es:

    Datos nuevos -> Transform -> Modelo -> Score -> Decision

Es CRITICO que:
1. Uses el MISMO pipeline de transform que en training
2. Los features esten en el MISMO orden
3. Manejes los mismos edge cases (nulos, outliers)

Si algo difiere, tendras "training-serving skew" y
el modelo dara resultados incorrectos.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ml.application.ports.feature_engineer import FeatureEngineerPort
from ml.application.ports.model_store import ModelStorePort
from ml.adapters.training.sklearn_feature_engineer import SklearnFeatureEngineer
from ml.config import MLConfig
from ml.domain.entities import Dataset, Prediction, ModelInfo


@dataclass
class PredictResult:
    """Resultado de una prediccion."""

    prediction: Prediction
    model_version: str
    inference_time_ms: float


class PredictAnomalyUseCase:
    """
    Detecta anomalias usando un modelo entrenado.

    CUANDO SE USA:
    - En la API (online)
    - Cada vez que se computan insights de un proyecto

    REQUISITOS:
    - Debe haber un modelo "activo" guardado
    - El modelo debe haber sido entrenado con el mismo pipeline
    """

    def __init__(
        self,
        config: MLConfig,
        model_store: ModelStorePort,
    ) -> None:
        """
        Inicializa el use case.

        NOTA: NO cargamos el modelo aqui.
        Lo cargamos "lazy" cuando se necesita.
        Esto permite iniciar la app sin modelo.
        """
        self.config = config
        self.model_store = model_store

        # Cache del modelo cargado
        self._model: Any | None = None
        self._pipeline: FeatureEngineerPort | None = None
        self._model_version: str | None = None
        self._model_info: ModelInfo | None = None

    def _ensure_model_loaded(self) -> bool:
        """
        Carga el modelo si no esta cargado.

        PATRON: Lazy Loading
        --------------------
        No cargamos el modelo hasta que se necesita.
        Esto permite:
        - Iniciar la app rapidamente
        - Funcionar sin modelo (modo degradado)
        - Recargar si cambia la version activa

        Returns:
            True si el modelo esta cargado, False si no hay modelo
        """
        if self._model is not None:
            return True

        active_version = self.model_store.get_active_version(
            model_id=self.config.model_type
        )

        if active_version is None:
            # No hay modelo activo
            return False

        # Cargar modelo y pipeline
        model, model_info, pipeline = self.model_store.load(
            model_id=self.config.model_type,
            version=active_version,
        )

        self._model = model
        self._pipeline = self._normalize_pipeline(pipeline)
        self._model_version = active_version
        self._model_info = model_info

        return True

    def _normalize_pipeline(self, pipeline: Any | None) -> FeatureEngineerPort | None:
        if pipeline is None:
            return None
        if hasattr(pipeline, "transform"):
            return pipeline
        if isinstance(pipeline, dict):
            engineer = SklearnFeatureEngineer(self.config)
            engineer._imputer = pipeline["imputer"]  # type: ignore[attr-defined]
            engineer._scaler = pipeline["scaler"]  # type: ignore[attr-defined]
            engineer._feature_names = list(pipeline["feature_names"])  # type: ignore[attr-defined]
            engineer._is_fitted = bool(pipeline.get("is_fitted", True))  # type: ignore[attr-defined]
            return engineer
        raise ValueError(f"Pipeline no soportado: {type(pipeline)!r}")

    def execute(self, dataset: Dataset) -> PredictResult | None:
        """
        Predice si un proyecto es anomalo.

        Args:
            dataset: Dataset con features del proyecto
                    (debe tener exactamente 1 muestra)

        Returns:
            PredictResult con la prediccion, o None si no hay modelo

        Raises:
            ValueError: Si el dataset no tiene exactamente 1 muestra
        """
        start_time = datetime.now(timezone.utc)

        # Verificar que hay exactamente 1 muestra
        if dataset.n_samples != 1:
            raise ValueError(
                f"Dataset debe tener exactamente 1 muestra, "
                f"tiene {dataset.n_samples}"
            )

        # Cargar modelo si no esta cargado
        if not self._ensure_model_loaded():
            # No hay modelo - retornar None (modo degradado)
            return None

        # Transformar features con el pipeline guardado
        if self._pipeline is None:
            raise ValueError("Pipeline no disponible para inferencia.")
        transformed = self._pipeline.transform(dataset)

        # Predecir con el modelo
        # El modelo tiene un metodo predict que devuelve scores
        scores = self._model.predict(transformed)

        # Crear resultado
        sample_id = dataset.sample_ids[0]
        anomaly_score = float(scores[0])
        threshold = float(self.config.thresholds.anomaly_threshold)
        if self._model_info is not None:
            calibrated = self._model_info.metrics.get("calibrated_threshold")
            if calibrated is not None:
                threshold = float(calibrated)
        is_anomaly = anomaly_score >= threshold

        prediction = Prediction(
            sample_id=sample_id,
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
            threshold_used=threshold,
            predicted_at=datetime.now(timezone.utc),
        )

        end_time = datetime.now(timezone.utc)
        inference_time_ms = (end_time - start_time).total_seconds() * 1000

        return PredictResult(
            prediction=prediction,
            model_version=self._model_version or "unknown",
            inference_time_ms=inference_time_ms,
        )

    def reload_model(self) -> bool:
        """
        Recarga el modelo desde el store.

        CUANDO SE USA:
        - Despues de entrenar un nuevo modelo
        - Si se activa una nueva version
        - Para debugging

        Returns:
            True si se cargo exitosamente
        """
        self._model = None
        self._pipeline = None
        self._model_version = None
        self._model_info = None

        return self._ensure_model_loaded()

    @property
    def model_info(self) -> ModelInfo | None:
        return self._model_info
