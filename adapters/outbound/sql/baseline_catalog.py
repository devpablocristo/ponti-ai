from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineQuery:
    query_id: str
    feature_name: str
    window: str
    sql_template: str


_COHORT_QUERIES: list[BaselineQuery] = [
    BaselineQuery(
        query_id="cohort_cost_total_all",
        feature_name="cost_total",
        window="all",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT p.id AS project_id,
                 COALESCE(dmb.costos_directos_ejecutados_usd, 0) AS value
          FROM public.projects p
          LEFT JOIN v4_report.dashboard_management_balance dmb
            ON dmb.project_id = p.id
          WHERE p.deleted_at IS NULL
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'cost_total'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_cost_per_ha_all",
        feature_name="cost_per_ha",
        window="all",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            lm.project_id,
            COALESCE(SUM(lm.direct_cost_total_usd), 0) / NULLIF(SUM(lm.hectares), 0) AS value
          FROM v4_report.lot_metrics lm
          GROUP BY lm.project_id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'cost_per_ha'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_inputs_total_all",
        feature_name="inputs_total_used",
        window="all",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            project_id,
            COALESCE(SUM(total_insumos_usd), 0) AS value
          FROM v4_report.field_crop_insumos
          GROUP BY project_id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'inputs_total_used'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_workorders_count_all",
        feature_name="workorders_count",
        window="all",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT project_id, COALESCE(SUM(total_workorders), 0) AS value
          FROM v4_report.labor_metrics
          GROUP BY project_id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'workorders_count'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_stock_variance_all",
        feature_name="stock_variance",
        window="all",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            project_id,
            COALESCE(SUM(real_stock_units - initial_units), 0) AS value
          FROM public.stocks
          WHERE deleted_at IS NULL
          GROUP BY project_id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'stock_variance'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_total_hectares_all",
        feature_name="total_hectares",
        window="all",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT project_id, total_hectares AS value
          FROM project_base
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN fv.value IS NULL THEN 'size=unknown'
              WHEN fv.value <= %(size_small_max)s THEN 'size=small'
              WHEN fv.value <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'total_hectares'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_cost_total_last_30d",
        feature_name="cost_total",
        window="last_30d",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            p.id AS project_id,
            COALESCE(SUM(lb.price * w.effective_area), 0) AS value
          FROM public.projects p
          LEFT JOIN public.workorders w
            ON w.project_id = p.id
           AND w.deleted_at IS NULL
           AND w.effective_area > 0
           AND w.date >= (CURRENT_DATE - INTERVAL '30 days')
          LEFT JOIN public.labors lb
            ON lb.id = w.labor_id AND lb.deleted_at IS NULL
          WHERE p.deleted_at IS NULL
          GROUP BY p.id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'cost_total'::text AS feature_name,
          'last_30d'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_cost_total_last_7d",
        feature_name="cost_total",
        window="last_7d",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            p.id AS project_id,
            COALESCE(SUM(lb.price * w.effective_area), 0) AS value
          FROM public.projects p
          LEFT JOIN public.workorders w
            ON w.project_id = p.id
           AND w.deleted_at IS NULL
           AND w.effective_area > 0
           AND w.date >= (CURRENT_DATE - INTERVAL '7 days')
          LEFT JOIN public.labors lb
            ON lb.id = w.labor_id AND lb.deleted_at IS NULL
          WHERE p.deleted_at IS NULL
          GROUP BY p.id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'cost_total'::text AS feature_name,
          'last_7d'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_inputs_last_30d",
        feature_name="inputs_total_used",
        window="last_30d",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            p.id AS project_id,
            COALESCE(SUM(wi.total_used), 0) AS value
          FROM public.projects p
          LEFT JOIN public.workorders w
            ON w.project_id = p.id
           AND w.deleted_at IS NULL
           AND w.date >= (CURRENT_DATE - INTERVAL '30 days')
          LEFT JOIN public.workorder_items wi
            ON wi.workorder_id = w.id AND wi.deleted_at IS NULL
          WHERE p.deleted_at IS NULL
          GROUP BY p.id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'inputs_total_used'::text AS feature_name,
          'last_30d'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_inputs_last_7d",
        feature_name="inputs_total_used",
        window="last_7d",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            p.id AS project_id,
            COALESCE(SUM(wi.total_used), 0) AS value
          FROM public.projects p
          LEFT JOIN public.workorders w
            ON w.project_id = p.id
           AND w.deleted_at IS NULL
           AND w.date >= (CURRENT_DATE - INTERVAL '7 days')
          LEFT JOIN public.workorder_items wi
            ON wi.workorder_id = w.id AND wi.deleted_at IS NULL
          WHERE p.deleted_at IS NULL
          GROUP BY p.id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'inputs_total_used'::text AS feature_name,
          'last_7d'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_workorders_last_30d",
        feature_name="workorders_count",
        window="last_30d",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            p.id AS project_id,
            COUNT(w.id) AS value
          FROM public.projects p
          LEFT JOIN public.workorders w
            ON w.project_id = p.id
           AND w.deleted_at IS NULL
           AND w.date >= (CURRENT_DATE - INTERVAL '30 days')
          WHERE p.deleted_at IS NULL
          GROUP BY p.id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'workorders_count'::text AS feature_name,
          'last_30d'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="cohort_workorders_last_7d",
        feature_name="workorders_count",
        window="last_7d",
        sql_template="""
        WITH project_base AS (
          SELECT p.id AS project_id,
                 v4_ssot.total_hectares_for_project(p.id) AS total_hectares
          FROM public.projects p
          WHERE p.deleted_at IS NULL
        ),
        feature_values AS (
          SELECT
            p.id AS project_id,
            COUNT(w.id) AS value
          FROM public.projects p
          LEFT JOIN public.workorders w
            ON w.project_id = p.id
           AND w.deleted_at IS NULL
           AND w.date >= (CURRENT_DATE - INTERVAL '7 days')
          WHERE p.deleted_at IS NULL
          GROUP BY p.id
        ),
        cohort AS (
          SELECT
            fv.project_id,
            CASE
              WHEN pb.total_hectares IS NULL THEN 'size=unknown'
              WHEN pb.total_hectares <= %(size_small_max)s THEN 'size=small'
              WHEN pb.total_hectares <= %(size_medium_max)s THEN 'size=medium'
              ELSE 'size=large'
            END AS cohort_key,
            fv.value
          FROM feature_values fv
          JOIN project_base pb ON pb.project_id = fv.project_id
        )
        SELECT
          %(project_id)s::text AS project_id,
          cohort_key,
          'workorders_count'::text AS feature_name,
          'last_7d'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM cohort
        GROUP BY cohort_key
        LIMIT %(limit)s
        """,
    ),
]


_PROJECT_QUERIES: list[BaselineQuery] = [
    BaselineQuery(
        query_id="project_cost_total_history",
        feature_name="cost_total",
        window="all",
        sql_template="""
        WITH daily AS (
          SELECT
            w.date::date AS day,
            COALESCE(SUM(lb.price * w.effective_area), 0) AS value
          FROM public.workorders w
          JOIN public.labors lb ON lb.id = w.labor_id AND lb.deleted_at IS NULL
          WHERE w.project_id = %(project_id)s
            AND w.deleted_at IS NULL
            AND w.effective_area > 0
            AND w.date >= (CURRENT_DATE - (%(baseline_days)s || ' days')::interval)
          GROUP BY w.date::date
        )
        SELECT
          %(project_id)s::text AS project_id,
          'self'::text AS cohort_key,
          'cost_total'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM daily
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="project_inputs_history",
        feature_name="inputs_total_used",
        window="all",
        sql_template="""
        WITH daily AS (
          SELECT
            w.date::date AS day,
            COALESCE(SUM(wi.total_used), 0) AS value
          FROM public.workorders w
          JOIN public.workorder_items wi ON wi.workorder_id = w.id AND wi.deleted_at IS NULL
          WHERE w.project_id = %(project_id)s
            AND w.deleted_at IS NULL
            AND w.date >= (CURRENT_DATE - (%(baseline_days)s || ' days')::interval)
          GROUP BY w.date::date
        )
        SELECT
          %(project_id)s::text AS project_id,
          'self'::text AS cohort_key,
          'inputs_total_used'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM daily
        LIMIT %(limit)s
        """,
    ),
    BaselineQuery(
        query_id="project_workorders_history",
        feature_name="workorders_count",
        window="all",
        sql_template="""
        WITH daily AS (
          SELECT
            w.date::date AS day,
            COUNT(*) AS value
          FROM public.workorders w
          WHERE w.project_id = %(project_id)s
            AND w.deleted_at IS NULL
            AND w.date >= (CURRENT_DATE - (%(baseline_days)s || ' days')::interval)
          GROUP BY w.date::date
        )
        SELECT
          %(project_id)s::text AS project_id,
          'self'::text AS cohort_key,
          'workorders_count'::text AS feature_name,
          'all'::text AS window,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS p50,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
          percentile_cont(0.9) WITHIN GROUP (ORDER BY value) AS p90,
          COUNT(*) AS n_samples
        FROM daily
        LIMIT %(limit)s
        """,
    ),
]


PROJECT_LIST_SQL = """
SELECT %(project_id)s::text AS project_id, id
FROM public.projects
WHERE deleted_at IS NULL
  AND (%(start_after_id)s IS NULL OR id > %(start_after_id)s)
ORDER BY id
LIMIT %(limit)s
"""


def list_cohort_queries() -> list[BaselineQuery]:
    return _COHORT_QUERIES


def list_project_queries() -> list[BaselineQuery]:
    return _PROJECT_QUERIES
