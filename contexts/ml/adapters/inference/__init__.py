"""
=============================================================================
INFERENCE ADAPTERS
=============================================================================

Componentes optimizados para prediccion en la API.

DIFERENCIA VS TRAINING:
-----------------------
Training adapters:
- Pueden ser lentos (minutos)
- Cargan datasets grandes
- Usan muchas dependencias

Inference adapters:
- Deben ser rapidos (<100ms)
- Cargan una muestra a la vez
- Minimas dependencias

Por ahora, reutilizamos los adapters de training porque
son suficientemente rapidos. En el futuro, podrias:
- Pre-cargar modelos en memoria al iniciar
- Usar ONNX para inference mas rapido
- Separar dependencias (sklearn solo en training)
"""

# Por ahora no exportamos nada especifico
# Los use cases usan los adapters de training
