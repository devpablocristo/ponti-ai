"""
=============================================================================
ML DOMAIN LAYER - ENTIDADES PURAS
=============================================================================

Este modulo contiene las entidades del dominio de ML.
Son clases "puras" que NO dependen de librerias externas (sklearn, pandas, etc).

PRINCIPIO: Domain Layer sin dependencias externas
--------------------------------------------------
Las entidades del dominio son el "nucleo" de tu logica.
No deben depender de:
- Frameworks (FastAPI, Flask)
- Librerias de BD (psycopg, sqlalchemy)
- Librerias de ML (sklearn, xgboost)

Por que? Porque si cambias de sklearn a pytorch, no quieres
reescribir tu logica de negocio.

ENTIDADES EN ESTE MODULO:
-------------------------
- Dataset: Representa un conjunto de datos para entrenar
- Prediction: Resultado de una prediccion del modelo
- ModelInfo: Metadata sobre un modelo entrenado
"""

from contexts.ml.domain.entities import Dataset, Prediction, ModelInfo

__all__ = ["Dataset", "Prediction", "ModelInfo"]
