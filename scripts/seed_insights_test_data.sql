-- Seed mínimo para probar insights en ai_copilot (sin Ponti completo)
-- Ejecutar: psql $DB_DSN -f scripts/seed_insights_test_data.sql

BEGIN;

-- Schemas
CREATE SCHEMA IF NOT EXISTS v4_report;
CREATE SCHEMA IF NOT EXISTS v4_ssot;

-- Proyectos (necesario para baselines)
CREATE TABLE IF NOT EXISTS public.projects (
    id BIGINT PRIMARY KEY,
    deleted_at TIMESTAMPTZ
);
INSERT INTO public.projects (id) VALUES (1), (2), (3) ON CONFLICT (id) DO NOTHING;

-- Función total_hectares_for_project (150, 80, 120 para proyectos 1,2,3)
CREATE OR REPLACE FUNCTION v4_ssot.total_hectares_for_project(pid BIGINT)
RETURNS FLOAT AS $$
    SELECT CASE pid WHEN 1 THEN 150.0 WHEN 2 THEN 80.0 WHEN 3 THEN 120.0 ELSE 100.0 END;
$$ LANGUAGE SQL STABLE;

-- Costos por proyecto (feature_cost_total)
CREATE TABLE IF NOT EXISTS v4_report.dashboard_management_balance (
    project_id BIGINT PRIMARY KEY,
    costos_directos_ejecutados_usd FLOAT
);
INSERT INTO v4_report.dashboard_management_balance (project_id, costos_directos_ejecutados_usd)
VALUES (1, 80000), (2, 25000), (3, 45000)
ON CONFLICT (project_id) DO UPDATE SET costos_directos_ejecutados_usd = EXCLUDED.costos_directos_ejecutados_usd;

-- Lot metrics (feature_cost_per_ha, baselines)
CREATE TABLE IF NOT EXISTS v4_report.lot_metrics (
    project_id BIGINT PRIMARY KEY,
    direct_cost_total_usd FLOAT,
    hectares FLOAT
);
INSERT INTO v4_report.lot_metrics (project_id, direct_cost_total_usd, hectares)
VALUES (1, 80000, 150), (2, 25000, 80), (3, 45000, 120)
ON CONFLICT (project_id) DO UPDATE SET direct_cost_total_usd = EXCLUDED.direct_cost_total_usd, hectares = EXCLUDED.hectares;

-- Field crop insumos (feature_inputs_usage)
CREATE TABLE IF NOT EXISTS v4_report.field_crop_insumos (
    project_id BIGINT PRIMARY KEY,
    total_insumos_usd FLOAT
);
INSERT INTO v4_report.field_crop_insumos (project_id, total_insumos_usd)
VALUES (1, 35000), (2, 12000), (3, 20000)
ON CONFLICT (project_id) DO UPDATE SET total_insumos_usd = EXCLUDED.total_insumos_usd;

-- Labor metrics (feature_workorders_count)
CREATE TABLE IF NOT EXISTS v4_report.labor_metrics (
    project_id BIGINT PRIMARY KEY,
    total_workorders FLOAT
);
INSERT INTO v4_report.labor_metrics (project_id, total_workorders)
VALUES (1, 45), (2, 15), (3, 28)
ON CONFLICT (project_id) DO UPDATE SET total_workorders = EXCLUDED.total_workorders;

-- Stocks (feature_stock_variance)
CREATE TABLE IF NOT EXISTS public.stocks (
    project_id BIGINT,
    real_stock_units FLOAT,
    initial_units FLOAT,
    deleted_at TIMESTAMPTZ
);
INSERT INTO public.stocks (project_id, real_stock_units, initial_units)
VALUES (1, 100, 80), (2, 50, 45), (3, 75, 70);

-- Workorders (feature_cost_total_last_30d, last_7d, baselines)
DROP TABLE IF EXISTS public.workorder_items;
DROP TABLE IF EXISTS public.workorders;
CREATE TABLE public.workorders (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT,
    labor_id BIGINT,
    effective_area FLOAT,
    date DATE,
    deleted_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS public.workorder_items (
    id BIGSERIAL PRIMARY KEY,
    workorder_id BIGINT REFERENCES public.workorders(id),
    total_used FLOAT DEFAULT 0,
    deleted_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS public.labors (
    id BIGINT PRIMARY KEY,
    price FLOAT,
    deleted_at TIMESTAMPTZ
);
DROP TABLE IF EXISTS public.lots;
DROP TABLE IF EXISTS public.fields;
CREATE TABLE public.fields (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT,
    deleted_at TIMESTAMPTZ
);
CREATE TABLE public.lots (
    id BIGSERIAL PRIMARY KEY,
    field_id BIGINT REFERENCES public.fields(id),
    hectares FLOAT,
    deleted_at TIMESTAMPTZ
);

INSERT INTO public.labors (id, price) VALUES (1, 100) ON CONFLICT (id) DO NOTHING;
INSERT INTO public.fields (project_id) VALUES (1), (2), (3);
INSERT INTO public.lots (field_id, hectares) VALUES (1, 150), (2, 80), (3, 120);
INSERT INTO public.workorders (id, project_id, labor_id, effective_area, date)
VALUES (1, 1, 1, 100, CURRENT_DATE - INTERVAL '5 days'),
       (2, 2, 1, 30, CURRENT_DATE - INTERVAL '10 days'),
       (3, 3, 1, 60, CURRENT_DATE - INTERVAL '3 days');
INSERT INTO public.workorder_items (workorder_id, total_used)
VALUES (1, 5000), (2, 1500), (3, 3000);

COMMIT;
