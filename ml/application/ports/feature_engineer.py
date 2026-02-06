"""
=============================================================================
PORT: FEATURE ENGINEER
=============================================================================

Este port define como transformar features crudos a features utiles.

LECCION DE ML #8: Feature Engineering
--------------------------------------
Los datos crudos casi NUNCA son optimos para ML.
Necesitas transformarlos.

Transformaciones tipicas:

1. NORMALIZACION (Scaling)
   Problema: cost_total va de 1,000 a 100,000
             workorders va de 1 a 50
   Solucion: Escalar ambos a media=0, std=1

   Por que importa?
   Sin scaling, el modelo daria mas peso a cost_total
   solo porque sus numeros son mas grandes.

2. MANEJO DE NULOS
   Problema: Algunos proyectos no tienen cost_per_ha
   Soluciones:
   - Reemplazar con mediana
   - Reemplazar con 0
   - Crear feature "tiene_cost_per_ha" (0/1)

3. FEATURES DERIVADOS
   Problema: Los features individuales no capturan relaciones
   Solucion: Crear nuevos features:
   - ratio = cost_total / hectares
   - growth = this_week / last_week
   - is_spike = growth > 2.0

4. ENCODING DE CATEGORICOS
   Problema: region="norte" no es un numero
   Soluciones:
   - One-hot: region_norte=1, region_sur=0, region_este=0
   - Label encoding: norte=0, sur=1, este=2


CONCEPTO CRITICO: Training-Serving Skew
----------------------------------------
Si transformas datos de forma DIFERENTE en training vs inference,
el modelo no funcionara bien.

Ejemplo de bug:
    # Training
    scaler.fit(training_data)  # Aprende media=1000, std=500
    X_train = scaler.transform(training_data)

    # Inference (MAL!)
    scaler.fit(new_data)  # Aprende media=1200, std=400 <-- DIFERENTE!
    X_new = scaler.transform(new_data)

    # El modelo fue entrenado esperando media=1000,
    # pero recibe datos con media=1200. Resultados incorrectos.

Solucion:
    # Training
    scaler.fit(training_data)
    X_train = scaler.transform(training_data)
    save_scaler(scaler)  # Guardar parametros

    # Inference (BIEN!)
    scaler = load_scaler()  # Cargar los MISMOS parametros
    X_new = scaler.transform(new_data)  # Usa media=1000, std=500
"""

from typing import Protocol, Any

from ml.domain.entities import Dataset


class FeatureEngineerPort(Protocol):
    """
    Interface para transformar features.

    PATRON: Fit-Transform
    ---------------------
    - fit(): Aprende parametros (media, std, etc)
    - transform(): Aplica transformacion
    - fit_transform(): Hace ambos (para training)

    IMPLEMENTACIONES POSIBLES:
    - StandardFeatureEngineer: Scaling + imputation basico
    - AdvancedFeatureEngineer: + features derivados
    - NullFeatureEngineer: No hace nada (para debugging)
    """

    def fit(self, dataset: Dataset) -> None:
        """
        Aprende parametros de transformacion del dataset.

        CUANDO SE USA:
        - Durante training
        - UNA sola vez

        QUE APRENDE:
        - Media y std de cada feature (para scaling)
        - Mediana de cada feature (para imputar nulos)
        - etc.

        Args:
            dataset: Dataset de entrenamiento
        """
        ...

    def transform(self, dataset: Dataset) -> Dataset:
        """
        Transforma un dataset usando parametros aprendidos.

        CUANDO SE USA:
        - Durante training (despues de fit)
        - Durante inference

        Args:
            dataset: Dataset a transformar

        Returns:
            Dataset transformado
        """
        ...

    def fit_transform(self, dataset: Dataset) -> Dataset:
        """
        Fit + transform en un paso (para training).

        Args:
            dataset: Dataset de entrenamiento

        Returns:
            Dataset transformado
        """
        ...

    def save(self, path: Any) -> None:
        """
        Guarda los parametros aprendidos.

        IMPORTANTE: Debes guardar el pipeline junto al modelo
        para asegurar que inference use los mismos parametros.
        """
        ...

    def load(self, path: Any) -> None:
        """
        Carga parametros previamente guardados.
        """
        ...
