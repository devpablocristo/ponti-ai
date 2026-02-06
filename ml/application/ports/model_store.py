"""
=============================================================================
PORT: MODEL STORE
=============================================================================

Este port define como guardar y cargar modelos entrenados.

CONCEPTO: Model Registry
------------------------
En produccion, no puedes tener modelos "sueltos" en tu laptop.
Necesitas:
1. Guardar modelos de forma persistente
2. Versionar (v1, v2, v3...)
3. Saber cual es la version "activa"
4. Poder hacer rollback si algo falla

OPCIONES DE ALMACENAMIENTO:
---------------------------
Simple (lo que usamos):
    - Filesystem local + archivos .joblib
    - Bueno para empezar y proyectos pequenos

Produccion real:
    - MLflow: Open source, muy usado
    - W&B (Weights & Biases): SaaS, buena UI
    - AWS SageMaker: Si ya usas AWS
    - Vertex AI: Si ya usas GCP
"""

from pathlib import Path
from typing import Protocol, Any

from ml.domain.entities import ModelInfo


class ModelStorePort(Protocol):
    """
    Interface para guardar y cargar modelos.

    IMPLEMENTACIONES POSIBLES:
    - FileSystemModelStore: Guarda en disco local
    - S3ModelStore: Guarda en S3
    - MLflowModelStore: Usa MLflow registry
    """

    def save(
        self,
        model: Any,  # El modelo entrenado (sklearn, xgboost, etc)
        model_info: ModelInfo,
        pipeline: Any | None = None,  # Pipeline de preprocesamiento
    ) -> Path:
        """
        Guarda un modelo entrenado.

        QUE SE GUARDA:
        1. El modelo en si (pesos, estructura)
        2. Metadata (cuando, con que datos, hiperparametros)
        3. Pipeline de preprocesamiento (para aplicar en inference)

        Args:
            model: El modelo entrenado
            model_info: Metadata del modelo
            pipeline: Pipeline de preprocesamiento (opcional)

        Returns:
            Path donde se guardo el modelo
        """
        ...

    def load(
        self,
        model_id: str,
        version: str | None = None,
    ) -> tuple[Any, ModelInfo, Any | None]:
        """
        Carga un modelo guardado.

        Args:
            model_id: ID del modelo (ej: "isolation_forest")
            version: Version especifica (ej: "v1_20240101")
                    Si None, carga la version activa

        Returns:
            Tuple de (modelo, metadata, pipeline)
        """
        ...

    def get_active_version(self, model_id: str) -> str | None:
        """
        Obtiene la version activa de un modelo.

        CONCEPTO: Active Version
        ------------------------
        Solo UNA version de cada modelo puede estar "activa".
        Esta es la que se usa en produccion.

        Esto permite:
        - Entrenar nuevas versiones sin afectar produccion
        - Probar antes de activar
        - Rollback rapido

        Args:
            model_id: ID del modelo

        Returns:
            Version activa, o None si no hay modelo
        """
        ...

    def set_active_version(self, model_id: str, version: str) -> None:
        """
        Marca una version como activa.

        CUIDADO: Esto afecta produccion inmediatamente.
        Asegurate de probar antes de activar.

        Args:
            model_id: ID del modelo
            version: Version a activar
        """
        ...

    def list_versions(self, model_id: str) -> list[str]:
        """
        Lista todas las versiones de un modelo.

        Returns:
            Lista de versiones ordenadas (mas reciente primero)
        """
        ...
