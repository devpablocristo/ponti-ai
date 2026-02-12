"""
=============================================================================
ML USE CASES
=============================================================================

Los use cases encapsulan la logica de negocio de ML.
Cada use case representa una "accion" que el sistema puede hacer.

USE CASES EN ESTE MODULO:
-------------------------
- TrainModel: Entrena un modelo con datos historicos
- PredictAnomaly: Detecta anomalias en datos nuevos

PATRON: Use Case / Interactor
-----------------------------
Un use case:
1. Recibe input (datos, configuracion)
2. Coordina multiples componentes (data loader, trainer, store)
3. Retorna output (resultado, errores)

No contiene:
- Logica de acceso a datos (eso va en adapters)
- Logica de presentacion (eso va en API)

En Go, esto seria similar a un "Service" en Clean Architecture.
"""

from contexts.ml.application.use_cases.train_model import TrainModelUseCase
from contexts.ml.application.use_cases.predict_anomaly import PredictAnomalyUseCase

__all__ = ["TrainModelUseCase", "PredictAnomalyUseCase"]
