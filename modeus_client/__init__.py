"""
Асинхронный клиент для MODEUS API
"""

__version__ = "1.0.0"

from .client import ModeusClient
from .models import Lesson, Person, Timetable, Grades, CourseGrade, Attendance, AttendanceRate

__all__ = ["ModeusClient", "Lesson", "Person", "Timetable", "Grades", "CourseGrade", "Attendance", "AttendanceRate"]
