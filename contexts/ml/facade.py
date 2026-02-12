"""
=============================================================================
ML FACADE - PUNTO DE ENTRADA SIMPLIFICADO
=============================================================================

PATRON: Facade
--------------
El patron Facade provee una interface simplificada a un subsistema complejo.

Sin Facade, para entrenar un modelo necesitas:
    1. Crear MLConfig
    2. Crear PostgresDataLoader
    3. Crear SklearnFeatureEngineer
    4. Crear IsolationForestTrainer
    5. Crear FileSystemModelStore
    6. Crear TrainModelUseCase con todas las dependencias
    7. Llamar execute()

Con Facade:
    ml = MLFacade(settings)
    ml.train()

El Facade "esconde" la complejidad interna y expone
solo los metodos que los usuarios necesitan.

EN GO SERIA:
------------
    // Sin facade
    loader := NewPostgresDataLoader(db)
    engineer := NewFeatureEngineer()
    trainer := NewTrainer(config)
    store := NewModelStore(path)
    useCase := NewTrainUseCase(loader, engineer, trainer, store)
    useCase.Execute()

    // Con facade
    ml := NewMLFacade(config)
    ml.Train()


LECCION DE PYTHON #14: @property
--------------------------------
@property convierte un metodo en un "getter":

    class Persona:
        def __init__(self, nombre: str):
            self._nombre = nombre

        @property
        def nombre(self) -> str:
            return self._nombre

    p = Persona("Juan")
    print(p.nombre)  # "Juan" - se llama como atributo, no metodo

En Go seria:
    func (p *Persona) Nombre() string {
        return p.nombre
    }
"""

from datetime import datetime, timezone
from typing import Any
import uuid
import hashlib

from contexts.ml.config import MLConfig, load_ml_config
from contexts.ml.domain.entities import Dataset, Prediction, ModelInfo
from contexts.ml.application.use_cases.train_model import TrainModelUseCase, TrainModelResult
from contexts.ml.application.use_cases.predict_anomaly import PredictAnomalyUseCase
from adapters.outbound.observability.metrics import inc_counter

# Importamos adapters directamente (el facade conoce la implementacion)
from contexts.ml.adapters.training.postgres_data_loader import PostgresDataLoader
from contexts.ml.adapters.training.sklearn_feature_engineer import SklearnFeatureEngineer
from contexts.ml.adapters.training.isolation_forest_trainer import IsolationForestTrainer
from contexts.ml.adapters.training.filesystem_model_store import FileSystemModelStore

# Importamos tipos del proyecto principal
from contexts.insights.application.ports.feature_repository import FeatureValue
from contexts.insights.domain.entities import Insight

HANDLED_MODEL_LOAD_ERRORS = (FileNotFoundError, ValueError, RuntimeError, OSError)


class MLFacade:
    """
    Punto de entrada simplificado para el modulo ML.

    Esconde la complejidad de:
    - Data loaders, feature engineers, trainers, stores
    - Use cases y sus dependencias
    - Configuracion

    Expone solo lo que necesitas:
    - train(): Entrena un modelo
    - detect_anomalies(): Detecta anomalias en features

    EJEMPLO DE USO:
    ---------------
        from contexts.ml import MLFacade
        from app.config import load_settings

        # Crear facade
        settings = load_settings()
        ml = MLFacade.from_settings(settings)

        # Entrenar (offline, en script)
        result = ml.train(version="v1", activate=True)
        print(f"Modelo entrenado: {result.model_info.version}")

        # Detectar anomalias (online, en API)
        insights = ml.detect_anomalies(project_id, features)
        print(f"Anomalias detectadas: {len(insights)}")
    """

    def __init__(
        self,
        ml_config: MLConfig,
        db_dsn: str,
        rollout_percent: int = 100,
        enabled_project_ids: tuple[str, ...] = (),
        auto_promote: bool = True,
        auto_retrain_min_hours: int = 24,
        promotion_min_alert_rate_improvement: float = 0.01,
        promotion_min_samples_ratio: float = 0.8,
    ) -> None:
        """
        Inicializa el facade con configuracion.

        Args:
            ml_config: Configuracion ML
            db_dsn: Connection string de PostgreSQL
        """
        self.config = ml_config
        self.db_dsn = db_dsn
        self.rollout_percent = max(0, min(100, int(rollout_percent)))
        self.enabled_project_ids = {item.strip() for item in enabled_project_ids if item and item.strip()}
        self.auto_promote = bool(auto_promote)
        self.auto_retrain_min_hours = max(1, int(auto_retrain_min_hours))
        self.promotion_min_alert_rate_improvement = max(0.0, float(promotion_min_alert_rate_improvement))
        self.promotion_min_samples_ratio = max(0.0, float(promotion_min_samples_ratio))
        self._last_drift_score: float | None = None
        self._last_drift_level: str | None = None

        # Crear componentes (lazy initialization seria mejor en produccion)
        self._data_loader = PostgresDataLoader(db_dsn, ml_config)
        self._feature_engineer = SklearnFeatureEngineer(ml_config)
        self._trainer = IsolationForestTrainer(ml_config)
        self._model_store = FileSystemModelStore(ml_config, db_dsn=db_dsn)

        # Use cases
        self._train_use_case: TrainModelUseCase | None = None
        self._predict_use_case: PredictAnomalyUseCase | None = None

    @classmethod
    def from_settings(cls, settings: Any) -> "MLFacade":
        """
        Crea facade desde Settings de la app.

        Este es el metodo recomendado para crear el facade
        desde el contexto de la aplicacion.
        """
        ml_config = load_ml_config()
        return cls(
            ml_config=ml_config,
            db_dsn=settings.db_dsn,
            rollout_percent=int(getattr(settings, "ml_rollout_percent", 100)),
            enabled_project_ids=tuple(getattr(settings, "ml_enabled_project_ids", ()) or ()),
            auto_promote=bool(getattr(settings, "ml_auto_promote", True)),
            auto_retrain_min_hours=int(getattr(settings, "ml_auto_retrain_min_hours", 24)),
            promotion_min_alert_rate_improvement=float(
                getattr(settings, "ml_promotion_min_alert_rate_improvement", 0.01)
            ),
            promotion_min_samples_ratio=float(getattr(settings, "ml_promotion_min_samples_ratio", 0.8)),
        )

    @property
    def is_enabled(self) -> bool:
        """Si ML esta habilitado en la configuracion."""
        return self.config.enabled

    @property
    def has_active_model(self) -> bool:
        """Si hay un modelo activo disponible."""
        version = self._model_store.get_active_version(self.config.model_type)
        return version is not None

    @property
    def active_version(self) -> str | None:
        """Version activa del modelo, o None si no hay."""
        return self._model_store.get_active_version(self.config.model_type)

    @property
    def available_versions(self) -> list[str]:
        """Versiones disponibles en storage local."""
        return self._model_store.list_versions(self.config.model_type)

    def get_status(self) -> dict[str, Any]:
        """Estado operativo del modulo ML para observabilidad."""
        active_history: list[str] = []
        if hasattr(self._model_store, "get_active_history"):
            active_history = getattr(self._model_store, "get_active_history")(self.config.model_type, 5)
        return {
            "enabled": bool(self.is_enabled),
            "model_type": self.config.model_type,
            "models_dir": str(self.config.models_dir),
            "has_active_model": bool(self.has_active_model),
            "active_version": self.active_version,
            "available_versions": self.available_versions,
            "active_history": active_history,
            "rollout_percent": self.rollout_percent,
            "rollout_allowlist_size": len(self.enabled_project_ids),
            "last_drift_score": self._last_drift_score,
            "last_drift_level": self._last_drift_level,
            "auto_promote": self.auto_promote,
            "auto_retrain_min_hours": self.auto_retrain_min_hours,
            "promotion_min_alert_rate_improvement": self.promotion_min_alert_rate_improvement,
            "promotion_min_samples_ratio": self.promotion_min_samples_ratio,
        }

    def train(
        self,
        version: str | None = None,
        activate: bool = False,
        hyperparameters: dict[str, Any] | None = None,
    ) -> TrainModelResult:
        """
        Entrena un modelo con datos actuales.

        CUANDO USAR:
        - En scripts offline (no en la API)
        - Despues de acumular nuevos datos
        - Periodicamente (ej: semanal)

        Args:
            version: Nombre de la version (ej: "v1_20240101")
                    Si None, genera automaticamente
            activate: Si True, marca como version activa
            hyperparameters: Override de hiperparametros

        Returns:
            TrainModelResult con info del modelo

        Raises:
            ValueError: Si no hay suficientes datos

        EJEMPLO:
            result = ml.train(version="v2", activate=True)
            print(f"Entrenado en {result.training_time_seconds}s")
            print(f"Metricas: {result.metrics}")
        """
        # Crear use case con dependencias actuales
        use_case = TrainModelUseCase(
            config=self.config,
            data_loader=self._data_loader,
            feature_engineer=self._feature_engineer,
            model_trainer=self._trainer,
            model_store=self._model_store,
        )

        return use_case.execute(
            version=version,
            set_active=activate,
            hyperparameters=hyperparameters,
        )

    def detect_anomalies(
        self,
        project_id: str,
        features: list[FeatureValue],
    ) -> list[Insight]:
        """
        Detecta anomalias en un proyecto usando ML.

        Esta es la funcion principal que integra ML con el resto
        del sistema de insights.

        Args:
            project_id: ID del proyecto
            features: Lista de features del proyecto

        Returns:
            Lista de Insights detectados (puede estar vacia)

        NOTA: Si no hay modelo activo, retorna lista vacia.
        Esto permite "degradar gracefully" sin modelo.
        """
        if not self.is_enabled:
            return []

        if not self.has_active_model:
            return []

        if not self._is_project_enabled_for_ml(project_id):
            inc_counter("ml.rollout.skipped.count", 1)
            return []

        project_features = [f for f in features if f.entity_type == "project"]
        if not project_features:
            return []

        # Crear use case de prediccion si no existe
        if self._predict_use_case is None:
            self._predict_use_case = PredictAnomalyUseCase(
                config=self.config,
                model_store=self._model_store,
            )

        # Convertir features a Dataset
        dataset = self._features_to_dataset(project_id, features)

        # Predecir
        result = self._predict_use_case.execute(dataset)

        if result is None:
            return []

        self._update_drift_state(dataset)

        # Convertir prediccion a Insights
        return self._prediction_to_insights(
            project_id=project_id,
            features=features,
            prediction=result.prediction,
            model_version=result.model_version,
        )

    def _features_to_dataset(
        self,
        project_id: str,
        features: list[FeatureValue],
    ) -> Dataset:
        """
        Convierte features del sistema a Dataset de ML.
        """
        contract = [
            f"{feature_name}_{window}"
            for feature_name in self.config.features.feature_names
            for window in self.config.features.windows
        ]
        feature_dict: dict[str, list[float]] = {name: [0.0] for name in contract}

        for f in features:
            if f.entity_type != "project":
                continue
            key = f"{f.feature_name}_{f.window}"
            if key in feature_dict:
                feature_dict[key] = [f.value]

        return Dataset(
            features=feature_dict,
            sample_ids=(project_id,),
            created_at=datetime.now(timezone.utc),
            metadata={"feature_contract": "features-v1"},
        )

    def _prediction_to_insights(
        self,
        project_id: str,
        features: list[FeatureValue],
        prediction: Prediction,
        model_version: str,
    ) -> list[Insight]:
        """
        Convierte prediccion ML a Insights del sistema.
        """
        if not prediction.is_anomaly:
            return []

        now = datetime.now(timezone.utc)
        from datetime import timedelta

        # Determinar severidad basada en score
        score = prediction.anomaly_score
        if score >= self.config.thresholds.severity_high:
            insight_type = "anomaly"
            severity = int(80 + (score - 0.8) * 100)
            severity = min(severity, 100)
        elif score >= self.config.thresholds.severity_medium:
            insight_type = "recommendation"
            severity = int(40 + (score - 0.5) * 130)
            severity = min(severity, 79)
        else:
            return []

        # Encontrar features mas extremos
        extreme_features = self._find_extreme_features(features)

        title = "Patron anomalo detectado por ML"
        summary = (
            f"El modelo ML detecta un patron inusual "
            f"(score: {score:.2f}). Features: {', '.join(extreme_features[:3])}."
        )

        dedupe_key = f"ml:{insight_type}"
        stable_key = f"{project_id}|ml|{insight_type}|{score:.2f}"

        insight = Insight(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key)),
            project_id=project_id,
            entity_type="project",
            entity_id=project_id,
            type=insight_type,
            severity=severity,
            priority=severity,
            title=title,
            summary=summary,
            evidence={
                "ml_model": self.config.model_type,
                "model_version": model_version,
                "anomaly_score": score,
                "threshold": prediction.threshold_used,
                "extreme_features": extreme_features,
            },
            explanations={
                "rule": f"ml_{self.config.model_type}",
                "description": (
                    "Isolation Forest detecta puntos que son faciles "
                    "de aislar (diferentes del patron normal)."
                ),
            },
            action={
                "action_type": "checklist",
                "action_params": {"source": "ml"},
                "suggested_due_date": (now + timedelta(days=7)).date().isoformat(),
                "cta_label": "Revisar patron",
            },
            model_version=f"ml-{model_version}",
            features_version="features-v1",
            computed_at=now,
            valid_until=now + timedelta(days=7),
            status="new",
            impact_min=None,
            impact_max=None,
            impact_unit=None,
            confidence="medium",
            dedupe_key=dedupe_key,
            cooldown_until=now + timedelta(days=self.config.cooldown_days),
            rules_version="ml_v1",
        )

        return [insight]

    def activate_version(self, version: str) -> dict[str, Any]:
        previous = self.active_version
        self._model_store.set_active_version(self.config.model_type, version)
        current = self.active_version
        if self._predict_use_case is not None:
            self._predict_use_case.reload_model()
        return {
            "status": "ok",
            "previous_active_version": previous,
            "active_version": current,
        }

    def rollback_version(self, target_version: str | None = None) -> dict[str, Any]:
        current = self.active_version
        if target_version is None:
            if hasattr(self._model_store, "get_active_history"):
                history = getattr(self._model_store, "get_active_history")(self.config.model_type, 5)
                if len(history) < 2:
                    raise ValueError("No hay version previa para rollback")
                target_version = history[1]
            else:
                raise ValueError("Rollback automatico no soportado por el model store")
        self._model_store.set_active_version(self.config.model_type, target_version)
        if self._predict_use_case is not None:
            self._predict_use_case.reload_model()
        return {
            "status": "ok",
            "previous_active_version": current,
            "active_version": self.active_version,
            "rollback_target_version": target_version,
        }

    def retrain_with_policy(
        self,
        version: str | None = None,
        hyperparameters: dict[str, Any] | None = None,
        auto_promote: bool | None = None,
        force_activate: bool = False,
    ) -> dict[str, Any]:
        previous_active_version = self.active_version
        active_info = self._get_model_info(previous_active_version)

        train_result = self.train(
            version=version,
            activate=False,
            hyperparameters=hyperparameters,
        )
        candidate_info = train_result.model_info

        effective_auto_promote = self.auto_promote if auto_promote is None else bool(auto_promote)
        should_activate = bool(force_activate)
        promotion_reason = "forced_activate" if force_activate else "auto_promote_disabled"

        if not should_activate and effective_auto_promote:
            should_activate, promotion_reason = self._should_promote(
                candidate_info=candidate_info,
                active_info=active_info,
            )

        if should_activate:
            self.activate_version(candidate_info.version)

        return {
            "status": "ok",
            "model_version": candidate_info.version,
            "training_time_seconds": float(train_result.training_time_seconds),
            "metrics": {k: float(v) for k, v in train_result.metrics.items()},
            "promoted": bool(should_activate),
            "promotion_reason": promotion_reason,
            "previous_active_version": previous_active_version,
            "active_version": self.active_version,
        }

    def retrain_if_needed(
        self,
        min_hours: int | None = None,
        version: str | None = None,
        hyperparameters: dict[str, Any] | None = None,
        auto_promote: bool | None = None,
    ) -> dict[str, Any]:
        hours_threshold = max(1, int(min_hours if min_hours is not None else self.auto_retrain_min_hours))
        active_info = self._get_model_info(self.active_version)
        if active_info is not None:
            age_hours = (datetime.now(timezone.utc) - active_info.trained_at).total_seconds() / 3600.0
            if age_hours < hours_threshold:
                return {
                    "status": "skipped",
                    "reason": "active_model_recent",
                    "age_hours": float(age_hours),
                    "min_hours": int(hours_threshold),
                    "active_version": self.active_version,
                }

        result = self.retrain_with_policy(
            version=version,
            hyperparameters=hyperparameters,
            auto_promote=auto_promote,
            force_activate=False,
        )
        result["status"] = "ok"
        result["reason"] = "trained"
        result["min_hours"] = int(hours_threshold)
        return result

    def _is_project_enabled_for_ml(self, project_id: str) -> bool:
        if self.enabled_project_ids:
            return project_id in self.enabled_project_ids
        if self.rollout_percent <= 0:
            return False
        if self.rollout_percent >= 100:
            return True
        bucket = int(hashlib.sha256(project_id.encode("utf-8")).hexdigest(), 16) % 100
        return bucket < self.rollout_percent

    def _update_drift_state(self, dataset: Dataset) -> None:
        if self._predict_use_case is None or self._predict_use_case.model_info is None:
            return
        drift = self._estimate_drift(dataset, self._predict_use_case.model_info)
        self._last_drift_score = drift["score"]
        self._last_drift_level = drift["level"]
        if drift["level"] == "high":
            inc_counter("ml.drift.high.count", 1)
        elif drift["level"] == "medium":
            inc_counter("ml.drift.medium.count", 1)
        else:
            inc_counter("ml.drift.low.count", 1)

    def _estimate_drift(self, dataset: Dataset, model_info: ModelInfo) -> dict[str, float | str]:
        z_scores: list[float] = []
        for feature_name in dataset.features.keys():
            train_mean = model_info.metrics.get(f"profile_mean_{feature_name}")
            if train_mean is None:
                continue
            train_std = float(model_info.metrics.get(f"profile_std_{feature_name}", 0.0))
            current_value = float(dataset.features.get(feature_name, [0.0])[0])
            scale = train_std if train_std > 1e-9 else max(abs(float(train_mean)), 1.0)
            z_score = abs(current_value - float(train_mean)) / scale
            z_scores.append(min(z_score, 10.0))

        if not z_scores:
            return {"score": 0.0, "level": "unknown"}

        avg_z = sum(z_scores) / len(z_scores)
        score = min(avg_z / 3.0, 1.0)
        if score >= 0.6:
            level = "high"
        elif score >= 0.3:
            level = "medium"
        else:
            level = "low"
        return {"score": float(score), "level": level}

    def _find_extreme_features(
        self,
        features: list[FeatureValue],
    ) -> list[str]:
        """
        Identifica features con valores mas extremos.
        """
        project_features = [
            f for f in features
            if f.entity_type == "project" and f.value != 0
        ]

        sorted_features = sorted(
            project_features,
            key=lambda f: abs(f.value),
            reverse=True,
        )

        return [f"{f.feature_name}_{f.window}" for f in sorted_features]

    def _get_model_info(self, version: str | None) -> ModelInfo | None:
        if version is None:
            return None
        if hasattr(self._model_store, "get_model_info"):
            info = getattr(self._model_store, "get_model_info")(self.config.model_type, version)
            if info is not None:
                return info
        try:
            _, info, _ = self._model_store.load(self.config.model_type, version)
            return info
        except HANDLED_MODEL_LOAD_ERRORS:
            return None

    def _should_promote(self, *, candidate_info: ModelInfo, active_info: ModelInfo | None) -> tuple[bool, str]:
        if active_info is None:
            return True, "no_active_model"

        min_samples = int(active_info.n_samples_trained * self.promotion_min_samples_ratio)
        if candidate_info.n_samples_trained < max(min_samples, 10):
            return False, "insufficient_samples"

        candidate_rate = candidate_info.metrics.get("backtest_alert_rate_at_threshold")
        active_rate = active_info.metrics.get("backtest_alert_rate_at_threshold")
        target_rate = float(self.config.isolation_forest.contamination)

        if candidate_rate is None or active_rate is None:
            if candidate_info.n_samples_trained > active_info.n_samples_trained:
                return True, "more_training_data"
            return False, "no_comparable_metrics"

        candidate_gap = abs(float(candidate_rate) - target_rate)
        active_gap = abs(float(active_rate) - target_rate)
        improvement = active_gap - candidate_gap
        if improvement >= self.promotion_min_alert_rate_improvement:
            return True, "better_alert_rate_calibration"
        return False, "no_significant_improvement"
