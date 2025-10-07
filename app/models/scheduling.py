from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=datetime.utcnow, nullable=False)


class Room(Base):
    __tablename__ = "dim_room"

    room_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    room_code: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    station_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    building: Mapped[str] = mapped_column(String(64), nullable=False)
    floor: Mapped[str | None] = mapped_column(String(32), nullable=True)
    room_type: Mapped[str] = mapped_column(String(32), nullable=False)
    equipment_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "room_code", name="uq_room_dataset_code"),
    )


class Timeslot(Base):
    __tablename__ = "dim_timeslot"

    timeslot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(16), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_peak: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    block_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_id", "day_of_week", "start_time", name="uq_timeslot_dataset_start"),
    )


class Course(Base):
    __tablename__ = "dim_course"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    course_code: Mapped[str] = mapped_column(String(64), nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    requires_lab: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_session_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "course_code", name="uq_course_dataset_code"),
    )


class Class(Base):
    __tablename__ = "dim_class"

    class_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("dim_course.course_id", ondelete="CASCADE"), nullable=False)
    cohort_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    class_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parity_rule: Mapped[str | None] = mapped_column(String(32), nullable=True)
    needs_back_to_back: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    same_room_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Lecturer(Base):
    __tablename__ = "dim_lecturer"

    lecturer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    lecturer_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    home_building: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_load_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_load_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "lecturer_code", name="uq_lecturer_dataset_code"),
    )


class Availability(Base):
    __tablename__ = "fact_availability"

    availability_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("dim_lecturer.lecturer_id", ondelete="CASCADE"), nullable=False)
    timeslot_id: Mapped[int] = mapped_column(ForeignKey("dim_timeslot.timeslot_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "lecturer_id", "timeslot_id", name="uq_availability_dataset_key"),
    )


class Preference(Base):
    __tablename__ = "fact_preference"

    preference_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("dim_lecturer.lecturer_id", ondelete="CASCADE"), nullable=False)
    timeslot_id: Mapped[int] = mapped_column(ForeignKey("dim_timeslot.timeslot_id", ondelete="CASCADE"), nullable=False)
    preference_score: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_id", "lecturer_id", "timeslot_id", name="uq_preference_dataset_key"),
    )


class Enrollment(Base):
    __tablename__ = "fact_enrollment"

    enrollment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("dim_class.class_id", ondelete="CASCADE"), nullable=False)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cohort_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "class_id", name="uq_enrollment_dataset_class"),
    )


class RoomEquipment(Base):
    __tablename__ = "fact_equipment"

    equipment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("dim_room.room_id", ondelete="CASCADE"), nullable=False)
    equipment_key: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "room_id", "equipment_key", name="uq_equipment_dataset_key"),
    )


class CourseEquipmentRequirement(Base):
    __tablename__ = "course_equipment_requirements"

    requirement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("dim_course.course_id", ondelete="CASCADE"), nullable=False)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False)
    requirement_key: Mapped[str] = mapped_column(String(64), nullable=False)
    min_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "course_id",
            "session_type",
            "requirement_key",
            name="uq_course_equipment_requirement",
        ),
    )


class SoftwareLicense(Base):
    __tablename__ = "software_licenses"

    license_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("dim_room.room_id", ondelete="CASCADE"), nullable=False)
    package: Mapped[str] = mapped_column(String(128), nullable=False)
    licensed_seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "room_id", "package", name="uq_software_license"),
    )


class BuildingDistance(Base):
    __tablename__ = "fact_distance"

    distance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    building_origin: Mapped[str] = mapped_column(String(64), nullable=False)
    building_destination: Mapped[str] = mapped_column(String(64), nullable=False)
    walking_minutes: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "building_origin",
            "building_destination",
            name="uq_distance_dataset_pair",
        ),
    )


class AssignmentPolicy(Base):
    __tablename__ = "fact_assignment_policy"

    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "rule_name", name="uq_assignment_policy_rule"),
    )


class PenaltyWeight(Base):
    __tablename__ = "mart_penalty_weight"

    penalty_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    soft_constraint: Mapped[str] = mapped_column(String(128), nullable=False)
    weight_bwm: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_id", "soft_constraint", name="uq_penalty_weight_constraint"),
    )


class ScheduleEntry(Base):
    __tablename__ = "out_schedule"

    schedule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("dim_class.class_id", ondelete="SET NULL"), nullable=True)
    lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("dim_lecturer.lecturer_id", ondelete="SET NULL"), nullable=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("dim_room.room_id", ondelete="SET NULL"), nullable=True)
    timeslot_id: Mapped[int | None] = mapped_column(ForeignKey("dim_timeslot.timeslot_id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    penalty: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "class_id", "timeslot_id", name="uq_schedule_dataset_class_timeslot"),
    )
