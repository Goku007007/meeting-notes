from pydantic import BaseModel


class MeetingResponse(BaseModel):
    id: str
    title: str
