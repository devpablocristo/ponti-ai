"""
=============================================================================
ENTIDADES DEL DOMINIO ML
=============================================================================

LECCION DE PYTHON #5: Dataclasses Avanzadas
--------------------------------------------

Los dataclasses pueden tener:
- Valores por defecto
- Campos calculados (usando field y default_factory)
- Metodos custom
- Validacion en __post_init__

Ejemplo:
    @dataclass
    class Persona:
        nombre: str
        edad: int = 0  # Valor por defecto

        def es_adulto(self) -> bool:  # Metodo custom
            return self.edad >= 18


LECCION DE ML #5: Que es un Dataset?
-------------------------------------
Un dataset es una coleccion de "muestras" (ejemplos).
Cada muestra tiene "features" (caracteristicas).

Ejemplo para tu caso:
    Dataset de proyectos agricolas:
    - Muestra 1: proyecto_a con [cost=1000, hectares=50, ...]
    - Muestra 2: proyecto_b con [cost=2000, hectares=100, ...]
    - ...

El modelo ML aprende patrones de estos datos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Dataset:
    """
    Representa un conjunto de datos para entrenamiento o prediccion.

    CONCEPTO: Immutabilidad (frozen=True)
    -------------------------------------
    Los datasets son inmutables porque:
    1. Evita bugs: No puedes modificar datos accidentalmente
    2. Thread-safe: Multiples threads pueden leer sin locks
    3. Hasheable: Puedes usarlos como keys en diccionarios

    En Go, esto seria como pasar structs por valor en lugar de puntero.

    Atributos:
        features: Diccionario {nombre_feature: [valores]}
        sample_ids: Lista de IDs (ej: project_ids)
        created_at: Cuando se creo el dataset
        metadata: Info adicional (fuente, version, etc)
    """

    # features es un dict donde:
    # - key = nombre del feature (ej: "cost_total_all")
    # - value = lista de valores, uno por muestra
    #
    # Ejemplo:
    # {
    #     "cost_total_all": [1000, 2000, 1500, ...],
    #     "hectares_all": [50, 100, 75, ...],
    # }
    features: dict[str, list[float]]

    # IDs de las muestras (para poder rastrear despues)
    sample_ids: tuple[str, ...]

    # Cuando se creo este dataset
    created_at: datetime

    # Metadata opcional (fuente de datos, filtros aplicados, etc)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        """Cantidad de muestras en el dataset."""
        return len(self.sample_ids)

    @property
    def n_features(self) -> int:
        """Cantidad de features."""
        return len(self.features)

    @property
    def feature_names(self) -> list[str]:
        """Lista de nombres de features."""
        return list(self.features.keys())


@dataclass(frozen=True)
class Prediction:
    """
    Resultado de una prediccion del modelo.

    CONCEPTO: Anomaly Score
    -----------------------
    Los modelos de deteccion de anomalias no dicen "si/no".
    Dan un SCORE (numero) que indica "que tan anomalo" es algo.

    - Score 0.0 = Completamente normal
    - Score 0.5 = Ambiguo
    - Score 1.0 = Muy anomalo

    TU decides el "threshold" (umbral) para clasificar:
    - Si score >= threshold -> es anomalia
    - Si score < threshold -> es normal

    TRADE-OFF (Precision vs Recall):
    - Threshold alto: Menos falsos positivos, pero pierdes anomalias reales
    - Threshold bajo: Detectas mas anomalias, pero mas falsos positivos
    """

    # ID de la muestra (ej: project_id)
    sample_id: str

    # Score de anomalia (0.0 a 1.0)
    anomaly_score: float

    # Si se considera anomalia (score >= threshold)
    is_anomaly: bool

    # Threshold usado para decidir
    threshold_used: float

    # Features que contribuyeron mas a la decision (explainability)
    top_features: tuple[str, ...] = field(default_factory=tuple)

    # Timestamp de la prediccion
    predicted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ModelInfo:
    """
    Metadata sobre un modelo entrenado.

    CONCEPTO: Model Registry
    ------------------------
    En produccion, necesitas saber:
    - Que version del modelo esta corriendo
    - Cuando se entreno
    - Con cuantos datos
    - Que hiperparametros uso
    - Que tan bien funciona (metricas)

    Esto permite:
    1. Debuggear: "Por que esta alerta? Ah, usa modelo v3"
    2. Rollback: "v4 tiene problemas, volver a v3"
    3. Compliance: "Que modelo genero esta decision?"
    """

    # Identificador unico del modelo
    model_id: str

    # Tipo de modelo ("isolation_forest", "xgboost", etc)
    model_type: str

    # Version del modelo (ej: "v1_20240101")
    version: str

    # Cuando se entreno
    trained_at: datetime

    # Con cuantas muestras se entreno
    n_samples_trained: int

    # Hiperparametros usados
    hyperparameters: dict[str, Any]

    # Nombres de features usados
    feature_names: tuple[str, ...]

    # Metricas de evaluacion (precision, recall, etc)
    metrics: dict[str, float] = field(default_factory=dict)

    # Si es el modelo activo en produccion
    is_active: bool = False
