"""EduFusion migration runner.

Applies the ordered SQL migration files under ``backend/sql/migrations`` to the
configured database (from ``DATABASE_URL`` in ``.env``), tracking applied
migrations in the ``schema_migrations`` table so they are applied exactly once.

Usage (run from ``backend/``):

    .venv/Scripts/python.exe -m scripts.run_migrations
    .venv/Scripts/python.exe -X utf8 -m scripts.run_migrations   (Windows)

Migrations are applied inside a transaction each. The files themselves use
idempotent ``IF NOT EXISTS`` / ``ADD COLUMN IF NOT EXISTS`` guards, so a partial
or manual application does not cause failures on a subsequent run.
"""

import asyncio
import selectors
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "migrations"


async def _apply(loop: asyncio.AbstractEventLoop) -> None:
    from app.core import database

    await database.init_pool()
    try:
        async with database.connection() as conn:
            if conn is None:
                print("ERROR: no database connection (DATABASE_URL unset).", file=sys.stderr)
                sys.exit(1)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    name       text primary key,
                    applied_at timestamptz not null default now()
                )
                """
            )

            files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            applied = []
            for path in files:
                row = await conn.execute(
                    "SELECT 1 FROM public.schema_migrations WHERE name = %s", (path.name,)
                )
                if await row.fetchone():
                    print(f"skip  {path.name} (already applied)")
                    continue
                sql = path.read_text(encoding="utf-8")
                try:
                    async with conn.transaction():
                        await conn.execute(sql)
                        await conn.execute(
                            "INSERT INTO public.schema_migrations (name) VALUES (%s)",
                            (path.name,),
                        )
                except Exception as exc:  # noqa: BLE001
                    print(f"FAIL  {path.name}: {exc}", file=sys.stderr)
                    sys.exit(1)
                applied.append(path.name)
                print(f"apply {path.name}")

            if not applied:
                print("No pending migrations.")
            else:
                print(f"Applied {len(applied)} migration(s).")
    finally:
        await database.close_pool()


def main() -> None:
    loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
    try:
        loop.run_until_complete(_apply(loop))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
