"""
=============================================================================
TRAINING ADAPTERS
=============================================================================

Implementaciones concretas para el proceso de training.

COMPONENTES:
------------
- PostgresDataLoader: Carga datos de PostgreSQL
- SklearnFeatureEngineer: Preprocesamiento con sklearn
- IsolationForestTrainer: Entrena Isolation Forest
- FileSystemModelStore: Guarda modelos en disco

DEPENDENCIAS:
-------------
Estos adapters usan librerias externas:
- sklearn: Para preprocesamiento y modelos
- pandas: Para manipulacion de datos
- joblib: Para serializar modelos

Estas dependencias NO deben "escapar" a otros layers.
El domain y application no deben saber que usamos sklearn.
"""

from ml.adapters.training.postgres_data_loader import PostgresDataLoader
from ml.adapters.training.sklearn_feature_engineer import SklearnFeatureEngineer
from ml.adapters.training.isolation_forest_trainer import IsolationForestTrainer
from ml.adapters.training.filesystem_model_store import FileSystemModelStore

__all__ = [
    "PostgresDataLoader",
    "SklearnFeatureEngineer",
    "IsolationForestTrainer",
    "FileSystemModelStore",
]
