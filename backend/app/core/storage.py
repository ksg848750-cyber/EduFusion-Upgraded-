import httpx

from app.core.config import get_settings


async def upload_bytes(
    bucket: str,
    path: str,
    content: bytes,
    content_type: str = "application/pdf",
) -> str:
    """Upload raw bytes to Supabase Storage. Returns the storage reference path.

    Uses the service-role key; never exposed to the frontend.
    """
    settings = get_settings()
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{path}"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(url, headers=headers, content=content)
        resp.raise_for_status()
    return path