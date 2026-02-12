BEGIN;

SELECT setval(
  pg_get_serial_sequence('public.workorders', 'id'),
  COALESCE((SELECT MAX(id) FROM public.workorders), 1),
  true
);

SELECT setval(
  pg_get_serial_sequence('public.workorder_items', 'id'),
  COALESCE((SELECT MAX(id) FROM public.workorder_items), 1),
  true
);

INSERT INTO public.projects (id)
SELECT i FROM generate_series(4, 20) AS i
ON CONFLICT (id) DO NOTHING;

INSERT INTO v4_report.dashboard_management_balance (project_id, costos_directos_ejecutados_usd)
SELECT i, (18000 + i * 2200)::float
FROM generate_series(4, 20) AS i
ON CONFLICT (project_id) DO UPDATE SET
  costos_directos_ejecutados_usd = EXCLUDED.costos_directos_ejecutados_usd;

INSERT INTO v4_report.lot_metrics (project_id, direct_cost_total_usd, hectares)
SELECT i, (18000 + i * 2200)::float, (60 + (i % 7) * 15)::float
FROM generate_series(4, 20) AS i
ON CONFLICT (project_id) DO UPDATE SET
  direct_cost_total_usd = EXCLUDED.direct_cost_total_usd,
  hectares = EXCLUDED.hectares;

INSERT INTO v4_report.field_crop_insumos (project_id, total_insumos_usd)
SELECT i, (7000 + i * 900)::float
FROM generate_series(4, 20) AS i
ON CONFLICT (project_id) DO UPDATE SET
  total_insumos_usd = EXCLUDED.total_insumos_usd;

INSERT INTO v4_report.labor_metrics (project_id, total_workorders)
SELECT i, (8 + (i % 9) * 4)::float
FROM generate_series(4, 20) AS i
ON CONFLICT (project_id) DO UPDATE SET
  total_workorders = EXCLUDED.total_workorders;

INSERT INTO public.fields (project_id)
SELECT i FROM generate_series(4, 20) AS i;

INSERT INTO public.lots (field_id, hectares)
SELECT f.id, (40 + (f.project_id % 6) * 18)::float
FROM public.fields f
LEFT JOIN public.lots l ON l.field_id = f.id
WHERE f.project_id BETWEEN 4 AND 20 AND l.id IS NULL;

WITH new_workorders AS (
  INSERT INTO public.workorders (project_id, labor_id, effective_area, date)
  SELECT i, 1, (20 + (i % 8) * 6)::float, CURRENT_DATE - ((i % 20) || ' days')::interval
  FROM generate_series(4, 20) AS i
  WHERE NOT EXISTS (
    SELECT 1
    FROM public.workorders w
    WHERE w.project_id = i
      AND w.labor_id = 1
      AND w.date = CURRENT_DATE - ((i % 20) || ' days')::interval
      AND w.deleted_at IS NULL
  )
  RETURNING id, project_id
)
INSERT INTO public.workorder_items (workorder_id, total_used)
SELECT w.id, (500 + (w.project_id % 10) * 180)::float
FROM (
  SELECT id, project_id FROM new_workorders
  UNION ALL
  SELECT id, project_id
  FROM public.workorders
  WHERE project_id BETWEEN 4 AND 20
) AS w
LEFT JOIN public.workorder_items wi ON wi.workorder_id = w.id
WHERE wi.id IS NULL;

INSERT INTO public.stocks (project_id, real_stock_units, initial_units, deleted_at)
SELECT i, (120 + i * 4)::float, (100 + i * 3)::float, NULL
FROM generate_series(4, 20) AS i;

COMMIT;
