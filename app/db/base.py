"""Import all SQLAlchemy models here for Alembic autogeneration."""

from app.models.base import Base
from app.models import (
	AssignmentPolicy,
	Availability,
	BuildingDistance,
	Class,
	Course,
	CourseEquipmentRequirement,
	Dataset,
	Enrollment,
	PenaltyWeight,
	Preference,
	Room,
	RoomEquipment,
	ScheduleEntry,
	SoftwareLicense,
	Timeslot,
	User,
)

__all__ = [
	"AssignmentPolicy",
	"Availability",
	"Base",
	"BuildingDistance",
	"Class",
	"Course",
	"CourseEquipmentRequirement",
	"Dataset",
	"Enrollment",
	"PenaltyWeight",
	"Preference",
	"Room",
	"RoomEquipment",
	"ScheduleEntry",
	"SoftwareLicense",
	"Timeslot",
	"User",
]
