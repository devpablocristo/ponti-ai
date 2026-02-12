"""
=============================================================================
CONFIGURACION DEL MODULO ML
=============================================================================

LECCION DE PYTHON #1: Dataclasses
---------------------------------
En Go tienes structs. En Python usamos "dataclasses":

    Go:
        type Config struct {
            Enabled bool
            Threshold float64
        }

    Python:
        @dataclass
        class Config:
            enabled: bool
            threshold: float

La diferencia principal:
- Go: tienes que escribir getters/setters si quieres
- Python: @dataclass genera automaticamente __init__, __repr__, __eq__

El parametro "frozen=True" hace el objeto inmutable (como en Go por defecto).


LECCION DE PYTHON #2: Type Hints
--------------------------------
Python es dinamicamente tipado, pero puedes agregar "hints":

    def suma(a: int, b: int) -> int:
        return a + b

Los hints NO son obligatorios y NO se verifican en runtime.
Son documentacion y ayudan a IDEs/linters. Similar a JSDoc en JS.


LECCION DE PYTHON #3: Optional y Union
--------------------------------------
    campo: str | None      # Puede ser string o None (como *string en Go)
    campo: int | float     # Puede ser int o float (union type)


PRINCIPIO DE DISENO: Configuracion Estructurada
-----------------------------------------------
En lugar de 50 variables sueltas, agrupamos en dataclasses anidados:

    # Mal (dificil de mantener):
    ML_IF_CONTAMINATION=0.05
    ML_IF_N_ESTIMATORS=100
    ML_XGB_MAX_DEPTH=6

    # Bien (estructurado):
    ml:
        isolation_forest:
            contamination: 0.05
            n_estimators: 100
        xgboost:
            max_depth: 6
"""

from dataclasses import dataclass
from pathlib import Path
import os


# =============================================================================
# CONFIGURACION DE ISOLATION FOREST
# =============================================================================

@dataclass(frozen=True)
class IsolationForestConfig:
    """
    Hiperparametros de Isolation Forest.

    LECCION DE ML #1: Que son Hiperparametros?
    ------------------------------------------
    Los hiperparametros son configuraciones que TU defines antes de entrenar.
    El modelo NO los aprende de los datos.

    Ejemplos:
    - contamination: "Espero que ~5% de mis datos sean anomalias"
    - n_estimators: "Usa 100 arboles para decidir"

    Esto es diferente de los PARAMETROS del modelo, que SI se aprenden:
    - Los "cortes" de cada arbol se aprenden de los datos
    - Los "pesos" en redes neuronales se aprenden

    Analogia: Hiperparametros son como la configuracion de un compilador,
    mientras que los parametros son como el codigo compilado.
    """

    # contamination: Proporcion esperada de anomalias (0.0 a 0.5)
    #
    # COMO ELEGIR ESTE VALOR:
    # - Si tienes datos historicos, calcula: anomalias_pasadas / total
    # - Si no, empieza con 0.05 (5%) y ajusta segun resultados
    # - Valor bajo (0.01) = muy pocas alertas, riesgo de perder anomalias
    # - Valor alto (0.2) = muchas alertas, riesgo de falsos positivos
    contamination: float = 0.05

    # n_estimators: Numero de arboles de decision
    #
    # COMO FUNCIONA:
    # El modelo crea N arboles, cada uno intenta "aislar" los puntos.
    # Promedia los resultados de todos los arboles.
    #
    # COMO ELEGIR:
    # - Mas arboles = mejor precision, pero mas lento
    # - 100-300 es un buen rango para la mayoria de casos
    # - Si tienes muchos datos (>100k), puedes subir a 500
    n_estimators: int = 100

    # random_state: Semilla para reproducibilidad
    #
    # POR QUE ES IMPORTANTE:
    # Isolation Forest usa aleatoridad. Sin semilla fija,
    # cada vez que entrenas obtienes un modelo diferente.
    # Con semilla fija, siempre obtienes el mismo modelo.
    #
    # CUANDO CAMBIAR:
    # - Para produccion: usa valor fijo (42 es convencion)
    # - Para experimentar: cambia el valor y compara resultados
    random_state: int = 42


# =============================================================================
# CONFIGURACION DE XGBOOST (FASE 2)
# =============================================================================

@dataclass(frozen=True)
class XGBoostConfig:
    """
    Hiperparametros de XGBoost.

    LECCION DE ML #2: XGBoost vs Isolation Forest
    ----------------------------------------------
    Isolation Forest:
    - "Unsupervised": No necesita saber que es anomalia y que no
    - Detecta puntos "raros" o "diferentes"
    - Bueno cuando NO tienes datos etiquetados

    XGBoost:
    - "Supervised": NECESITA saber que es anomalia (label=1) y que no (label=0)
    - Aprende patrones especificos de TUS anomalias
    - Mejor precision cuando tienes suficientes datos etiquetados

    CUANDO USAR CADA UNO:
    - Inicio del proyecto: Isolation Forest (no tienes etiquetas)
    - Despues de meses: XGBoost (ya tienes feedback de usuarios)
    """

    # n_estimators: Numero de arboles (boosting rounds)
    n_estimators: int = 100

    # max_depth: Profundidad maxima de cada arbol
    #
    # CONCEPTO: Overfitting
    # - Arbol muy profundo = aprende "de memoria" los datos de training
    # - Arbol poco profundo = muy simple, no captura patrones
    # - 3-8 es un buen rango para empezar
    max_depth: int = 6

    # learning_rate: Que tan rapido aprende (0.0 a 1.0)
    #
    # CONCEPTO: Learning Rate
    # - Alto (0.3) = aprende rapido pero puede "pasarse" del optimo
    # - Bajo (0.01) = aprende lento pero mas preciso
    # - 0.1 es un buen balance para empezar
    learning_rate: float = 0.1

    random_state: int = 42


# =============================================================================
# CONFIGURACION DE THRESHOLDS
# =============================================================================

@dataclass(frozen=True)
class ThresholdsConfig:
    """
    Umbrales para convertir scores ML a severidades.

    LECCION DE ML #3: Scores vs Clasificacion
    ------------------------------------------
    Los modelos ML no dicen "es anomalia" o "no es anomalia".
    Dan un SCORE continuo (ej: 0.73).

    TU decides el "threshold" (umbral) para clasificar:
    - score >= 0.6 -> "es anomalia"
    - score < 0.6 -> "no es anomalia"

    TRADE-OFF:
    - Threshold alto (0.8) = pocas alertas, pero las que hay son seguras
    - Threshold bajo (0.3) = muchas alertas, algunas falsas

    Este trade-off se llama "Precision vs Recall":
    - Precision: De las alertas que di, cuantas eran reales?
    - Recall: De las anomalias reales, cuantas detecte?
    """

    # anomaly_threshold: Score minimo para considerar anomalia
    anomaly_threshold: float = 0.6

    # severity_high: Score para severity 80-100
    severity_high: float = 0.8

    # severity_medium: Score para severity 40-79
    severity_medium: float = 0.5


# =============================================================================
# CONFIGURACION DE FEATURES
# =============================================================================

@dataclass(frozen=True)
class FeaturesConfig:
    """
    Configuracion de features disponibles.

    LECCION DE ML #4: Que son Features?
    ------------------------------------
    Features = Variables/Columnas que el modelo usa para decidir.

    En tu caso, los features son metricas del proyecto:
    - cost_total: Cuanto se gasto en total
    - workorders_count: Cuantas ordenes de trabajo
    - etc.

    El modelo busca PATRONES en estos features:
    "Cuando cost_total es alto Y workorders_count es bajo,
    suele haber un problema"

    FEATURE ENGINEERING:
    A veces los features crudos no son los mejores.
    Puedes crear features derivados:
    - cost_per_workorder = cost_total / workorders_count
    - cost_growth = cost_this_week / cost_last_week

    Esto se llama "Feature Engineering" y es una de las partes
    mas importantes de ML.
    """

    # Features base disponibles en el sistema
    feature_names: tuple[str, ...] = (
        "cost_total",
        "cost_per_ha",
        "inputs_total_used",
        "workorders_count",
        "stock_variance",
        "total_hectares",
    )

    # Ventanas temporales
    # "all" = acumulado total
    # "last_7d" = ultimos 7 dias
    # "last_30d" = ultimos 30 dias
    windows: tuple[str, ...] = ("all", "last_7d", "last_30d")


# =============================================================================
# CONFIGURACION PRINCIPAL
# =============================================================================

@dataclass(frozen=True)
class MLConfig:
    """
    Configuracion principal del modulo ML.

    PATRON DE DISENO: Composition over Inheritance
    -----------------------------------------------
    En lugar de una clase gigante con 30 campos,
    componemos varias clases pequenas.

    Esto hace el codigo mas:
    - Legible: Cada seccion tiene su proposito
    - Testeable: Puedes probar cada parte por separado
    - Mantenible: Cambios en una seccion no afectan otras
    """

    # Directorio donde se guardan modelos entrenados
    models_dir: Path

    # Si ML esta habilitado
    enabled: bool

    # Tipo de modelo a usar: "isolation_forest", "xgboost", "ensemble"
    model_type: str

    # Configuraciones especificas por modelo
    isolation_forest: IsolationForestConfig
    xgboost: XGBoostConfig
    thresholds: ThresholdsConfig
    features: FeaturesConfig

    # Dias de cooldown entre alertas duplicadas
    cooldown_days: int = 7


def load_ml_config() -> MLConfig:
    """
    Carga configuracion desde variables de entorno.

    LECCION DE PYTHON #4: os.getenv()
    ----------------------------------
    os.getenv("VARIABLE", "default") lee variables de entorno.

    En Go seria:
        value := os.Getenv("VARIABLE")
        if value == "" {
            value = "default"
        }

    PATRON: Environment-based Configuration
    ----------------------------------------
    Configurar via variables de entorno permite:
    1. Diferentes valores en dev/staging/prod
    2. Secretos fuera del codigo
    3. Cambios sin recompilar
    """

    def get_bool(key: str, default: str) -> bool:
        """Helper para convertir string a bool."""
        return os.getenv(key, default).lower() in ("true", "1", "yes")

    def get_float(key: str, default: str) -> float:
        """Helper para convertir string a float."""
        return float(os.getenv(key, default))

    def get_int(key: str, default: str) -> int:
        """Helper para convertir string a int."""
        return int(os.getenv(key, default))

    return MLConfig(
        models_dir=Path(os.getenv("ML_MODELS_DIR", "ml_models")),
        enabled=get_bool("ML_ENABLED", "false"),
        model_type=os.getenv("ML_MODEL_TYPE", "isolation_forest"),
        isolation_forest=IsolationForestConfig(
            contamination=get_float("ML_IF_CONTAMINATION", "0.05"),
            n_estimators=get_int("ML_IF_N_ESTIMATORS", "100"),
            random_state=get_int("ML_IF_RANDOM_STATE", "42"),
        ),
        xgboost=XGBoostConfig(
            n_estimators=get_int("ML_XGB_N_ESTIMATORS", "100"),
            max_depth=get_int("ML_XGB_MAX_DEPTH", "6"),
            learning_rate=get_float("ML_XGB_LEARNING_RATE", "0.1"),
            random_state=get_int("ML_XGB_RANDOM_STATE", "42"),
        ),
        thresholds=ThresholdsConfig(
            anomaly_threshold=get_float("ML_ANOMALY_THRESHOLD", "0.6"),
            severity_high=get_float("ML_SEVERITY_HIGH", "0.8"),
            severity_medium=get_float("ML_SEVERITY_MEDIUM", "0.5"),
        ),
        features=FeaturesConfig(),
        cooldown_days=get_int("ML_COOLDOWN_DAYS", "7"),
    )
