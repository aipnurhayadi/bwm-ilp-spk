from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.seed import DEFAULT_DATASET_NAME, seed_demo_dataset
from app.models.scheduling import Dataset
from app.schemas.scheduling import AssignmentRead, BwmSimulationRequest, BwmSimulationResponse
from app.services.bwm_ilp import run_bwm_ilp

router = APIRouter()


async def _resolve_dataset(
    session: AsyncSession,
    *,
    payload: BwmSimulationRequest,
) -> Dataset:
    if payload.dataset_id is not None:
        dataset = await session.get(Dataset, payload.dataset_id)
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        if payload.force_seed:
            dataset = await seed_demo_dataset(session, dataset_name=dataset.name, force_reset=True)
        return dataset

    dataset_name = payload.dataset_name or DEFAULT_DATASET_NAME
    dataset = await seed_demo_dataset(session, dataset_name=dataset_name, force_reset=payload.force_seed)
    return dataset


@router.post("/simulate", response_model=BwmSimulationResponse, status_code=status.HTTP_200_OK)
async def simulate_bwm_ilp(
    payload: BwmSimulationRequest,
    db: AsyncSession = Depends(get_db),
) -> BwmSimulationResponse:
    dataset = await _resolve_dataset(db, payload=payload)
    result = await run_bwm_ilp(db, dataset.id)
    return BwmSimulationResponse(
        dataset_id=result.dataset_id,
        dataset_name=result.dataset_name,
        objective_value=result.objective_value,
        soft_constraint_totals=result.soft_constraint_totals,
        assignments=[
            AssignmentRead(
                class_id=assignment.class_id,
                course_code=assignment.course_code,
                course_name=assignment.course_name,
                cohort_id=assignment.cohort_id,
                lecturer=assignment.lecturer,
                lecturer_code=assignment.lecturer_code,
                room_code=assignment.room_code,
                building=assignment.building,
                day=assignment.day,
                start_time=assignment.start_time,
                end_time=assignment.end_time,
                penalty=assignment.penalty,
                penalty_breakdown=assignment.penalty_breakdown,
            )
            for assignment in result.assignments
        ],
    )
