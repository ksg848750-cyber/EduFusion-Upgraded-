from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection


async def append_event(
    learner_id: str,
    subject_id: str,
    event_type: str,
    entity_type: str = "",
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append an immutable learning event to the activity timeline."""
    async with connection() as conn:
        if conn is None:
            return
        await conn.execute(
            """
            INSERT INTO public.learning_events
              (learner_id, subject_id, event_type, entity_type, entity_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                learner_id,
                subject_id,
                event_type,
                entity_type,
                entity_id,
                Jsonb(metadata or {}),
            ),
        )