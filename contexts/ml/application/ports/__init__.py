"""
=============================================================================
ML PORTS (INTERFACES)
=============================================================================

LECCION DE PYTHON #6: Protocol vs ABC
--------------------------------------
Python tiene dos formas de definir "interfaces":

1. ABC (Abstract Base Class):
    from abc import ABC, abstractmethod

    class MiInterface(ABC):
        @abstractmethod
        def metodo(self) -> int:
            pass

    # Error si no implementas todos los metodos abstractos

2. Protocol (Structural Typing):
    from typing import Protocol

    class MiInterface(Protocol):
        def metodo(self) -> int:
            ...

    # No necesitas heredar, solo implementar los metodos

CUAL USAR:
- ABC: Cuando quieres forzar herencia explicita
- Protocol: Cuando quieres duck typing (como interfaces en Go)

En este proyecto usamos Protocol porque:
- Es mas flexible
- Es mas parecido a Go
- No requiere herencia explicita


LECCION DE PYTHON #7: Duck Typing
---------------------------------
"Si camina como pato y hace cuac como pato, es un pato"

En Go:
    type Reader interface {
        Read(p []byte) (n int, err error)
    }
    // Cualquier struct que tenga Read() implementa Reader

En Python con Protocol:
    class Reader(Protocol):
        def read(self, n: int) -> bytes:
            ...
    # Cualquier clase que tenga read() "implementa" Reader
"""

from contexts.ml.application.ports.data_loader import DataLoaderPort
from contexts.ml.application.ports.model_trainer import ModelTrainerPort
from contexts.ml.application.ports.model_store import ModelStorePort
from contexts.ml.application.ports.feature_engineer import FeatureEngineerPort

__all__ = [
    "DataLoaderPort",
    "ModelTrainerPort",
    "ModelStorePort",
    "FeatureEngineerPort",
]
