"""
=============================================================================
ML ADAPTERS
=============================================================================

Los adapters son implementaciones concretas de los ports.

ESTRUCTURA:
-----------
adapters/
├── training/     # Componentes para entrenar modelos (offline)
│   ├── postgres_data_loader.py
│   ├── sklearn_trainer.py
│   └── ...
└── inference/    # Componentes para prediccion (online)
    ├── sklearn_predictor.py
    └── ...

POR QUE SEPARAR TRAINING E INFERENCE:
-------------------------------------
1. Dependencias diferentes:
   - Training: puede usar pandas, grandes datasets
   - Inference: debe ser ligero y rapido

2. Contextos diferentes:
   - Training: corre en scripts offline
   - Inference: corre en la API

3. Requerimientos diferentes:
   - Training: puede ser lento (minutos)
   - Inference: debe ser rapido (<100ms)
"""

# Adapters se importan directamente cuando se necesitan
# No los exponemos aqui para evitar cargar dependencias innecesarias
