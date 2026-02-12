from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import Settings

HANDLED_DB_HEALTH_ERRORS = (psycopg.Error, ValueError, OSError)


class DBSession:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @contextmanager
    def connect(self):
        if not self.settings.db_dsn:
            raise ValueError("DB_DSN no configurado")
        with psycopg.connect(self.settings.db_dsn, row_factory=dict_row) as conn:
            yield conn


def check_db_health(settings: Settings) -> bool:
    try:
        session = DBSession(settings)
        with session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except HANDLED_DB_HEALTH_ERRORS:
        return False
