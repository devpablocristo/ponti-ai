#!/usr/bin/env python3
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

import numpy as np
from dotenv import load_dotenv

DEFAULT_ROOT = Path(__file__).parent.parent
ROOT_DIR = Path("/app") if Path("/app").exists() else DEFAULT_ROOT
sys.path.insert(0, str(ROOT_DIR))

from app.config import load_settings  # noqa: E402
from contexts.ml import MLFacade  # noqa: E402
from contexts.ml.application.use_cases.predict_anomaly import PredictAnomalyUseCase  # noqa: E402
from contexts.ml.domain.entities import Dataset  # noqa: E402

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None


@dataclass
class EvalConfig:
    retrain: bool
    min_samples: int
    min_alert_rate: float
    max_alert_rate: float
    min_labeled_samples: int
    min_precision: float
    min_recall: float
    output_json: str | None


def parse_args() -> EvalConfig:
    parser = argparse.ArgumentParser(
        description="Evalua si el modulo ML cumple umbrales MVP para deteccion de anomalias.",
    )
    parser.add_argument("--retrain", action="store_true", help="Reentrena y activa una version antes de evaluar.")
    parser.add_argument("--min-samples", type=int, default=10, help="Minimo de muestras para evaluar.")
    parser.add_argument("--min-alert-rate", type=float, default=0.01, help="Tasa minima de alertas esperada.")
    parser.add_argument("--max-alert-rate", type=float, default=0.35, help="Tasa maxima de alertas aceptable.")
    parser.add_argument(
        "--min-labeled-samples",
        type=int,
        default=20,
        help="Minimo de labels de feedback para evaluar precision/recall.",
    )
    parser.add_argument(
        "--min-precision",
        type=float,
        default=0.60,
        help="Precision minima aceptable cuando hay labels suficientes.",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.40,
        help="Recall minimo aceptable cuando hay labels suficientes.",
    )
    parser.add_argument("--output-json", type=str, default=None, help="Path opcional para guardar reporte JSON.")
    args = parser.parse_args()
    return EvalConfig(
        retrain=bool(args.retrain),
        min_samples=max(1, int(args.min_samples)),
        min_alert_rate=float(args.min_alert_rate),
        max_alert_rate=float(args.max_alert_rate),
        min_labeled_samples=max(1, int(args.min_labeled_samples)),
        min_precision=float(args.min_precision),
        min_recall=float(args.min_recall),
        output_json=args.output_json,
    )


def _slice_dataset(dataset: Dataset, index: int) -> Dataset:
    return Dataset(
        features={name: [values[index]] for name, values in dataset.features.items()},
        sample_ids=(dataset.sample_ids[index],),
        created_at=dataset.created_at,
        metadata=dict(dataset.metadata or {}),
    )


def _compute_label_metrics(pairs: list[tuple[float, int]], threshold: float) -> dict[str, float]:
    tp = fp = fn = tn = 0
    for score, label in pairs:
        pred = 1 if score >= threshold else 0
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 1:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "labeled_samples": float(len(pairs)),
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
        "tn": float(tn),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def _load_feedback_pairs(db_dsn: str) -> list[tuple[float, int]]:
    if psycopg is None:
        return []
    query = """
    SELECT
        (i.evidence_json->>'anomaly_score')::float AS score,
        CASE
            WHEN a.action IN ('acknowledged', 'resolved') THEN 1
            WHEN a.action = 'dismissed' THEN 0
            ELSE NULL
        END AS label
    FROM ai_insights i
    JOIN ai_insight_actions a ON a.insight_id = i.id
    WHERE i.evidence_json ? 'anomaly_score'
      AND (i.rules_version LIKE 'ml_%' OR i.model_version LIKE 'ml-%')
      AND a.action IN ('acknowledged', 'resolved', 'dismissed')
      AND i.status <> 'deleted'
    """
    pairs: list[tuple[float, int]] = []
    with psycopg.connect(db_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            for row in cur.fetchall():
                score = row.get("score")
                label = row.get("label")
                if score is None or label is None:
                    continue
                pairs.append((float(score), int(label)))
    return pairs


def main() -> int:
    cfg = parse_args()
    load_dotenv()
    settings = load_settings()

    if not settings.ml_enabled:
        print("FAIL ML esta deshabilitado (ML_ENABLED=false)")
        return 1

    facade = MLFacade.from_settings(settings)
    report: dict[str, object] = {
        "gates": [],
        "status": "ok",
    }
    gates: list[str] = []

    if cfg.retrain:
        retrain_result = facade.retrain_with_policy(force_activate=True)
        report["retrain"] = retrain_result

    if not facade.has_active_model:
        print("FAIL No hay modelo activo para evaluar")
        return 1

    active_version = facade.active_version
    model_info = facade._model_store.get_model_info(facade.config.model_type, active_version)  # noqa: SLF001
    if model_info is None:
        print("FAIL No se pudo cargar metadata del modelo activo")
        return 1

    threshold = float(model_info.metrics.get("calibrated_threshold", facade.config.thresholds.anomaly_threshold))

    dataset = facade._data_loader.load_training_data()  # noqa: SLF001
    if dataset.n_samples < cfg.min_samples:
        print(f"FAIL Muestras insuficientes: {dataset.n_samples} < {cfg.min_samples}")
        return 1

    predictor = PredictAnomalyUseCase(config=facade.config, model_store=facade._model_store)  # noqa: SLF001

    scores: list[float] = []
    for i in range(dataset.n_samples):
        row_dataset = _slice_dataset(dataset, i)
        prediction_result = predictor.execute(row_dataset)
        if prediction_result is None:
            print("FAIL No hay modelo cargado para prediccion")
            return 1
        scores.append(float(prediction_result.prediction.anomaly_score))

    scores_arr = np.asarray(scores, dtype=float)
    alert_rate = float(np.mean(scores_arr >= threshold))
    snapshot_metrics = {
        "samples": int(dataset.n_samples),
        "threshold_used": float(threshold),
        "score_mean": float(np.mean(scores_arr)),
        "score_std": float(np.std(scores_arr)),
        "score_p90": float(np.percentile(scores_arr, 90)),
        "score_p95": float(np.percentile(scores_arr, 95)),
        "score_p99": float(np.percentile(scores_arr, 99)),
        "alert_rate": float(alert_rate),
    }

    if alert_rate < cfg.min_alert_rate:
        gates.append(
            f"alert_rate demasiado baja ({alert_rate:.4f} < {cfg.min_alert_rate:.4f}); posible modelo ciego."
        )
    if alert_rate > cfg.max_alert_rate:
        gates.append(
            f"alert_rate demasiado alta ({alert_rate:.4f} > {cfg.max_alert_rate:.4f}); posible exceso de ruido."
        )

    feedback_pairs = _load_feedback_pairs(settings.db_dsn)
    feedback_metrics: dict[str, float] = {}
    if feedback_pairs:
        feedback_metrics = _compute_label_metrics(feedback_pairs, threshold)
        if len(feedback_pairs) >= cfg.min_labeled_samples:
            if feedback_metrics["precision"] < cfg.min_precision:
                gates.append(
                    f"precision baja ({feedback_metrics['precision']:.4f} < {cfg.min_precision:.4f}) en labels reales."
                )
            if feedback_metrics["recall"] < cfg.min_recall:
                gates.append(
                    f"recall baja ({feedback_metrics['recall']:.4f} < {cfg.min_recall:.4f}) en labels reales."
                )

    training_metrics = {
        "version": model_info.version,
        "n_samples_trained": int(model_info.n_samples_trained),
        "trained_at": model_info.trained_at.isoformat(),
        "backtest_alert_rate_at_threshold": float(model_info.metrics.get("backtest_alert_rate_at_threshold", -1.0)),
        "anomaly_rate_train": float(model_info.metrics.get("anomaly_rate", -1.0)),
        "avg_score_train": float(model_info.metrics.get("avg_score", -1.0)),
    }

    report["training"] = training_metrics
    report["snapshot"] = snapshot_metrics
    report["feedback"] = feedback_metrics
    report["status"] = "fail" if gates else "ok"
    report["gates"] = gates
    report["summary"] = {
        "active_version": active_version,
        "threshold": threshold,
        "samples_scored": int(dataset.n_samples),
        "mean_score": float(mean(scores)),
        "alert_rate": alert_rate,
        "feedback_samples": len(feedback_pairs),
    }

    print("=" * 70)
    print("ML MVP EVALUATION")
    print("=" * 70)
    print(f"Modelo activo: {active_version}")
    print(f"Muestras evaluadas: {dataset.n_samples}")
    print(f"Threshold: {threshold:.4f}")
    print(f"Alert rate snapshot: {alert_rate:.4f}")
    if feedback_pairs:
        print(
            "Feedback: "
            f"samples={len(feedback_pairs)} "
            f"precision={feedback_metrics.get('precision', 0.0):.4f} "
            f"recall={feedback_metrics.get('recall', 0.0):.4f} "
            f"f1={feedback_metrics.get('f1', 0.0):.4f}"
        )
    else:
        print("Feedback: sin etiquetas aun (se salta gate de precision/recall).")

    if cfg.output_json:
        output_path = Path(cfg.output_json)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True))
        print(f"Reporte JSON: {output_path}")

    if gates:
        print("\nGATES FALLIDOS:")
        for gate in gates:
            print(f"- {gate}")
        return 1

    print("\nEstado MVP IA: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
