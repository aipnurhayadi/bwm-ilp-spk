from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict, List, Mapping, Tuple

from fastapi import HTTPException, status
from ortools.linear_solver import pywraplp
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduling import (
    Class,
    Course,
    Dataset,
    Lecturer,
    PenaltyWeight,
    Preference,
    Room,
    ScheduleEntry,
    Timeslot,
)
from app.models.scheduling import Availability as AvailabilityModel
from app.models.scheduling import CourseEquipmentRequirement, Enrollment, RoomEquipment


@dataclass(frozen=True)
class ClassInfo:
    class_id: int
    course_id: int
    course_code: str
    course_name: str
    cohort_id: str
    capacity: int
    session_type: str
    requires_lab: bool
    needs_back_to_back: bool
    same_room_preferred: bool
    candidate_lecturers: tuple[int, ...]


@dataclass(frozen=True)
class RoomInfo:
    room_id: int
    room_code: str
    capacity: int
    room_type: str
    building: str
    equipment: Mapping[str, int]


@dataclass(frozen=True)
class TimeslotInfo:
    timeslot_id: int
    day: str
    start_time: Any
    end_time: Any
    is_peak: bool


@dataclass(frozen=True)
class LecturerInfo:
    lecturer_id: int
    lecturer_code: str
    name: str


@dataclass
class AssignmentResult:
    class_id: int
    course_code: str
    course_name: str
    cohort_id: str
    lecturer: str
    lecturer_code: str
    room_code: str
    room_id: int
    building: str
    timeslot_id: int
    day: str
    start_time: Any
    end_time: Any
    penalty: float
    penalty_breakdown: Dict[str, float]


@dataclass
class BwmIlpResult:
    dataset_id: int
    dataset_name: str
    objective_value: float
    soft_constraint_totals: Dict[str, float]
    assignments: List[AssignmentResult]
    solver_status: str
    status: str
    execution_time: float


SOFT_CONSTRAINT_KEYS = {
    "LECTURER_PREFERENCE",
    "ROOM_UTILIZATION",
    "PEAK_TIME_AVOIDANCE",
}


async def run_bwm_ilp(session: AsyncSession, dataset_id: int) -> BwmIlpResult:
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    classes = (
        await session.execute(
            select(Class).where(Class.dataset_id == dataset_id).order_by(Class.class_id)
        )
    ).scalars().all()
    if not classes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset has no classes to schedule")

    courses = (
        await session.execute(select(Course).where(Course.dataset_id == dataset_id))
    ).scalars().all()
    course_by_id = {course.course_id: course for course in courses}

    lecturers = (
        await session.execute(select(Lecturer).where(Lecturer.dataset_id == dataset_id))
    ).scalars().all()
    lecturer_by_id = {lec.lecturer_id: lec for lec in lecturers}
    lecturer_by_code = {lec.lecturer_code: lec for lec in lecturers}

    timeslots = (
        await session.execute(select(Timeslot).where(Timeslot.dataset_id == dataset_id))
    ).scalars().all()
    rooms = (
        await session.execute(select(Room).where(Room.dataset_id == dataset_id))
    ).scalars().all()

    enrollments = (
        await session.execute(select(Enrollment).where(Enrollment.dataset_id == dataset_id))
    ).scalars().all()
    enrollment_by_class = {enr.class_id: enr for enr in enrollments}

    availability_rows = (
        await session.execute(select(AvailabilityModel).where(AvailabilityModel.dataset_id == dataset_id))
    ).scalars().all()

    preference_rows = (
        await session.execute(select(Preference).where(Preference.dataset_id == dataset_id))
    ).scalars().all()

    room_equipment_rows = (
        await session.execute(select(RoomEquipment).where(RoomEquipment.dataset_id == dataset_id))
    ).scalars().all()

    course_requirement_rows = (
        await session.execute(
            select(CourseEquipmentRequirement).where(CourseEquipmentRequirement.dataset_id == dataset_id)
        )
    ).scalars().all()

    penalty_weights = (
        await session.execute(select(PenaltyWeight).where(PenaltyWeight.dataset_id == dataset_id))
    ).scalars().all()
    weight_map = {row.soft_constraint: row.weight_bwm for row in penalty_weights}
    for key in SOFT_CONSTRAINT_KEYS:
        weight_map.setdefault(key, 0.0)

    course_candidates: dict[int, tuple[int, ...]] = {}
    for course in courses:
        profile = course.default_session_profile or {}
        candidates = []
        for code in profile.get("candidate_lecturers", []):
            lecturer = lecturer_by_code.get(code)
            if lecturer:
                candidates.append(lecturer.lecturer_id)
        if not candidates:
            candidates = list(lecturer_by_id.keys())
        course_candidates[course.course_id] = tuple(sorted(set(candidates)))

    room_equipment: dict[int, dict[str, int]] = defaultdict(dict)
    for req in room_equipment_rows:
        room_equipment[req.room_id][req.equipment_key] = req.quantity

    course_requirements: dict[int, list[CourseEquipmentRequirement]] = defaultdict(list)
    for req in course_requirement_rows:
        course_requirements[req.course_id].append(req)

    availability_map: dict[Tuple[int, int], bool] = {}
    for row in availability_rows:
        availability_map[(row.lecturer_id, row.timeslot_id)] = row.status.lower() == "available"

    preference_map: dict[Tuple[int, int], float] = {}
    for row in preference_rows:
        preference_map[(row.lecturer_id, row.timeslot_id)] = row.preference_score

    class_infos: list[ClassInfo] = []
    for cls in classes:
        course = course_by_id.get(cls.course_id)
        if not course:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class references missing course")
        candidates = course_candidates[course.course_id]
        session_type = cls.session_type.lower()
        requires_lab = session_type == "lab"
        class_infos.append(
            ClassInfo(
                class_id=cls.class_id,
                course_id=course.course_id,
                course_code=course.course_code,
                course_name=course.course_name,
                cohort_id=cls.cohort_id,
                capacity=enrollment_by_class[cls.class_id].student_count
                if cls.class_id in enrollment_by_class
                else cls.class_capacity,
                session_type=cls.session_type,
                requires_lab=requires_lab,
                needs_back_to_back=cls.needs_back_to_back,
                same_room_preferred=cls.same_room_preferred,
                candidate_lecturers=candidates,
            )
        )

    room_infos: dict[int, RoomInfo] = {}
    for room in rooms:
        room_infos[room.room_id] = RoomInfo(
            room_id=room.room_id,
            room_code=room.room_code,
            capacity=room.capacity,
            room_type=room.room_type,
            building=room.building,
            equipment=room_equipment.get(room.room_id, {}),
        )

    timeslot_infos: dict[int, TimeslotInfo] = {}
    for ts in timeslots:
        timeslot_infos[ts.timeslot_id] = TimeslotInfo(
            timeslot_id=ts.timeslot_id,
            day=ts.day_of_week,
            start_time=ts.start_time,
            end_time=ts.end_time,
            is_peak=ts.is_peak,
        )

    lecturer_infos: dict[int, LecturerInfo] = {}
    for lec in lecturers:
        lecturer_infos[lec.lecturer_id] = LecturerInfo(
            lecturer_id=lec.lecturer_id,
            lecturer_code=lec.lecturer_code,
            name=lec.name,
        )

    solver = pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to initialise solver")

    x_vars: dict[Tuple[int, int, int], pywraplp.Variable] = {}
    w_vars: dict[Tuple[int, int, int], pywraplp.Variable] = {}
    class_timeslot_candidates: dict[int, set[int]] = defaultdict(set)

    def _room_compatible(class_info: ClassInfo, room_info: RoomInfo) -> bool:
        """Return True when the room satisfies all hard requirements for the class.

        The checks are ordered from cheapest to most specific:
        1. Capacity must be sufficient.
        2. Lab-only sessions can only use rooms marked lab/hybrid.
        3. Non-lab sessions may still use lab rooms (they are generally better equipped).
        4. Equipment requirements tied to the course/session type must be met when marked
           as required. Preferred equipment is ignored here and handled as soft costs.
        """
        if class_info.capacity > room_info.capacity:
            return False
        if class_info.requires_lab and room_info.room_type.lower() not in {"lab", "hybrid"}:
            return False
        if not class_info.requires_lab and room_info.room_type.lower() == "lab" and class_info.session_type != "lab":
            return True
        requirements = course_requirements.get(class_info.course_id, [])
        if not requirements:
            return True
        for req in requirements:
            if req.session_type and req.session_type.lower() != class_info.session_type.lower():
                continue
            quantity = room_info.equipment.get(req.requirement_key, 0)
            if req.required_flag and quantity < (req.min_quantity or 1):
                return False
        return True

    timeslot_list = list(timeslot_infos.values())
    room_candidates: dict[int, list[int]] = {}
    class_info_by_id: dict[int, ClassInfo] = {}
    for class_info in class_infos:
        class_info_by_id[class_info.class_id] = class_info
        compatible_rooms = [room.room_id for room in rooms if _room_compatible(class_info, room_infos[room.room_id])]
        if not compatible_rooms:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No compatible room for class {class_info.class_id}")
        room_candidates[class_info.class_id] = compatible_rooms

        for lecturer_id in class_info.candidate_lecturers:
            for timeslot in timeslot_list:
                if availability_map.get((lecturer_id, timeslot.timeslot_id), False):
                    class_timeslot_candidates[class_info.class_id].add(timeslot.timeslot_id)
                    key = (class_info.class_id, timeslot.timeslot_id, lecturer_id)
                    w_vars[key] = solver.BoolVar(f"w_{class_info.class_id}_{timeslot.timeslot_id}_{lecturer_id}")

        if not class_timeslot_candidates[class_info.class_id]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Class {class_info.class_id} has no feasible lecturer availability",
            )

    for class_info in class_infos:
        for timeslot_id in class_timeslot_candidates[class_info.class_id]:
            for room_id in room_candidates[class_info.class_id]:
                key = (class_info.class_id, timeslot_id, room_id)
                x_vars[key] = solver.BoolVar(f"x_{class_info.class_id}_{timeslot_id}_{room_id}")

    # ==== ILP hard constraints =====================================================
    # The equalities and inequalities below enforce the feasibility relationships:
    # * each class is assigned to exactly one lecturer-timeslot pairing
    # * class-room assignments mirror the chosen lecturer-timeslot
    # * lecturers and rooms cannot double-book the same timeslot.
    for class_info in class_infos:
        solver.Add(
            solver.Sum(w_vars[(class_info.class_id, ts, lec)] for ts in class_timeslot_candidates[class_info.class_id] for lec in class_info.candidate_lecturers if (class_info.class_id, ts, lec) in w_vars)
            == 1
        )

    for class_info in class_infos:
        for timeslot_id in class_timeslot_candidates[class_info.class_id]:
            w_sum = solver.Sum(
                w_vars[(class_info.class_id, timeslot_id, lec)]
                for lec in class_info.candidate_lecturers
                if (class_info.class_id, timeslot_id, lec) in w_vars
            )
            x_sum = solver.Sum(
                x_vars[(class_info.class_id, timeslot_id, room_id)]
                for room_id in room_candidates[class_info.class_id]
                if (class_info.class_id, timeslot_id, room_id) in x_vars
            )
            solver.Add(w_sum == x_sum)

    for lecturer_id in lecturer_infos:
        for ts in timeslot_infos.values():
            vars_for_lecturer = [
                w_vars[(class_info.class_id, ts.timeslot_id, lecturer_id)]
                for class_info in class_infos
                if (class_info.class_id, ts.timeslot_id, lecturer_id) in w_vars
            ]
            if vars_for_lecturer:
                solver.Add(solver.Sum(vars_for_lecturer) <= 1)

    for room_id, room in room_infos.items():
        for ts in timeslot_infos.values():
            vars_for_room = [
                x_vars[(class_info.class_id, ts.timeslot_id, room_id)]
                for class_info in class_infos
                if (class_info.class_id, ts.timeslot_id, room_id) in x_vars
            ]
            if vars_for_room:
                solver.Add(solver.Sum(vars_for_room) <= 1)

    # ==== ILP objective ============================================================
    # Minimise the weighted sum of soft-constraint penalties. Hard rules above must
    # hold; here we only influence solution quality (preferences, utilisation, etc.).
    objective_coeffs: dict[pywraplp.Variable, float] = defaultdict(float)

    def add_soft_cost(var: pywraplp.Variable, key: str, value: float) -> None:
        if value == 0:
            return
        objective_coeffs[var] += value

    # Soft constraints inject weighted penalties that come from the BWM scores.
    # Each helper below computes the penalty for its dimension and adds it to the
    # objective via `add_soft_cost`. The solver will minimise the sum, so higher
    # penalties make a configuration less desirable but never infeasible.
    for (class_id, timeslot_id, lecturer_id), var in w_vars.items():
        timeslot = timeslot_infos[timeslot_id]
        pref_score = preference_map.get((lecturer_id, timeslot_id), 0.0)
        pref_penalty = 1.0 - pref_score
        add_soft_cost(var, "LECTURER_PREFERENCE", weight_map["LECTURER_PREFERENCE"] * pref_penalty)
        peak_penalty = 1.0 if timeslot.is_peak else 0.0
        add_soft_cost(var, "PEAK_TIME_AVOIDANCE", weight_map["PEAK_TIME_AVOIDANCE"] * peak_penalty)

    for (class_id, timeslot_id, room_id), var in x_vars.items():
        class_info = class_info_by_id[class_id]
        room_info = room_infos[room_id]
        capacity_gap = max(room_info.capacity - class_info.capacity, 0)
        utilization_penalty = capacity_gap / room_info.capacity if room_info.capacity else 0.0
        add_soft_cost(var, "ROOM_UTILIZATION", weight_map["ROOM_UTILIZATION"] * utilization_penalty)

    objective = solver.Objective()
    for var, coeff in objective_coeffs.items():
        objective.SetCoefficient(var, coeff)
    objective.SetMinimization()

    start_time = perf_counter()
    status_code = solver.Solve()
    execution_time = perf_counter() - start_time

    solver_status = "FEASIBLE" if status_code in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else "NOT FEASIBLE"
    solution_status = "OPTIMAL" if status_code == pywraplp.Solver.OPTIMAL else "NOT OPTIMAL"
    if solver_status == "NOT FEASIBLE":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No feasible schedule found")

    # Remove previous schedule entries
    await session.execute(delete(ScheduleEntry).where(ScheduleEntry.dataset_id == dataset_id))

    assignments: list[AssignmentResult] = []
    soft_totals: dict[str, float] = defaultdict(float)

    def _collect_penalties(class_info: ClassInfo, ts_info: TimeslotInfo, room_info: RoomInfo, lecturer_info: LecturerInfo) -> tuple[float, dict[str, float]]:
        penalties: dict[str, float] = {}
        pref_score = preference_map.get((lecturer_info.lecturer_id, ts_info.timeslot_id), 0.0)
        pref_penalty = weight_map["LECTURER_PREFERENCE"] * (1.0 - pref_score)
        if pref_penalty:
            penalties["LECTURER_PREFERENCE"] = pref_penalty
        if ts_info.is_peak:
            penalties["PEAK_TIME_AVOIDANCE"] = weight_map["PEAK_TIME_AVOIDANCE"] * 1.0
        capacity_gap = max(room_info.capacity - class_info.capacity, 0)
        utilization_penalty = 0.0
        if room_info.capacity:
            utilization_penalty = weight_map["ROOM_UTILIZATION"] * (capacity_gap / room_info.capacity)
        if utilization_penalty:
            penalties["ROOM_UTILIZATION"] = utilization_penalty
        total = sum(penalties.values())
        return total, penalties

    for class_info in class_infos:
        chosen_timeslot_id = None
        chosen_room_id = None
        chosen_lecturer_id = None
        for room_id in room_candidates[class_info.class_id]:
            for ts_id in class_timeslot_candidates[class_info.class_id]:
                var = x_vars.get((class_info.class_id, ts_id, room_id))
                if var and var.solution_value() > 0.5:
                    chosen_timeslot_id = ts_id
                    chosen_room_id = room_id
                    break
            if chosen_room_id is not None:
                break
        for lecturer_id in class_info.candidate_lecturers:
            var = w_vars.get((class_info.class_id, chosen_timeslot_id, lecturer_id)) if chosen_timeslot_id is not None else None
            if var and var.solution_value() > 0.5:
                chosen_lecturer_id = lecturer_id
                break
        if chosen_timeslot_id is None or chosen_room_id is None or chosen_lecturer_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Incomplete assignment in solution")

        ts_info = timeslot_infos[chosen_timeslot_id]
        room_info = room_infos[chosen_room_id]
        lecturer_info = lecturer_infos[chosen_lecturer_id]
        penalty_value, penalty_breakdown = _collect_penalties(class_info, ts_info, room_info, lecturer_info)
        for key, value in penalty_breakdown.items():
            soft_totals[key] += value

        assignments.append(
            AssignmentResult(
                class_id=class_info.class_id,
                course_code=class_info.course_code,
                course_name=class_info.course_name,
                cohort_id=class_info.cohort_id,
                lecturer=lecturer_info.name,
                lecturer_code=lecturer_info.lecturer_code,
                room_code=room_info.room_code,
                room_id=room_info.room_id,
                building=room_info.building,
                timeslot_id=ts_info.timeslot_id,
                day=ts_info.day,
                start_time=ts_info.start_time,
                end_time=ts_info.end_time,
                penalty=penalty_value,
                penalty_breakdown=penalty_breakdown,
            )
        )

        session.add(
            ScheduleEntry(
                dataset_id=dataset_id,
                class_id=class_info.class_id,
                lecturer_id=lecturer_info.lecturer_id,
                room_id=room_info.room_id,
                timeslot_id=ts_info.timeslot_id,
                status="simulated",
                penalty=penalty_value,
            )
        )

    await session.commit()

    soft_constraint_totals = {key: soft_totals.get(key, 0.0) for key in SOFT_CONSTRAINT_KEYS}
    objective_value = sum(soft_constraint_totals.values())

    return BwmIlpResult(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        objective_value=objective_value,
        soft_constraint_totals=soft_constraint_totals,
        assignments=assignments,
        solver_status=solver_status,
        status=solution_status,
        execution_time=execution_time,
    )
