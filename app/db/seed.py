from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.scheduling import (
    AssignmentPolicy,
    Availability,
    BuildingDistance,
    Class,
    Course,
    CourseEquipmentRequirement,
    Dataset,
    Enrollment,
    Lecturer,
    PenaltyWeight,
    Preference,
    Room,
    RoomEquipment,
    ScheduleEntry,
    SoftwareLicense,
    Timeslot,
)

DEFAULT_DATASET_NAME = "Demo BWM ILP Dataset"
SLOT_MINUTES = 40
START_TIME = time(8, 0)
END_TIME = time(21, 0)


def _timerange(start: time, end: time, *, slot_minutes: int) -> Iterable[tuple[time, time]]:
    """Yield (start, end) pairs stepping by slot_minutes until end (inclusive of start)."""

    anchor_day = date(2024, 1, 1)
    current = datetime.combine(anchor_day, start)
    end_dt = datetime.combine(anchor_day, end)
    step = timedelta(minutes=slot_minutes)
    while current + step <= end_dt:
        yield current.time(), (current + step).time()
        current += step


def _parse_time(value: str) -> time:
    hour, minute = map(int, value.split(":"))
    return time(hour, minute)


async def seed_demo_dataset(
    session: AsyncSession,
    *,
    dataset_name: str = DEFAULT_DATASET_NAME,
    force_reset: bool = False,
) -> Dataset:
    """Populate a synthetic dataset that exercises the BWM-ILP solver."""

    existing = await session.scalar(select(Dataset).where(Dataset.name == dataset_name))
    if existing and force_reset:
        await session.execute(delete(Dataset).where(Dataset.id == existing.id))
        await session.commit()
        existing = None

    if existing:
        return existing

    dataset = Dataset(name=dataset_name, description="Synthetic dataset for BWM-ILP schedule simulation.")
    session.add(dataset)
    await session.flush()
    dataset_id = dataset.id

    rooms: list[Room] = []
    rooms_data = [
        {
            "room_code": "A101",
            "capacity": 100,
            "station_capacity": 100,
            "building": "A",
            "floor": "1",
            "room_type": "lecture",
            "equipment": {"projector": 1, "whiteboard": 1},
            "software": {"office": 100},
        },
        {
            "room_code": "A102",
            "capacity": 100,
            "station_capacity": 100,
            "building": "A",
            "floor": "1",
            "room_type": "lecture",
            "equipment": {"projector": 1, "whiteboard": 1},
            "software": {"office": 100},
        },
        {
            "room_code": "B201",
            "capacity": 100,
            "station_capacity": 100,
            "building": "B",
            "floor": "2",
            "room_type": "lab",
            "equipment": {"lab_pc": 100, "projector": 1},
            "software": {"python": 100, "matlab": 80},
        },
        {
            "room_code": "B202",
            "capacity": 100,
            "station_capacity": 100,
            "building": "B",
            "floor": "2",
            "room_type": "lab",
            "equipment": {"lab_pc": 100, "projector": 1},
            "software": {"python": 100},
        },
        {
            "room_code": "C301",
            "capacity": 100,
            "station_capacity": 100,
            "building": "C",
            "floor": "3",
            "room_type": "lecture",
            "equipment": {"projector": 2, "sound_system": 1},
            "software": {"office": 100},
        },
        {
            "room_code": "C302",
            "capacity": 100,
            "station_capacity": 100,
            "building": "C",
            "floor": "3",
            "room_type": "seminar",
            "equipment": {"projector": 1, "whiteboard": 1},
            "software": {"office": 100},
        },
    ]

    for room_info in rooms_data:
        room = Room(
            dataset_id=dataset_id,
            room_code=room_info["room_code"],
            capacity=room_info["capacity"],
            station_capacity=room_info["station_capacity"],
            building=room_info["building"],
            floor=room_info["floor"],
            room_type=room_info["room_type"],
            equipment_json=room_info["equipment"],
        )
        rooms.append(room)
    session.add_all(rooms)
    await session.flush()

    room_code_map = {room.room_code: room for room in rooms}

    timeslots: list[Timeslot] = []
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in days:
        for start, end in _timerange(START_TIME, END_TIME, slot_minutes=SLOT_MINUTES):
            is_peak = time(10, 0) <= start < time(14, 0)
            timeslots.append(
                Timeslot(
                    dataset_id=dataset_id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    is_peak=is_peak,
                    block_minutes=SLOT_MINUTES,
                )
            )
    session.add_all(timeslots)
    await session.flush()

    timeslots_by_day: dict[str, list[Timeslot]] = defaultdict(list)
    for ts in timeslots:
        timeslots_by_day[ts.day_of_week].append(ts)

    lecturers: list[Lecturer] = []
    day_patterns = [
        {
            "Monday": (("08:00", "12:00"), ("13:00", "16:20")),
            "Wednesday": (("08:00", "12:00"), ("13:00", "16:20")),
            "Friday": (("08:00", "12:00"), ("13:00", "14:40")),
        },
        {
            "Tuesday": (("08:00", "12:40"), ("14:00", "17:00")),
            "Thursday": (("08:00", "12:40"), ("14:00", "17:00")),
            "Saturday": (("09:00", "12:20"),),
        },
        {
            "Monday": (("10:00", "18:00"),),
            "Tuesday": (("10:00", "18:00"),),
            "Thursday": (("10:00", "18:00"),),
        },
        {
            "Wednesday": (("08:00", "15:00"),),
            "Friday": (("08:00", "15:00"),),
            "Saturday": (("09:00", "13:00"),),
        },
        {
            "Monday": (("09:00", "13:20"),),
            "Tuesday": (("09:00", "13:20"),),
            "Thursday": (("09:00", "13:20"),),
            "Friday": (("13:20", "17:40"),),
        },
    ]
    preference_patterns = [
        {"morning": 1.0, "afternoon": 0.7, "evening": 0.3},
        {"morning": 0.8, "afternoon": 1.0, "evening": 0.5},
        {"morning": 0.6, "afternoon": 1.0, "evening": 0.8},
        {"morning": 0.5, "afternoon": 0.9, "evening": 0.7},
        {"morning": 0.7, "afternoon": 0.8, "evening": 0.4},
    ]
    building_cycle = ["A", "B", "C"]

    lecturer_names = [
        "Adi Nugroho",
        "Ayu Lestari",
        "Budi Santoso",
        "Citra Maharani",
        "Dewi Anggraini",
        "Eko Prasetyo",
        "Farah Salsabila",
        "Galih Pramudito",
        "Hana Wibisono",
        "Imam Ramadhan",
        "Joko Saputra",
        "Kartika Putri",
        "Lukman Hakim",
        "Maya Ardiani",
        "Nadia Paramita",
    ]

    lecturer_profiles: list[dict[str, object]] = []
    for idx, lecturer_name in enumerate(lecturer_names):
        day_pattern = day_patterns[idx % len(day_patterns)]
        day_blocks = {day: [tuple(block) for block in blocks] for day, blocks in day_pattern.items()}
        preferences = preference_patterns[idx % len(preference_patterns)]
        min_load = 4 + (idx % 4) * 2
        lecturer_profiles.append(
            {
                "lecturer_code": f"L{idx + 1:03d}",
                "name": lecturer_name,
                "home_building": building_cycle[idx % len(building_cycle)],
                "min_load": min_load,
                "max_load": min_load + 6,
                "day_blocks": day_blocks,
                "preference": preferences,
            }
        )

    for profile in lecturer_profiles:
        lecturers.append(
            Lecturer(
                dataset_id=dataset_id,
                lecturer_code=profile["lecturer_code"],
                name=profile["name"],
                home_building=profile["home_building"],
                min_load_credits=profile["min_load"],
                max_load_credits=profile["max_load"],
            )
        )
    session.add_all(lecturers)
    await session.flush()

    lecturer_code_map = {lec.lecturer_code: lec for lec in lecturers}

    courses: list[Course] = []
    lecturer_codes = [profile["lecturer_code"] for profile in lecturer_profiles]
    cohorts = [
        "TI-2020-A",
        "TI-2020-B",
        "TI-2021-A",
        "TI-2021-B",
        "TI-2022-A",
        "TI-2022-B",
        "TI-2023-A",
        "TI-2023-B",
        "TI-2024-A",
        "TI-2024-B",
    ]

    course_names = [
        "Analisis Data Lanjut",
        "Optimasi Industri",
        "Pemodelan Sistem Kompleks",
        "Kecerdasan Buatan Terapan",
        "Manajemen Rantai Pasok",
        "Statistika Multivariat",
        "Sistem Produksi Lean",
        "Perancangan Eksperimen",
        "Simulasi Monte Carlo",
        "Pengambilan Keputusan",
        "Analitika Bisnis",
        "Peramalan Deret Waktu",
        "Rekayasa Kualitas",
        "Manajemen Proyek Teknologi",
        "Logistik Distribusi",
        "Optimasi Kombinatorik",
        "Analitik Keuangan",
        "Data Mining Terapan",
        "Pemrograman Linear",
        "Pemodelan Stokastik",
        "Metode Numerik",
        "Sistem Pendukung Keputusan",
        "Machine Learning Industri",
        "Analisis Risiko Operasional",
        "Desain Jaringan Transportasi",
        "Analitik Layanan",
        "Perencanaan Produksi",
        "Audit Proses",
        "Manajemen Strategis Operasi",
        "Komputasi Evolusioner",
    ]

    course_specs: list[dict[str, object]] = []
    extra_sections = 10
    class_counter = 0
    for idx, course_name in enumerate(course_names):
        course_number = idx + 1
        course_code = f"CS{course_number + 700:03d}"
        lab_required = idx % 5 == 0
        candidate_lecturers = [
            lecturer_codes[idx % len(lecturer_codes)],
            lecturer_codes[(idx + 5) % len(lecturer_codes)],
            lecturer_codes[(idx + 10) % len(lecturer_codes)],
        ]
        section_count = 3 + (1 if idx < extra_sections else 0)
        class_entries: list[dict[str, object]] = []
        for section in range(section_count):
            class_counter += 1
            cohort_label = cohorts[(class_counter - 1) % len(cohorts)]
            cohort_id = f"{cohort_label}-C{class_counter:03d}"
            capacity = 60 + (class_counter % 41)
            class_entries.append(
                {
                    "cohort": cohort_id,
                    "capacity": capacity,
                    "session_type": "lab" if lab_required else "lecture",
                    "duration": 160,
                    "same_room": True,
                    "needs_lab": lab_required,
                }
            )
        course_specs.append(
            {
                "course_code": course_code,
                "course_name": course_name,
                "credits": 2 + (idx % 3),
                "requires_lab": lab_required,
                "candidate_lecturers": candidate_lecturers,
                "classes": class_entries,
            }
        )

    for spec in course_specs:
        profile = {
            "candidate_lecturers": spec["candidate_lecturers"],
            "sessions_per_week": len(spec["classes"]),
            "preferred_room_type": "lab" if spec["requires_lab"] else "lecture",
        }
        courses.append(
            Course(
                dataset_id=dataset_id,
                course_code=spec["course_code"],
                course_name=spec["course_name"],
                credits=spec["credits"],
                requires_lab=spec["requires_lab"],
                default_session_profile=profile,
            )
        )
    session.add_all(courses)
    await session.flush()

    course_code_map = {course.course_code: course for course in courses}

    classes: list[Class] = []
    for spec in course_specs:
        course = course_code_map[spec["course_code"]]
        for idx, cls_info in enumerate(spec["classes"], start=1):
            new_class = Class(
                dataset_id=dataset_id,
                course_id=course.course_id,
                cohort_id=cls_info["cohort"],
                group_no=str(idx),
                class_capacity=cls_info["capacity"],
                session_type=cls_info["session_type"],
                parity_rule=None,
                needs_back_to_back=cls_info.get("needs_back_to_back", False),
                same_room_preferred=cls_info.get("same_room", False),
            )
            classes.append(new_class)
    session.add_all(classes)
    await session.flush()

    enrollments: list[Enrollment] = []
    for cls in classes:
        enrollments.append(
            Enrollment(
                dataset_id=dataset_id,
                class_id=cls.class_id,
                student_count=cls.class_capacity,
                cohort_id=cls.cohort_id,
            )
        )
    session.add_all(enrollments)

    equipment_records: list[RoomEquipment] = []
    software_records: list[SoftwareLicense] = []
    for room_info in rooms_data:
        room = room_code_map[room_info["room_code"]]
        for key, qty in room_info["equipment"].items():
            equipment_records.append(
                RoomEquipment(
                    dataset_id=dataset_id,
                    room_id=room.room_id,
                    equipment_key=key,
                    quantity=qty,
                    status="available",
                )
            )
        for package, seats in room_info["software"].items():
            software_records.append(
                SoftwareLicense(
                    dataset_id=dataset_id,
                    room_id=room.room_id,
                    package=package,
                    licensed_seats=seats,
                    status="active",
                )
            )
    session.add_all(equipment_records)
    session.add_all(software_records)

    requirement_records: list[CourseEquipmentRequirement] = []
    for spec in course_specs:
        if not spec["requires_lab"]:
            continue
        course = course_code_map[spec["course_code"]]
        requirement_records.append(
            CourseEquipmentRequirement(
                dataset_id=dataset_id,
                course_id=course.course_id,
                session_type="lab",
                requirement_key="lab_pc",
                min_quantity=24,
                required_flag=True,
                preferred_flag=True,
            )
        )
        requirement_records.append(
            CourseEquipmentRequirement(
                dataset_id=dataset_id,
                course_id=course.course_id,
                session_type="lab",
                requirement_key="python",
                min_quantity=20,
                required_flag=False,
                preferred_flag=True,
            )
        )
    session.add_all(requirement_records)

    distance_records: list[BuildingDistance] = []
    buildings = ["A", "B", "C"]
    distance_matrix = {
        ("A", "B"): 6.0,
        ("A", "C"): 4.0,
        ("B", "C"): 3.5,
    }
    for origin in buildings:
        for dest in buildings:
            if origin == dest:
                distance = 0.0
            else:
                distance = distance_matrix.get((origin, dest)) or distance_matrix.get((dest, origin), 5.0)
            distance_records.append(
                BuildingDistance(
                    dataset_id=dataset_id,
                    building_origin=origin,
                    building_destination=dest,
                    walking_minutes=distance,
                )
            )
    session.add_all(distance_records)

    policy_records: list[AssignmentPolicy] = [
        AssignmentPolicy(
            dataset_id=dataset_id,
            rule_name="MAX_SESSIONS_PER_DAY",
            threshold=3,
            priority=1,
        ),
        AssignmentPolicy(
            dataset_id=dataset_id,
            rule_name="MAX_PEAK_HOURS",
            threshold=2,
            priority=2,
        ),
    ]
    session.add_all(policy_records)

    penalty_records: list[PenaltyWeight] = [
        PenaltyWeight(dataset_id=dataset_id, soft_constraint="LECTURER_PREFERENCE", weight_bwm=0.45),
        PenaltyWeight(dataset_id=dataset_id, soft_constraint="ROOM_UTILIZATION", weight_bwm=0.35),
        PenaltyWeight(dataset_id=dataset_id, soft_constraint="PEAK_TIME_AVOIDANCE", weight_bwm=0.20),
    ]
    session.add_all(penalty_records)

    # Availability and preferences
    availability_records: list[Availability] = []
    preference_records: list[Preference] = []

    for profile in lecturer_profiles:
        lecturer = lecturer_code_map[profile["lecturer_code"]]
        day_blocks = profile["day_blocks"]
        for day, blocks in day_blocks.items():
            for block_start, block_end in blocks:
                start_t = _parse_time(block_start)
                end_t = _parse_time(block_end)
                for ts in timeslots_by_day[day]:
                    if start_t <= ts.start_time and ts.end_time <= end_t:
                        availability_records.append(
                            Availability(
                                dataset_id=dataset_id,
                                lecturer_id=lecturer.lecturer_id,
                                timeslot_id=ts.timeslot_id,
                                status="available",
                                reason=None,
                            )
                        )
                        hour = ts.start_time.hour
                        if hour < 12:
                            score = profile["preference"]["morning"]
                        elif hour < 16:
                            score = profile["preference"]["afternoon"]
                        else:
                            score = profile["preference"]["evening"]
                        preference_records.append(
                            Preference(
                                dataset_id=dataset_id,
                                lecturer_id=lecturer.lecturer_id,
                                timeslot_id=ts.timeslot_id,
                                preference_score=score,
                            )
                        )
    session.add_all(availability_records)
    session.add_all(preference_records)

    await session.commit()
    return dataset


async def _main(force_reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        dataset = await seed_demo_dataset(session, force_reset=force_reset)
        print(f"Seeded dataset '{dataset.name}' with id={dataset.id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the demo dataset for BWM-ILP simulation")
    parser.add_argument("--reset", action="store_true", help="Recreate the dataset even if it exists")
    args = parser.parse_args()
    asyncio.run(_main(force_reset=args.reset))


if __name__ == "__main__":
    main()
