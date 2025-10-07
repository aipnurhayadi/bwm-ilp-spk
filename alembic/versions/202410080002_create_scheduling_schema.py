"""create scheduling schema"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202410080002"
down_revision: Union[str, None] = "202410080001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "dim_room",
        sa.Column("room_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_code", sa.String(length=64), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("station_capacity", sa.Integer(), nullable=True),
        sa.Column("building", sa.String(length=64), nullable=False),
        sa.Column("floor", sa.String(length=32), nullable=True),
        sa.Column("room_type", sa.String(length=32), nullable=False),
        sa.Column("equipment_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("dataset_id", "room_code", name="uq_room_dataset_code"),
    )

    op.create_table(
        "dim_timeslot",
        sa.Column("timeslot_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.String(length=16), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_peak", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("block_minutes", sa.Integer(), nullable=False),
        sa.UniqueConstraint("dataset_id", "day_of_week", "start_time", name="uq_timeslot_dataset_start"),
    )

    op.create_table(
        "dim_course",
        sa.Column("course_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_code", sa.String(length=64), nullable=False),
        sa.Column("course_name", sa.String(length=255), nullable=False),
        sa.Column("credits", sa.SmallInteger(), nullable=False),
        sa.Column("requires_lab", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("default_session_profile", sa.JSON(), nullable=True),
        sa.UniqueConstraint("dataset_id", "course_code", name="uq_course_dataset_code"),
    )

    op.create_table(
        "dim_class",
        sa.Column("class_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("dim_course.course_id", ondelete="CASCADE"), nullable=False),
        sa.Column("cohort_id", sa.String(length=64), nullable=False),
        sa.Column("group_no", sa.String(length=32), nullable=True),
        sa.Column("class_capacity", sa.Integer(), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("parity_rule", sa.String(length=32), nullable=True),
        sa.Column("needs_back_to_back", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("same_room_preferred", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "dim_lecturer",
        sa.Column("lecturer_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lecturer_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("home_building", sa.String(length=64), nullable=True),
        sa.Column("max_load_credits", sa.Integer(), nullable=True),
        sa.Column("min_load_credits", sa.Integer(), nullable=True),
        sa.UniqueConstraint("dataset_id", "lecturer_code", name="uq_lecturer_dataset_code"),
    )

    op.create_table(
        "fact_availability",
        sa.Column("availability_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lecturer_id", sa.Integer(), sa.ForeignKey("dim_lecturer.lecturer_id", ondelete="CASCADE"), nullable=False),
        sa.Column("timeslot_id", sa.Integer(), sa.ForeignKey("dim_timeslot.timeslot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("dataset_id", "lecturer_id", "timeslot_id", name="uq_availability_dataset_key"),
    )

    op.create_table(
        "fact_preference",
        sa.Column("preference_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lecturer_id", sa.Integer(), sa.ForeignKey("dim_lecturer.lecturer_id", ondelete="CASCADE"), nullable=False),
        sa.Column("timeslot_id", sa.Integer(), sa.ForeignKey("dim_timeslot.timeslot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("preference_score", sa.Float(), nullable=False),
        sa.UniqueConstraint("dataset_id", "lecturer_id", "timeslot_id", name="uq_preference_dataset_key"),
    )

    op.create_table(
        "fact_enrollment",
        sa.Column("enrollment_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("dim_class.class_id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_count", sa.Integer(), nullable=False),
        sa.Column("cohort_id", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("dataset_id", "class_id", name="uq_enrollment_dataset_class"),
    )

    op.create_table(
        "fact_equipment",
        sa.Column("equipment_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("dim_room.room_id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipment_key", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.UniqueConstraint("dataset_id", "room_id", "equipment_key", name="uq_equipment_dataset_key"),
    )

    op.create_table(
        "course_equipment_requirements",
        sa.Column("requirement_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("dim_course.course_id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("requirement_key", sa.String(length=64), nullable=False),
        sa.Column("min_quantity", sa.Integer(), nullable=True),
        sa.Column("required_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("preferred_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "dataset_id",
            "course_id",
            "session_type",
            "requirement_key",
            name="uq_course_equipment_requirement",
        ),
    )

    op.create_table(
        "software_licenses",
        sa.Column("license_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("dim_room.room_id", ondelete="CASCADE"), nullable=False),
        sa.Column("package", sa.String(length=128), nullable=False),
        sa.Column("licensed_seats", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.UniqueConstraint("dataset_id", "room_id", "package", name="uq_software_license"),
    )

    op.create_table(
        "fact_distance",
        sa.Column("distance_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("building_origin", sa.String(length=64), nullable=False),
        sa.Column("building_destination", sa.String(length=64), nullable=False),
        sa.Column("walking_minutes", sa.Float(), nullable=False),
        sa.UniqueConstraint(
            "dataset_id",
            "building_origin",
            "building_destination",
            name="uq_distance_dataset_pair",
        ),
    )

    op.create_table(
        "fact_assignment_policy",
        sa.Column("policy_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_name", sa.String(length=128), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.UniqueConstraint("dataset_id", "rule_name", name="uq_assignment_policy_rule"),
    )

    op.create_table(
        "mart_penalty_weight",
        sa.Column("penalty_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("soft_constraint", sa.String(length=128), nullable=False),
        sa.Column("weight_bwm", sa.Float(), nullable=False),
        sa.UniqueConstraint("dataset_id", "soft_constraint", name="uq_penalty_weight_constraint"),
    )

    op.create_table(
        "out_schedule",
        sa.Column("schedule_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("dim_class.class_id", ondelete="SET NULL"), nullable=True),
        sa.Column("lecturer_id", sa.Integer(), sa.ForeignKey("dim_lecturer.lecturer_id", ondelete="SET NULL"), nullable=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("dim_room.room_id", ondelete="SET NULL"), nullable=True),
        sa.Column("timeslot_id", sa.Integer(), sa.ForeignKey("dim_timeslot.timeslot_id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("penalty", sa.Float(), nullable=True),
        sa.UniqueConstraint("dataset_id", "class_id", "timeslot_id", name="uq_schedule_dataset_class_timeslot"),
    )



def downgrade() -> None:
    op.drop_table("out_schedule")
    op.drop_table("mart_penalty_weight")
    op.drop_table("fact_assignment_policy")
    op.drop_table("fact_distance")
    op.drop_table("software_licenses")
    op.drop_table("course_equipment_requirements")
    op.drop_table("fact_equipment")
    op.drop_table("fact_enrollment")
    op.drop_table("fact_preference")
    op.drop_table("fact_availability")
    op.drop_table("dim_lecturer")
    op.drop_table("dim_class")
    op.drop_table("dim_course")
    op.drop_table("dim_timeslot")
    op.drop_table("dim_room")
    op.drop_table("datasets")
