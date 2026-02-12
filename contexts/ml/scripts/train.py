#!/usr/bin/env python
"""
=============================================================================
SCRIPT DE ENTRENAMIENTO DE MODELOS ML
=============================================================================

Este script entrena un modelo Isolation Forest con los datos actuales.

CUANDO EJECUTAR:
----------------
- Manualmente cuando quieras entrenar un nuevo modelo
- Por un cron job (ej: semanal)
- Despues de acumular nuevos datos

USO:
----
    # Desde el directorio raiz del proyecto
    python -m contexts.ml.scripts.train

    # Con opciones
    python -m contexts.ml.scripts.train --version v2 --activate

    # Ver ayuda
    python -m contexts.ml.scripts.train --help


LECCION DE PYTHON #15: if __name__ == "__main__"
-------------------------------------------------
Este patron permite que un archivo sea:
1. Importado como modulo (sin ejecutar nada)
2. Ejecutado como script (ejecuta main())

    # Como modulo
    from contexts.ml.scripts.train import TrainScript  # No ejecuta main()

    # Como script
    python -m contexts.ml.scripts.train  # Ejecuta main()

En Go seria como tener un cmd/train/main.go separado.


LECCION DE PYTHON #16: argparse
--------------------------------
argparse es la libreria estandar para parsear argumentos CLI.

    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v1")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    print(args.version)   # "v1" o lo que pase el usuario
    print(args.activate)  # True si paso --activate

Es similar a la libreria flag de Go:
    version := flag.String("version", "v1", "Model version")
    flag.Parse()
"""

import argparse
import sys
import traceback

from dotenv import load_dotenv

HANDLED_TRAIN_INIT_ERRORS = (ImportError, ValueError, RuntimeError, OSError, KeyError)
HANDLED_TRAIN_EXEC_ERRORS = (ValueError, RuntimeError, OSError, KeyError)


def main():
    """
    Funcion principal del script.
    """
    # Parsear argumentos
    parser = argparse.ArgumentParser(
        description="Entrena un modelo Isolation Forest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    # Entrenar con version automatica
    python -m contexts.ml.scripts.train

    # Entrenar y activar
    python -m contexts.ml.scripts.train --activate

    # Entrenar con version especifica
    python -m contexts.ml.scripts.train --version v2_experiment --activate

    # Cambiar hiperparametros
    python -m contexts.ml.scripts.train --contamination 0.1 --n-estimators 200
        """,
    )

    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Version del modelo (default: v1_YYYYMMDD_HHMMSS)",
    )

    parser.add_argument(
        "--activate",
        action="store_true",
        help="Marcar como version activa despues de entrenar",
    )

    parser.add_argument(
        "--contamination",
        type=float,
        default=None,
        help="Override de contamination (default: 0.05)",
    )

    parser.add_argument(
        "--n-estimators",
        type=int,
        default=None,
        help="Override de n_estimators (default: 100)",
    )

    args = parser.parse_args()

    # Cargar variables de entorno
    load_dotenv()

    # Imports despues de load_dotenv para que las variables esten disponibles
    from app.config import load_settings
    from contexts.ml import MLFacade

    print("=" * 60)
    print("ENTRENAMIENTO DE MODELO ML")
    print("=" * 60)
    print()

    # Cargar configuracion
    settings = load_settings()

    # Verificar que ML esta habilitado
    if not settings.ml_enabled:
        print("[WARN] ML_ENABLED=false en configuracion.")
        print("       Activando temporalmente para entrenar...")
        # Continuamos de todos modos

    # Crear facade
    print("[1/4] Inicializando componentes...")
    try:
        ml = MLFacade.from_settings(settings)
    except HANDLED_TRAIN_INIT_ERRORS as e:
        print(f"[ERROR] No se pudo inicializar ML: {e}")
        return 1

    # Preparar hiperparametros override
    hyperparameters = {}
    if args.contamination is not None:
        hyperparameters["contamination"] = args.contamination
    if args.n_estimators is not None:
        hyperparameters["n_estimators"] = args.n_estimators

    print(f"       Hiperparametros: {hyperparameters if hyperparameters else 'default'}")

    # Entrenar
    print()
    print("[2/4] Cargando datos de entrenamiento...")

    try:
        result = ml.train(
            version=args.version,
            activate=args.activate,
            hyperparameters=hyperparameters if hyperparameters else None,
        )
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1
    except HANDLED_TRAIN_EXEC_ERRORS as e:
        print(f"[ERROR] Error durante entrenamiento: {e}")
        traceback.print_exc()
        return 1

    # Resultados
    print()
    print("[3/4] Entrenamiento completado!")
    print()
    print(f"       Version: {result.model_info.version}")
    print(f"       Muestras: {result.model_info.n_samples_trained}")
    print(f"       Tiempo: {result.training_time_seconds:.2f}s")
    print(f"       Guardado en: {result.saved_path}")
    print()
    print("       Metricas:")
    for name, value in result.metrics.items():
        print(f"         - {name}: {value:.4f}")

    if args.activate:
        print()
        print("[4/4] Modelo activado para produccion!")
    else:
        print()
        print("[4/4] Modelo guardado (NO activado)")
        print()
        print("       Para activar, ejecuta con --activate o edita:")
        print(f"       ml_models/isolation_forest/active.txt -> {result.model_info.version}")

    print()
    print("=" * 60)
    print("ENTRENAMIENTO EXITOSO")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
