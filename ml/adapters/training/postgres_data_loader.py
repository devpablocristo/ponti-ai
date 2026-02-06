"""
=============================================================================
ADAPTER: POSTGRES DATA LOADER
=============================================================================

Carga datos de PostgreSQL para entrenar modelos.

LECCION DE PYTHON #10: Context Managers (with)
----------------------------------------------
En Go usas defer para cerrar recursos:

    db, err := sql.Open(...)
    defer db.Close()

En Python usas "with":

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    # El cursor se cierra automaticamente aqui

El "with" llama a __enter__ al inicio y __exit__ al final.
Es mas seguro que defer porque es garantizado incluso con excepciones.


LECCION DE SQL #1: CTEs (Common Table Expressions)
--------------------------------------------------
CTEs son "tablas temporales" dentro de una query:

    WITH usuarios_activos AS (
        SELECT * FROM usuarios WHERE activo = true
    ),
    compras_recientes AS (
        SELECT * FROM compras WHERE fecha > '2024-01-01'
    )
    SELECT *
    FROM usuarios_activos u
    JOIN compras_recientes c ON c.usuario_id = u.id

Beneficios:
- Mas legible que subqueries anidados
- Puedes reusar la misma CTE multiples veces
- El optimizador puede materializarlas
"""

from datetime import datetime, timezone

from ml.domain.entities import Dataset
from ml.config import MLConfig
from adapters.outbound.sql.catalog import list_feature_entries

# Importamos tipos para type hints pero sin instanciar
# Esto evita errores si la libreria no esta instalada
try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None  # type: ignore


class PostgresDataLoader:
    """
    Carga datos de PostgreSQL.

    Implementa DataLoaderPort.
    """

    def __init__(self, dsn: str, ml_config: MLConfig) -> None:
        """
        Inicializa el loader.

        Args:
            dsn: Connection string de PostgreSQL
                 (ej: "postgresql://user:pass@host:5432/db")
            ml_config: Configuracion ML (para saber que features cargar)
        """
        self.dsn = dsn
        self.ml_config = ml_config

    def load_training_data(self) -> Dataset:
        """
        Carga features de todos los proyectos.

        Usa el mismo catalogo SQL de feature_repo para evitar
        training-serving skew.
        """
        if psycopg is None:
            raise RuntimeError("psycopg no esta instalado")

        with psycopg.connect(self.dsn) as conn:
            project_ids = self._fetch_project_ids(conn)
            rows = self._load_feature_rows(conn, project_ids)

        return self._rows_to_dataset(rows, ["project_id", "feature_name", "value"])

    def load_inference_data(self, sample_id: str) -> Dataset:
        """
        Carga features de UN proyecto.

        Optimizado para ser rapido (usado en API).
        """
        if psycopg is None:
            raise RuntimeError("psycopg no esta instalado")

        with psycopg.connect(self.dsn) as conn:
            rows = self._load_feature_rows(conn, [sample_id])
        return self._rows_to_dataset(rows, ["project_id", "feature_name", "value"])

    def load_labeled_data(self) -> Dataset:
        """
        Carga datos con etiquetas de feedback de usuarios.

        Las etiquetas vienen de ai_insight_actions:
        - acknowledged/resolved -> label=1 (era anomalia real)
        - dismissed -> label=0 (falso positivo)
        """
        query = """
        WITH labeled AS (
            SELECT
                i.project_id,
                i.evidence_json->>'feature' AS feature_name,
                (i.evidence_json->>'value')::float AS value,
                CASE
                    WHEN a.action IN ('acknowledged', 'resolved') THEN 1
                    WHEN a.action = 'dismissed' THEN 0
                END AS label
            FROM ai_insights i
            JOIN ai_insight_actions a ON a.insight_id = i.id
            WHERE a.action IN ('acknowledged', 'resolved', 'dismissed')
        )
        SELECT * FROM labeled WHERE label IS NOT NULL
        """

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

        return self._rows_to_dataset(rows, columns)

    def suggest_anomaly_threshold(self, default_threshold: float) -> float | None:
        """
        Sugiere threshold usando feedback historico de usuarios.

        Usa insights ML con anomaly_score en evidence_json y acciones:
        - acknowledged/resolved => label 1
        - dismissed => label 0
        """
        if psycopg is None:
            return None

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
        """

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                rows = cur.fetchall()

        pairs: list[tuple[float, int]] = []
        for row in rows:
            score = row.get("score")
            label = row.get("label")
            if score is None or label is None:
                continue
            pairs.append((float(score), int(label)))

        if len(pairs) < 20:
            return None

        positives = sum(1 for _, label in pairs if label == 1)
        negatives = sum(1 for _, label in pairs if label == 0)
        if positives < 5 or negatives < 5:
            return None

        scores_sorted = sorted(score for score, _ in pairs)
        candidates: list[float] = []
        for idx in range(1, 20):
            pos = int((idx / 20.0) * (len(scores_sorted) - 1))
            candidates.append(scores_sorted[pos])
        candidates.append(float(default_threshold))
        candidates = sorted(set(max(0.01, min(0.99, value)) for value in candidates))

        best_threshold = float(default_threshold)
        best_f1 = -1.0
        for threshold in candidates:
            tp = fp = fn = 0
            for score, label in pairs:
                predicted = 1 if score >= threshold else 0
                if predicted == 1 and label == 1:
                    tp += 1
                elif predicted == 1 and label == 0:
                    fp += 1
                elif predicted == 0 and label == 1:
                    fn += 1
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold

        return best_threshold

    def _fetch_project_ids(self, conn) -> list[str]:
        query = (
            "SELECT p.id::text AS project_id "
            "FROM public.projects p "
            "WHERE p.deleted_at IS NULL"
        )
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            return [str(row["project_id"]) for row in cur.fetchall() if row.get("project_id") is not None]

    def _load_feature_rows(self, conn, project_ids: list[str]) -> list[tuple[str, str, float]]:
        rows_out: list[tuple[str, str, float]] = []
        if not project_ids:
            return rows_out

        feature_entries = list_feature_entries()
        for project_id in project_ids:
            for entry in feature_entries:
                params = entry.validate_params({"project_id": project_id})
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(entry.sql_template, params)
                    rows = cur.fetchall()

                window = "all"
                if entry.query_id.endswith("_last_30d"):
                    window = "last_30d"
                elif entry.query_id.endswith("_last_7d"):
                    window = "last_7d"

                for row in rows:
                    entity_type = str(row.get("entity_type", "project"))
                    if entity_type != "project":
                        continue
                    feature_name = str(row.get("feature_name", entry.query_id))
                    value_raw = row.get("value", 0.0)
                    value = float(value_raw) if value_raw is not None else 0.0
                    row_project_id = str(row.get("project_id", project_id))
                    rows_out.append((row_project_id, f"{feature_name}_{window}", value))

        return rows_out

    def _rows_to_dataset(
        self,
        rows: list,
        columns: list[str],
    ) -> Dataset:
        """
        Convierte rows SQL a Dataset.

        El formato esperado de rows es:
            project_id | feature_name | value
            p1         | cost_total   | 1000
            p1         | hectares     | 50
            p2         | cost_total   | 2000
            ...

        Lo convertimos a formato Dataset:
            features = {
                "cost_total": [1000, 2000, ...],
                "hectares": [50, ...],
            }
            sample_ids = ("p1", "p2", ...)
        """
        # Encontrar indices de columnas
        try:
            project_idx = columns.index("project_id")
            feature_idx = columns.index("feature_name")
            value_idx = columns.index("value")
        except ValueError:
            # Columnas no encontradas, retornar dataset vacio
            return Dataset(
                features={},
                sample_ids=(),
                created_at=datetime.now(timezone.utc),
            )

        # Agrupar por proyecto
        project_features: dict[str, dict[str, float]] = {}

        for row in rows:
            project_id = str(row[project_idx])
            feature_name = str(row[feature_idx])
            value = float(row[value_idx]) if row[value_idx] is not None else 0.0

            if project_id not in project_features:
                project_features[project_id] = {}

            project_features[project_id][feature_name] = value

        # Convertir a formato Dataset
        sample_ids = tuple(project_features.keys())

        contract = [
            f"{feature_name}_{window}"
            for feature_name in self.ml_config.features.feature_names
            for window in self.ml_config.features.windows
        ]
        features: dict[str, list[float]] = {name: [] for name in contract}

        for project_id in sample_ids:
            proj_features = project_features[project_id]
            for name in features:
                # Si el proyecto no tiene este feature, usar 0
                features[name].append(proj_features.get(name, 0.0))

        return Dataset(
            features=features,
            sample_ids=sample_ids,
            created_at=datetime.now(timezone.utc),
            metadata={"source": "postgresql", "feature_contract": "features-v1"},
        )
