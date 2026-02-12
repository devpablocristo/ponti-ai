"""
=============================================================================
USE CASE: TRAIN MODEL
=============================================================================

Este use case orquesta el proceso completo de entrenamiento.

LECCION DE PYTHON #8: Clases y __init__
----------------------------------------
En Python, __init__ es el constructor (similar a New() en Go).

    Go:
        func NewService(db *sql.DB) *Service {
            return &Service{db: db}
        }

    Python:
        class Service:
            def __init__(self, db: Database):
                self.db = db

La diferencia: Python usa "self" explicito en lugar de punteros.


LECCION DE PYTHON #9: Dependency Injection
------------------------------------------
Inyectamos dependencias en el constructor:

    # MAL - acoplamiento fuerte
    class TrainModel:
        def __init__(self):
            self.loader = PostgresDataLoader()  # Hardcoded!

    # BIEN - inyeccion de dependencias
    class TrainModel:
        def __init__(self, loader: DataLoaderPort):
            self.loader = loader  # Recibido desde afuera

Esto permite:
- Testear con mocks
- Cambiar implementaciones sin tocar el use case
- Seguir el principio Open/Closed
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import numpy as np

from ml.application.ports.data_loader import DataLoaderPort
from ml.application.ports.feature_engineer import FeatureEngineerPort
from ml.application.ports.model_store import ModelStorePort
from ml.application.ports.model_trainer import ModelTrainerPort
from ml.config import MLConfig
from ml.domain.entities import ModelInfo

HANDLED_THRESHOLD_SUGGEST_ERRORS = (ValueError, RuntimeError, OSError, KeyError, TypeError)


@dataclass
class TrainModelResult:
    """
    Resultado del entrenamiento.

    Por que un dataclass en lugar de un dict?
    - Type hints: el IDE sabe que campos tiene
    - Documentacion: puedes ver que significa cada campo
    - Validacion: si falta un campo, da error al crear
    """

    model_info: ModelInfo
    training_time_seconds: float
    metrics: dict[str, float]
    saved_path: str


class TrainModelUseCase:
    """
    Orquesta el proceso de entrenamiento de un modelo.

    FLUJO:
    1. Cargar datos de training
    2. Transformar features (fit_transform)
    3. Entrenar modelo
    4. Evaluar modelo
    5. Guardar modelo + pipeline

    CUANDO SE USA:
    - En scripts offline (no en la API)
    - Tipicamente por un cron job o manualmente
    """

    def __init__(
        self,
        config: MLConfig,
        data_loader: DataLoaderPort,
        feature_engineer: FeatureEngineerPort,
        model_trainer: ModelTrainerPort,
        model_store: ModelStorePort,
    ) -> None:
        """
        Inicializa el use case con sus dependencias.

        NOTA: Todas las dependencias son INTERFACES (ports).
        El use case no sabe si usa PostgreSQL o SQLite,
        sklearn o pytorch. Solo sabe que puede:
        - Cargar datos
        - Transformar features
        - Entrenar modelo
        - Guardar modelo
        """
        self.config = config
        self.data_loader = data_loader
        self.feature_engineer = feature_engineer
        self.model_trainer = model_trainer
        self.model_store = model_store

    def execute(
        self,
        version: str | None = None,
        set_active: bool = False,
        hyperparameters: dict[str, Any] | None = None,
    ) -> TrainModelResult:
        """
        Ejecuta el proceso de entrenamiento.

        Args:
            version: Version del modelo (ej: "v1_20240101")
                    Si None, genera automaticamente
            set_active: Si True, marca como version activa
            hyperparameters: Override de hiperparametros

        Returns:
            TrainModelResult con info del modelo entrenado

        Raises:
            ValueError: Si no hay suficientes datos
        """
        start_time = datetime.now(timezone.utc)

        # Paso 1: Cargar datos
        # --------------------
        # Esto llama al DataLoaderPort, que podria:
        # - Leer de PostgreSQL
        # - Leer de un archivo Parquet
        # - Leer de S3
        # El use case no sabe ni le importa de donde vienen
        dataset = self.data_loader.load_training_data()

        if dataset.n_samples < 10:
            raise ValueError(
                f"Muy pocos datos para entrenar: {dataset.n_samples} muestras. "
                "Necesitas al menos 10."
            )

        # Paso 2: Transformar features
        # ----------------------------
        # fit_transform hace dos cosas:
        # 1. fit: Aprende parametros (media, std de cada feature)
        # 2. transform: Aplica la transformacion
        transformed_dataset = self.feature_engineer.fit_transform(dataset)

        # Paso 3: Entrenar modelo
        # -----------------------
        model_info = self.model_trainer.train(
            dataset=transformed_dataset,
            hyperparameters=hyperparameters,
        )

        # Paso 4: Evaluar (opcional, si hay datos de test)
        # ------------------------------------------------
        metrics = self.model_trainer.evaluate(transformed_dataset)
        metrics.update(self._build_training_profile(dataset))
        metrics.update(self._build_backtest_metrics(transformed_dataset))
        calibrated = self._suggest_threshold_from_feedback(default_threshold=self.config.thresholds.anomaly_threshold)
        if calibrated is not None:
            metrics["calibrated_threshold"] = float(calibrated)
            metrics["calibrated_threshold_source"] = 1.0

        # Generar version si no se dio
        if version is None:
            version = f"v1_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Actualizar model_info con version y metricas
        # Usamos un nuevo objeto porque ModelInfo es frozen
        model_info = ModelInfo(
            model_id=model_info.model_id,
            model_type=model_info.model_type,
            version=version,
            trained_at=model_info.trained_at,
            n_samples_trained=model_info.n_samples_trained,
            hyperparameters=model_info.hyperparameters,
            feature_names=model_info.feature_names,
            metrics=metrics,
            is_active=set_active,
        )

        # Paso 5: Guardar modelo
        # ----------------------
        # Guardamos tanto el modelo como el pipeline de features
        saved_path = self.model_store.save(
            model=self.model_trainer,  # El trainer tiene el modelo interno
            model_info=model_info,
            pipeline=self.feature_engineer,
        )

        if set_active:
            self.model_store.set_active_version(
                model_id=self.config.model_type,
                version=version,
            )

        end_time = datetime.now(timezone.utc)
        training_time = (end_time - start_time).total_seconds()

        return TrainModelResult(
            model_info=model_info,
            training_time_seconds=training_time,
            metrics=metrics,
            saved_path=str(saved_path),
        )

    def _build_training_profile(self, dataset) -> dict[str, float]:
        profile: dict[str, float] = {
            "profile_contract_version": 1.0,
            "profile_n_samples": float(dataset.n_samples),
            "profile_n_features": float(dataset.n_features),
        }
        for feature_name, values in dataset.features.items():
            if not values:
                profile[f"profile_mean_{feature_name}"] = 0.0
                profile[f"profile_std_{feature_name}"] = 0.0
                profile[f"profile_nonzero_rate_{feature_name}"] = 0.0
                continue
            arr = np.asarray(values, dtype=float)
            profile[f"profile_mean_{feature_name}"] = float(np.mean(arr))
            profile[f"profile_std_{feature_name}"] = float(np.std(arr))
            profile[f"profile_nonzero_rate_{feature_name}"] = float(np.mean(arr != 0.0))
        return profile

    def _build_backtest_metrics(self, transformed_dataset) -> dict[str, float]:
        if not hasattr(self.model_trainer, "predict"):
            return {}
        scores = getattr(self.model_trainer, "predict")(transformed_dataset)
        scores_arr = np.asarray(scores, dtype=float)
        if scores_arr.size == 0:
            return {}
        threshold = float(self.config.thresholds.anomaly_threshold)
        return {
            "backtest_score_p50": float(np.percentile(scores_arr, 50)),
            "backtest_score_p90": float(np.percentile(scores_arr, 90)),
            "backtest_score_p95": float(np.percentile(scores_arr, 95)),
            "backtest_score_p99": float(np.percentile(scores_arr, 99)),
            "backtest_alert_rate_at_threshold": float(np.mean(scores_arr >= threshold)),
        }

    def _suggest_threshold_from_feedback(self, default_threshold: float) -> float | None:
        if not hasattr(self.data_loader, "suggest_anomaly_threshold"):
            return None
        suggest_fn = getattr(self.data_loader, "suggest_anomaly_threshold")
        try:
            value = suggest_fn(default_threshold)
        except HANDLED_THRESHOLD_SUGGEST_ERRORS:
            return None
        if value is None:
            return None
        return float(value)
