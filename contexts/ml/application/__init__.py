"""
=============================================================================
ML APPLICATION LAYER
=============================================================================

Este layer contiene:
- Ports: Interfaces que definen contratos (como interfaces en Go)
- Use Cases: Logica de negocio de ML

PRINCIPIO: Dependency Inversion
-------------------------------
Los use cases dependen de INTERFACES (ports), no de implementaciones.

Esto permite:
1. Testear con mocks/fakes
2. Cambiar implementaciones sin tocar logica
3. Separar "que hacer" de "como hacerlo"

Ejemplo:
    # El use case solo sabe que necesita un "model trainer"
    # No le importa si usa sklearn, pytorch o un servicio externo
    class TrainModel:
        def __init__(self, trainer: ModelTrainerPort):
            self.trainer = trainer

        def execute(self, dataset):
            return self.trainer.train(dataset)
"""

from contexts.ml.application.ports import (
    DataLoaderPort,
    ModelTrainerPort,
    ModelStorePort,
    FeatureEngineerPort,
)

__all__ = [
    "DataLoaderPort",
    "ModelTrainerPort",
    "ModelStorePort",
    "FeatureEngineerPort",
]
