from datetime import datetime, timezone
from typing import Any

from app.core.database import connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_user_id_by_auth(auth_user_id: str) -> str | None:
    """Resolve a Supabase auth user id to the app-level users.id (owner id)."""
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            "SELECT id FROM public.users WHERE auth_user_id = %s",
            (auth_user_id,),
        )
        record = await row.fetchone()
        return str(record[0]) if record else None


async def upsert_user(
    auth_user_id: str,
    email: str,
    name: str | None,
) -> dict[str, Any] | None:
    """Create or update the app-level `users` row linked to a Supabase Auth identity."""
    async with connection() as conn:
        if conn is None:
            return None
        name = (name or "").strip() or "Learner"
        now = _now_iso()
        row = await conn.execute(
            """
            INSERT INTO public.users (auth_user_id, email, name, is_onboarded, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (auth_user_id) DO UPDATE
              SET email = EXCLUDED.email,
                  name = EXCLUDED.name,
                  updated_at = EXCLUDED.updated_at
            RETURNING id, auth_user_id, email, name, is_onboarded, created_at, updated_at
            """,
            (auth_user_id, email, name, False, now, now),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "authUserId": record[1],
            "email": record[2],
            "name": record[3],
            "isOnboarded": record[4],
            "createdAt": record[5].isoformat(),
            "updatedAt": record[6].isoformat(),
        }


async def get_user_by_auth_id(auth_user_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, auth_user_id, email, name, is_onboarded, created_at, updated_at
            FROM public.users
            WHERE auth_user_id = %s
            """,
            (auth_user_id,),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "authUserId": record[1],
            "email": record[2],
            "name": record[3],
            "isOnboarded": record[4],
            "createdAt": record[5].isoformat(),
            "updatedAt": record[6].isoformat(),
        }
