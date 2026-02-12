"""
=============================================================================
PORT: DATA LOADER
=============================================================================

Este port define como cargar datos para entrenar modelos.

CONCEPTO: Separacion Training vs Inference
-------------------------------------------
- Training: Cargar datos HISTORICOS para ensenar al modelo
- Inference: Cargar datos ACTUALES para hacer predicciones

Son diferentes porque:
1. Training necesita TODOS los datos (o un sample grande)
2. Inference solo necesita los datos de UNA muestra
3. Training es offline (lento esta OK)
4. Inference es online (debe ser rapido)
"""

from typing import Protocol

from contexts.ml.domain.entities import Dataset


class DataLoaderPort(Protocol):
    """
    Interface para cargar datos.

    IMPLEMENTACIONES POSIBLES:
    - PostgresDataLoader: Carga desde PostgreSQL
    - ParquetDataLoader: Carga desde archivos Parquet
    - S3DataLoader: Carga desde S3
    - MockDataLoader: Para tests
    """

    def load_training_data(self) -> Dataset:
        """
        Carga datos para entrenar el modelo.

        CUANDO SE USA:
        - En scripts de training (offline)
        - Tipicamente carga TODOS los proyectos
        - Puede ser lento (minutos)

        Returns:
            Dataset con features de todos los proyectos
        """
        ...

    def load_inference_data(self, sample_id: str) -> Dataset:
        """
        Carga datos para hacer prediccion en UNA muestra.

        CUANDO SE USA:
        - En la API (online)
        - Carga solo UN proyecto
        - Debe ser rapido (< 100ms)

        Args:
            sample_id: ID del proyecto/muestra

        Returns:
            Dataset con features del proyecto
        """
        ...

    def load_labeled_data(self) -> Dataset:
        """
        Carga datos CON etiquetas (para supervised learning).

        CUANDO SE USA:
        - Para entrenar XGBoost (supervised)
        - Las etiquetas vienen del feedback de usuarios

        Returns:
            Dataset con features + columna 'label'
        """
        ...
