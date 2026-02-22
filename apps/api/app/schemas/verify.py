from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    task: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)


IssueType = Literal[
    "contradiction",
    "missing_owner",
    "missing_due_date",
    "vague",
    "missing_context",
    "other",
]


class Issue(BaseModel):
    type: IssueType
    description: str
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class VerifyResponse(BaseModel):
    structured_summary: str
    decisions: List[str] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    issues: List[Issue] = Field(default_factory=list)
    had_retry: bool = False
    invalid_reason_counts: Dict[str, int] = Field(default_factory=dict)
