from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


Intent = Literal[
    "sql", "rag", "renovation", "report", "parse_floorplan", "web", "mixed", "unknown"
]


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str


class PlanStep(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    source_id: str
    snippet: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    text: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Citation] = Field(default_factory=list)


class GraphState(BaseModel):
    messages: List[Message] = Field(default_factory=list)
    intent: Intent = "unknown"
    plan: List[PlanStep] = Field(default_factory=list)
    result: Optional[AgentResult] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    # index of the current step in plan (managed by the driver)
    plan_idx: int = 0
