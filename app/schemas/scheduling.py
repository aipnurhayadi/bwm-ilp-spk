from __future__ import annotations

from datetime import time
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class BwmSimulationRequest(BaseModel):
    dataset_id: Optional[int] = Field(default=None, description="Existing dataset to simulate")
    dataset_name: Optional[str] = Field(default=None, description="Dataset name for seeding or lookup")
    force_seed: bool = Field(default=False, description="Recreate the demo dataset before simulation")


class AssignmentRead(BaseModel):
    class_id: int
    course_code: str
    course_name: str
    cohort_id: str
    lecturer: str
    lecturer_code: str
    room_code: str
    building: str
    day: str
    start_time: time
    end_time: time
    penalty: float
    penalty_breakdown: Dict[str, float]


class BwmSimulationResponse(BaseModel):
    dataset_id: int
    dataset_name: str
    objective_value: float
    soft_constraint_totals: Dict[str, float]
    solver_status: Literal["FEASIBLE", "NOT FEASIBLE"]
    status: Literal["OPTIMAL", "NOT OPTIMAL"]
    time_execution: float = Field(description="Solver runtime in seconds")
    assignments: List[AssignmentRead]


__all__ = [
    "AssignmentRead",
    "BwmSimulationRequest",
    "BwmSimulationResponse",
]
