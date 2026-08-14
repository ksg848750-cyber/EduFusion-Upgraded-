from datetime import datetime, timezone
from typing import Any

from app.core.database import connection


def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _material_row(record) -> dict[str, Any]:
    return {
        "id": str(record[0]),
        "subjectId": str(record[1]),
        "ownerId": str(record[2]),
        "filename": record[3],
        "fileType": record[4],
        "storageReference": record[5],
        "processingStatus": record[6],
        "pageCount": record[7],
        "processingError": record[8],
        "createdAt": _iso(record[9]),
        "updatedAt": _iso(record[10]),
    }


async def create_material(
    owner_id: str,
    subject_id: str,
    filename: str,
    file_type: str,
    storage_reference: str,
    processing_status: str = "UPLOADED",
) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        row = await conn.execute(
            """
            INSERT INTO public.materials
              (subject_id, owner_id, filename, file_type, storage_reference, processing_status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, subject_id, owner_id, filename, file_type, storage_reference,
                      processing_status, page_count, processing_error, created_at, updated_at
            """,
            (subject_id, owner_id, filename, file_type, storage_reference, processing_status, now, now),
        )
        record = await row.fetchone()
        return _material_row(record) if record else None


async def get_material(owner_id: str, material_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, subject_id, owner_id, filename, file_type, storage_reference,
                   processing_status, page_count, processing_error, created_at, updated_at
            FROM public.materials
            WHERE id = %s AND owner_id = %s
            """,
            (material_id, owner_id),
        )
        record = await row.fetchone()
        return _material_row(record) if record else None


async def list_materials(owner_id: str, subject_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT id, subject_id, owner_id, filename, file_type, storage_reference,
                   processing_status, page_count, processing_error, created_at, updated_at
            FROM public.materials
            WHERE owner_id = %s AND subject_id = %s
            ORDER BY created_at DESC
            """,
            (owner_id, subject_id),
        )
        return [_material_row(r) for r in await rows.fetchall()]


async def update_material_status(
    owner_id: str,
    material_id: str,
    status: str,
    processing_error: str | None = None,
    page_count: int | None = None,
) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        row = await conn.execute(
            """
            UPDATE public.materials
            SET processing_status = %s,
                processing_error = COALESCE(%s, processing_error),
                page_count = COALESCE(%s, page_count),
                updated_at = %s
            WHERE id = %s AND owner_id = %s
            RETURNING id, subject_id, owner_id, filename, file_type, storage_reference,
                      processing_status, page_count, processing_error, created_at, updated_at
            """,
            (status, processing_error, page_count, now, material_id, owner_id),
        )
        record = await row.fetchone()
        return _material_row(record) if record else None