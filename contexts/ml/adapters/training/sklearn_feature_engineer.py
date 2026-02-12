"""
=============================================================================
ADAPTER: SKLEARN FEATURE ENGINEER
=============================================================================

Transforma features usando sklearn.

LECCION DE PYTHON #11: numpy Arrays
------------------------------------
numpy es LA libreria para computacion numerica en Python.
Es como si Go tuviera un tipo []float64 super optimizado.

    import numpy as np

    # Crear array
    arr = np.array([1, 2, 3, 4, 5])

    # Operaciones vectorizadas (MUY rapido)
    arr * 2        # [2, 4, 6, 8, 10]
    arr.mean()     # 3.0
    arr.std()      # 1.414...

    # 2D arrays (matrices)
    matrix = np.array([[1, 2], [3, 4]])
    matrix.shape   # (2, 2)

Por que importa para ML?
- Los modelos esperan numpy arrays como input
- Las operaciones vectorizadas son 100x mas rapidas que loops
- sklearn, pytorch, tensorflow todos usan numpy internamente


LECCION DE ML #10: StandardScaler
---------------------------------
StandardScaler transforma cada feature para tener:
- Media = 0
- Desviacion estandar = 1

Formula: x_scaled = (x - mean) / std

Ejemplo:
    Antes:  [1000, 2000, 1500, 3000]
    Media:  1875
    Std:    707

    Despues: [-1.24, 0.18, -0.53, 1.59]

Por que normalizar?
1. Modelos como SVM y redes neuronales funcionan mejor
2. Features con valores grandes no dominan sobre otros
3. El gradiente se comporta mejor durante training
"""

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from contexts.ml.config import MLConfig
from contexts.ml.domain.entities import Dataset


class SklearnFeatureEngineer:
    """
    Preprocesa features usando sklearn.

    Implementa FeatureEngineerPort.

    Pipeline:
    1. Imputer: Rellena valores faltantes con la mediana
    2. Scaler: Normaliza a media=0, std=1
    """

    def __init__(self, ml_config: MLConfig) -> None:
        """
        Inicializa el engineer.

        NOTA: Los transformers se crean pero NO se fit.
        Debes llamar fit() o fit_transform() antes de transform().
        """
        self.ml_config = ml_config

        # Imputer: Maneja valores faltantes
        # strategy="median" es mas robusto que "mean" ante outliers
        self._imputer = SimpleImputer(strategy="median")

        # Scaler: Normaliza valores
        self._scaler = StandardScaler()

        # Flag para saber si ya se hizo fit
        self._is_fitted = False

        # Nombres de features en orden (importante para inference)
        self._feature_names: list[str] = []

    def fit(self, dataset: Dataset) -> None:
        """
        Aprende parametros de transformacion.

        QUE APRENDE:
        - Imputer: Mediana de cada feature
        - Scaler: Media y std de cada feature

        Estos valores se usaran en transform() para
        aplicar la misma transformacion a datos nuevos.
        """
        # Convertir Dataset a numpy array
        X = self._dataset_to_array(dataset)

        # Guardar nombres de features en orden
        self._feature_names = list(dataset.features.keys())

        # Fit imputer
        X_imputed = self._imputer.fit_transform(X)

        # Fit scaler
        self._scaler.fit(X_imputed)

        self._is_fitted = True

    def transform(self, dataset: Dataset) -> Dataset:
        """
        Transforma dataset usando parametros aprendidos.

        IMPORTANTE: Debes llamar fit() primero.
        """
        if not self._is_fitted:
            raise ValueError(
                "El pipeline no esta fitted. "
                "Llama fit() o fit_transform() primero."
            )

        # Convertir a array, asegurando mismo orden de features
        X = self._dataset_to_array(dataset, feature_order=self._feature_names)

        # Aplicar transformaciones
        X_imputed = self._imputer.transform(X)
        X_scaled = self._scaler.transform(X_imputed)

        # Convertir de vuelta a Dataset
        return self._array_to_dataset(
            X_scaled,
            sample_ids=dataset.sample_ids,
            feature_names=self._feature_names,
        )

    def fit_transform(self, dataset: Dataset) -> Dataset:
        """
        Fit + transform en un paso.

        Conveniencia para training donde haces ambos.
        """
        self.fit(dataset)
        return self.transform(dataset)

    def save(self, path: Path) -> None:
        """
        Guarda el pipeline fitted.

        Guardamos:
        - Imputer (con medianas aprendidas)
        - Scaler (con medias y stds aprendidos)
        - Feature names (para orden correcto)
        """
        if not self._is_fitted:
            raise ValueError("No hay pipeline para guardar. Llama fit() primero.")

        artifact = {
            "imputer": self._imputer,
            "scaler": self._scaler,
            "feature_names": self._feature_names,
            "is_fitted": True,
        }

        joblib.dump(artifact, path)

    def load(self, path: Path) -> None:
        """
        Carga pipeline previamente guardado.
        """
        artifact = joblib.load(path)

        self._imputer = artifact["imputer"]
        self._scaler = artifact["scaler"]
        self._feature_names = artifact["feature_names"]
        self._is_fitted = artifact["is_fitted"]

    def _dataset_to_array(
        self,
        dataset: Dataset,
        feature_order: list[str] | None = None,
    ) -> np.ndarray:
        """
        Convierte Dataset a numpy array.

        FORMATO ESPERADO POR sklearn:
        - Filas = muestras (proyectos)
        - Columnas = features

        Ejemplo:
            Dataset:
                features = {"cost": [100, 200], "ha": [10, 20]}
                sample_ids = ("p1", "p2")

            Array:
                [[100, 10],   <- p1
                 [200, 20]]   <- p2
        """
        if feature_order is None:
            feature_order = list(dataset.features.keys())

        # Verificar que tenemos todos los features
        missing = set(feature_order) - set(dataset.features.keys())
        if missing:
            # Agregar features faltantes con valor 0
            for name in missing:
                dataset.features[name] = [0.0] * dataset.n_samples

        # Crear matriz
        n_samples = dataset.n_samples
        n_features = len(feature_order)

        X = np.zeros((n_samples, n_features))

        for j, name in enumerate(feature_order):
            values = dataset.features.get(name, [0.0] * n_samples)
            X[:, j] = values

        return X

    def _array_to_dataset(
        self,
        X: np.ndarray,
        sample_ids: tuple[str, ...],
        feature_names: list[str],
    ) -> Dataset:
        """
        Convierte numpy array de vuelta a Dataset.
        """
        features = {}
        for j, name in enumerate(feature_names):
            features[name] = X[:, j].tolist()

        return Dataset(
            features=features,
            sample_ids=sample_ids,
            created_at=datetime.now(timezone.utc),
            metadata={"transformed": True},
        )
