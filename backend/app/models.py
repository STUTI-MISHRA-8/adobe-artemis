from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AEPLayer(str, Enum):
    schema_layer = "schema"
    dataset = "dataset"
    ingestion = "ingestion"
    modeling = "modeling"
    activation = "activation"
    governance = "governance"
    reporting = "reporting"
    general = "general"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class FlagType(str, Enum):
    clear = "clear"
    implicit = "implicit"
    ambiguous = "ambiguous"
    contradiction = "contradiction"
    assumption = "assumption"
    unclassified = "unclassified"


class Observation(BaseModel):
    obs_id: str
    text: str
    verbatim_quote: str = ""
    type: str = "explicit"
    section_title: str
    sec_id: str
    aep_relevance: AEPLayer = AEPLayer.general
    business_value: str = ""
    risk_if_missed: str = ""


class Requirement(BaseModel):
    req_id: str
    aep_layer: AEPLayer
    priority: Priority
    description: str = Field(max_length=500)
    source_obs: list[str] = []
    source_section: str
    sec_id: str
    flags: list[FlagType] = []
    dependencies: list[str] = []


class Task(BaseModel):
    task_id: str
    req_id: str
    title: str
    description: str
    aep_layer: AEPLayer
    priority: Priority
    phase: int
    dependencies: list[str] = []
    source_section: str
    acceptance_criteria: str = ""


class CoverageAudit(BaseModel):
    total_observations: int
    mapped_observations: int
    orphaned_observations: list[str]
    coverage_percent: float


class TraceNode(BaseModel):
    req_id: str
    description: str
    aep_layer: AEPLayer
    source_section: str
    observations: list[Observation]
    tasks: list[Task]


class AnalysisResult(BaseModel):
    job_id: str
    filename: str
    section_count: int
    observation_count: int
    requirement_count: int
    task_count: int
    coverage: CoverageAudit
    requirements: list[Requirement]
    tasks: list[Task]
    trace: list[TraceNode]
    sections: list[dict]


class JobStatus(str, Enum):
    queued = "queued"
    parsing = "parsing"
    extracting = "extracting"
    structuring = "structuring"
    planning = "planning"
    done = "done"
    error = "error"
