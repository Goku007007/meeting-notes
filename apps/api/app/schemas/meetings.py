from pydantic import BaseModel
from datetime import datetime


class MeetingResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
