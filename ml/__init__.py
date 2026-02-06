"""
=============================================================================
MODULO ML - BOUNDED CONTEXT PARA MACHINE LEARNING
=============================================================================

Este modulo es un "bounded context" separado del resto de la aplicacion.
Tiene su propia estructura hexagonal interna:

    ml/
    ├── domain/           Entidades puras de ML (sin dependencias externas)
    ├── application/      Casos de uso y ports (interfaces)
    │   ├── ports/        Interfaces que definen contratos
    │   └── use_cases/    Logica de negocio de ML
    └── adapters/         Implementaciones concretas
        ├── training/     Componentes para entrenar modelos
        └── inference/    Componentes para hacer predicciones

CONCEPTOS CLAVE PARA DESARROLLADORES DE GO:
-------------------------------------------

1. __init__.py = Es como el package en Go
   - Define que se exporta del modulo
   - Se ejecuta cuando haces "import ml"

2. Imports en Python:
   - "from ml.domain import Dataset" = similar a "import ml/domain"
   - "from ml import MLFacade" = similar a "import ml"

3. Este archivo exporta una "fachada" (MLFacade) que simplifica el uso:
   - En lugar de conocer 10 clases internas, usas 1 clase publica

USO BASICO:
-----------
    from ml import MLFacade

    # Crear fachada con configuracion
    ml = MLFacade(settings)

    # Entrenar modelo (offline, en script)
    ml.train_isolation_forest()

    # Detectar anomalias (online, en API)
    insights = ml.detect_anomalies(project_id, features)
"""

# Importamos solo lo que queremos exponer publicamente
# Esto es como definir las funciones publicas en Go (mayuscula)
from ml.facade import MLFacade
from ml.config import MLConfig, load_ml_config

# __all__ define que se exporta cuando alguien hace "from ml import *"
# Es una convencion de Python, no obligatorio pero buena practica
__all__ = ["MLFacade", "MLConfig", "load_ml_config"]
