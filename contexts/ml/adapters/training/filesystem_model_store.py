"""
=============================================================================
ADAPTER: FILESYSTEM MODEL STORE
=============================================================================

Guarda modelos en el filesystem local.

LECCION DE PYTHON #13: pathlib.Path
------------------------------------
En Go usas path/filepath para manejar paths:

    Go:
        path.Join("dir", "subdir", "file.txt")
        filepath.Abs(path)

En Python moderno usas pathlib:

    from pathlib import Path

    # Crear path
    p = Path("dir") / "subdir" / "file.txt"

    # Operaciones
    p.exists()          # True/False
    p.is_file()         # Es archivo?
    p.parent            # Path del directorio padre
    p.name              # Nombre del archivo
    p.suffix            # Extension (.txt)
    p.read_text()       # Lee contenido como string
    p.write_text("...")  # Escribe string

    # Crear directorio
    p.mkdir(parents=True, exist_ok=True)

Beneficios:
- Orientado a objetos (mas legible que strings)
- Cross-platform (maneja / y \\)
- Operaciones utiles integradas


ESTRUCTURA DE ALMACENAMIENTO:
-----------------------------
    ml_models/
    +-- isolation_forest/
    |   +-- active.txt                    # Contiene: "v1_20240101"
    |   +-- v1_20240101/
    |   |   +-- model.joblib              # Modelo sklearn
    |   |   +-- pipeline.joblib           # Feature engineer
    |   |   +-- metadata.json             # Info del modelo
    |   +-- v2_20240215/
    |       +-- ...
    +-- xgboost/
        +-- ...
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import psycopg
from psycopg.rows import dict_row

from contexts.ml.config import MLConfig
from contexts.ml.domain.entities import ModelInfo


class FileSystemModelStore:
    """
    Guarda modelos en el filesystem.

    Implementa ModelStorePort.

    VENTAJAS:
    - Simple, no requiere infraestructura
    - Facil de debuggear (puedes ver los archivos)
    - Funciona en desarrollo local

    DESVENTAJAS:
    - No escala a multiples servidores
    - No tiene UI para ver modelos
    - No tiene tracking de experimentos

    Para produccion real, considera MLflow o similar.
    """

    def __init__(self, ml_config: MLConfig, db_dsn: str | None = None) -> None:
        """
        Inicializa el store.

        Crea el directorio de modelos si no existe.
        """
        self.models_dir = ml_config.models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.db_dsn = db_dsn
        if self.db_dsn:
            self._ensure_registry_table()

    def save(
        self,
        model: Any,
        model_info: ModelInfo,
        pipeline: Any | None = None,
    ) -> Path:
        """
        Guarda modelo, metadata y pipeline.

        Args:
            model: Trainer con el modelo interno (ej: IsolationForestTrainer)
            model_info: Metadata del modelo
            pipeline: Feature engineer fitted (opcional)

        Returns:
            Path al directorio del modelo
        """
        # Crear directorio para esta version
        version_dir = self.models_dir / model_info.model_type / model_info.version
        version_dir.mkdir(parents=True, exist_ok=True)

        # Guardar modelo
        model_path = version_dir / "model.joblib"
        joblib.dump(model, model_path)

        # Guardar pipeline si existe
        if pipeline is not None:
            pipeline_path = version_dir / "pipeline.joblib"
            # Si el pipeline tiene metodo save, usarlo
            if hasattr(pipeline, "save"):
                pipeline.save(pipeline_path)
            else:
                joblib.dump(pipeline, pipeline_path)

        # Guardar metadata como JSON (legible por humanos)
        metadata_path = version_dir / "metadata.json"
        metadata_dict = {
            "model_id": model_info.model_id,
            "model_type": model_info.model_type,
            "version": model_info.version,
            "trained_at": model_info.trained_at.isoformat(),
            "n_samples_trained": model_info.n_samples_trained,
            "hyperparameters": model_info.hyperparameters,
            "feature_names": list(model_info.feature_names),
            "metrics": model_info.metrics,
            "is_active": model_info.is_active,
        }
        metadata_path.write_text(json.dumps(metadata_dict, indent=2))

        self._upsert_registry(version_dir, model_info)

        return version_dir

    def load(
        self,
        model_id: str,
        version: str | None = None,
    ) -> tuple[Any, ModelInfo, Any | None]:
        """
        Carga modelo, metadata y pipeline.

        Args:
            model_id: Tipo de modelo (ej: "isolation_forest")
            version: Version especifica, o None para la activa

        Returns:
            Tuple de (modelo, metadata, pipeline)

        Raises:
            FileNotFoundError: Si no existe el modelo
        """
        # Obtener version
        if version is None:
            version = self.get_active_version(model_id)
            if version is None:
                raise FileNotFoundError(
                    f"No hay version activa para {model_id}"
                )

        version_dir = self.models_dir / model_id / version

        if not version_dir.exists():
            raise FileNotFoundError(
                f"Modelo no encontrado: {model_id}/{version}"
            )

        # Cargar modelo
        model_path = version_dir / "model.joblib"
        model = joblib.load(model_path)

        # Cargar metadata
        metadata_path = version_dir / "metadata.json"
        metadata_dict = json.loads(metadata_path.read_text())

        model_info = ModelInfo(
            model_id=metadata_dict["model_id"],
            model_type=metadata_dict["model_type"],
            version=metadata_dict["version"],
            trained_at=datetime.fromisoformat(metadata_dict["trained_at"]),
            n_samples_trained=metadata_dict["n_samples_trained"],
            hyperparameters=metadata_dict["hyperparameters"],
            feature_names=tuple(metadata_dict["feature_names"]),
            metrics=metadata_dict.get("metrics", {}),
            is_active=metadata_dict.get("is_active", False),
        )

        # Cargar pipeline si existe
        pipeline = None
        pipeline_path = version_dir / "pipeline.joblib"
        if pipeline_path.exists():
            pipeline = joblib.load(pipeline_path)

        return model, model_info, pipeline

    def get_active_version(self, model_id: str) -> str | None:
        """
        Obtiene la version activa de un modelo.

        Lee el archivo active.txt que contiene el nombre de la version.
        """
        if self.db_dsn:
            with psycopg.connect(self.db_dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT version
                        FROM ai_ml_models
                        WHERE model_type = %(model_type)s
                          AND is_active = TRUE
                        ORDER BY activated_at DESC NULLS LAST, updated_at DESC
                        LIMIT 1
                        """,
                        {"model_type": model_id},
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["version"])

        active_file = self.models_dir / model_id / "active.txt"

        if not active_file.exists():
            return None

        return active_file.read_text().strip()

    def set_active_version(self, model_id: str, version: str) -> None:
        """
        Marca una version como activa.

        Escribe el nombre de la version en active.txt
        """
        # Verificar que la version existe
        version_dir = self.models_dir / model_id / version
        if not version_dir.exists():
            raise FileNotFoundError(
                f"Version no encontrada: {model_id}/{version}"
            )

        if self.db_dsn:
            with psycopg.connect(self.db_dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE ai_ml_models
                        SET is_active = FALSE,
                            status = 'inactive',
                            deactivated_at = NOW(),
                            updated_at = NOW()
                        WHERE model_type = %(model_type)s
                          AND is_active = TRUE
                        """,
                        {"model_type": model_id},
                    )
                    cur.execute(
                        """
                        UPDATE ai_ml_models
                        SET is_active = TRUE,
                            status = 'active',
                            activated_at = NOW(),
                            deactivated_at = NULL,
                            updated_at = NOW()
                        WHERE model_type = %(model_type)s
                          AND version = %(version)s
                        """,
                        {"model_type": model_id, "version": version},
                    )
                    if cur.rowcount == 0:
                        raise FileNotFoundError(f"Version no registrada: {model_id}/{version}")
                conn.commit()

        # Escribir archivo active.txt
        active_file = self.models_dir / model_id / "active.txt"
        active_file.parent.mkdir(parents=True, exist_ok=True)
        active_file.write_text(version)

    def list_versions(self, model_id: str) -> list[str]:
        """
        Lista todas las versiones de un modelo.

        Retorna ordenadas por nombre (mas reciente primero si
        usas formato v1_YYYYMMDD).
        """
        if self.db_dsn:
            with psycopg.connect(self.db_dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT version
                        FROM ai_ml_models
                        WHERE model_type = %(model_type)s
                        ORDER BY created_at DESC, version DESC
                        """,
                        {"model_type": model_id},
                    )
                    rows = cur.fetchall()
            db_versions = [str(row["version"]) for row in rows]
            if db_versions:
                return db_versions

        model_dir = self.models_dir / model_id

        if not model_dir.exists():
            return []

        versions = [
            d.name
            for d in model_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

        # Ordenar descendente (mas reciente primero)
        return sorted(versions, reverse=True)

    def delete_version(self, model_id: str, version: str) -> None:
        """
        Elimina una version de modelo.

        CUIDADO: No se puede deshacer.
        """
        version_dir = self.models_dir / model_id / version

        if not version_dir.exists():
            return  # Ya no existe, OK

        # Verificar que no sea la version activa
        active = self.get_active_version(model_id)
        if active == version:
            raise ValueError(
                f"No puedes eliminar la version activa ({version}). "
                "Activa otra version primero."
            )

        if self.db_dsn:
            with psycopg.connect(self.db_dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        DELETE FROM ai_ml_models
                        WHERE model_type = %(model_type)s
                          AND version = %(version)s
                        """,
                        {"model_type": model_id, "version": version},
                    )
                conn.commit()

        shutil.rmtree(version_dir)

    def get_active_history(self, model_id: str, limit: int = 5) -> list[str]:
        if not self.db_dsn:
            active = self.get_active_version(model_id)
            return [active] if active else []
        with psycopg.connect(self.db_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT version
                    FROM ai_ml_models
                    WHERE model_type = %(model_type)s
                      AND activated_at IS NOT NULL
                    ORDER BY activated_at DESC
                    LIMIT %(limit)s
                    """,
                    {"model_type": model_id, "limit": limit},
                )
                rows = cur.fetchall()
        return [str(row["version"]) for row in rows]

    def get_model_info(self, model_id: str, version: str | None = None) -> ModelInfo | None:
        target_version = version or self.get_active_version(model_id)
        if target_version is None:
            return None

        if self.db_dsn:
            with psycopg.connect(self.db_dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            model_type,
                            version,
                            trained_at,
                            n_samples_trained,
                            hyperparameters_json,
                            feature_names_json,
                            metrics_json,
                            is_active
                        FROM ai_ml_models
                        WHERE model_type = %(model_type)s
                          AND version = %(version)s
                        LIMIT 1
                        """,
                        {"model_type": model_id, "version": target_version},
                    )
                    row = cur.fetchone()
            if row:
                return ModelInfo(
                    model_id=str(row["model_type"]),
                    model_type=str(row["model_type"]),
                    version=str(row["version"]),
                    trained_at=row["trained_at"],
                    n_samples_trained=int(row["n_samples_trained"]),
                    hyperparameters=dict(row["hyperparameters_json"] or {}),
                    feature_names=tuple(row["feature_names_json"] or []),
                    metrics={k: float(v) for k, v in dict(row["metrics_json"] or {}).items()},
                    is_active=bool(row["is_active"]),
                )

        metadata_path = self.models_dir / model_id / target_version / "metadata.json"
        if not metadata_path.exists():
            return None
        data = json.loads(metadata_path.read_text())
        return ModelInfo(
            model_id=str(data["model_id"]),
            model_type=str(data["model_type"]),
            version=str(data["version"]),
            trained_at=datetime.fromisoformat(data["trained_at"]),
            n_samples_trained=int(data["n_samples_trained"]),
            hyperparameters=dict(data.get("hyperparameters", {})),
            feature_names=tuple(data.get("feature_names", [])),
            metrics={k: float(v) for k, v in dict(data.get("metrics", {})).items()},
            is_active=bool(data.get("is_active", False)),
        )

    def _ensure_registry_table(self) -> None:
        with psycopg.connect(self.db_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_ml_models (
                        model_type TEXT NOT NULL,
                        version TEXT NOT NULL,
                        artifact_path TEXT NOT NULL,
                        trained_at TIMESTAMPTZ NOT NULL,
                        n_samples_trained INT NOT NULL,
                        hyperparameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        feature_names_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                        metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        is_active BOOLEAN NOT NULL DEFAULT FALSE,
                        status TEXT NOT NULL DEFAULT 'trained',
                        activated_at TIMESTAMPTZ NULL,
                        deactivated_at TIMESTAMPTZ NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (model_type, version)
                    )
                    """
                )
            conn.commit()

    def _upsert_registry(self, version_dir: Path, model_info: ModelInfo) -> None:
        if not self.db_dsn:
            return
        with psycopg.connect(self.db_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_ml_models (
                        model_type,
                        version,
                        artifact_path,
                        trained_at,
                        n_samples_trained,
                        hyperparameters_json,
                        feature_names_json,
                        metrics_json,
                        is_active,
                        status,
                        activated_at,
                        deactivated_at,
                        updated_at
                    ) VALUES (
                        %(model_type)s,
                        %(version)s,
                        %(artifact_path)s,
                        %(trained_at)s,
                        %(n_samples_trained)s,
                        %(hyperparameters_json)s::jsonb,
                        %(feature_names_json)s::jsonb,
                        %(metrics_json)s::jsonb,
                        %(is_active)s,
                        %(status)s,
                        %(activated_at)s,
                        %(deactivated_at)s,
                        NOW()
                    )
                    ON CONFLICT (model_type, version) DO UPDATE SET
                        artifact_path = EXCLUDED.artifact_path,
                        trained_at = EXCLUDED.trained_at,
                        n_samples_trained = EXCLUDED.n_samples_trained,
                        hyperparameters_json = EXCLUDED.hyperparameters_json,
                        feature_names_json = EXCLUDED.feature_names_json,
                        metrics_json = EXCLUDED.metrics_json,
                        is_active = EXCLUDED.is_active,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    """,
                    {
                        "model_type": model_info.model_type,
                        "version": model_info.version,
                        "artifact_path": str(version_dir),
                        "trained_at": model_info.trained_at,
                        "n_samples_trained": model_info.n_samples_trained,
                        "hyperparameters_json": json.dumps(model_info.hyperparameters),
                        "feature_names_json": json.dumps(list(model_info.feature_names)),
                        "metrics_json": json.dumps(model_info.metrics),
                        "is_active": bool(model_info.is_active),
                        "status": "active" if model_info.is_active else "trained",
                        "activated_at": datetime.utcnow() if model_info.is_active else None,
                        "deactivated_at": None,
                    },
                )
            conn.commit()
