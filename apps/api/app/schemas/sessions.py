from datetime import datetime

from pydantic import BaseModel


class GuestSessionResponse(BaseModel):
    token: str
    session_id: str
    created_at: datetime
    expires_at: datetime | None = None
