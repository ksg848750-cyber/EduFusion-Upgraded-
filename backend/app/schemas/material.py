from datetime import datetime

from pydantic import BaseModel


class MaterialResponse(BaseModel):
    id: str
    subjectId: str
    ownerId: str
    filename: str
    fileType: str
    storageReference: str
    processingStatus: str
    pageCount: int | None = None
    processingError: str | None = None
    createdAt: datetime
    updatedAt: datetime