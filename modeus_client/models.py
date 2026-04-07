"""
Модели данных для MODEUS API
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Person:
    """Информация о пользователе"""
    id: str
    full_name: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None


@dataclass
class Location:
    """Местоположение занятия"""
    building_number: Optional[int] = None
    building_address: Optional[str] = None
    room: Optional[str] = None
    full: Optional[str] = None


@dataclass
class Subject:
    """Предмет"""
    id: str
    name: str
    name_short: str


@dataclass
class Lesson:
    """Занятие"""
    id: str
    subject: Subject
    name: str
    name_short: str
    start: datetime
    end: datetime
    location: Optional[Location] = None
    description: Optional[str] = None
    lesson_type: Optional[str] = None
    format: Optional[str] = None
    teachers: list[Person] = None
    team_name: Optional[str] = None

    def __post_init__(self):
        if self.teachers is None:
            self.teachers = []


@dataclass
class Timetable:
    """Расписание"""
    lessons: list[Lesson]
    from_date: datetime
    to_date: datetime

    def get_lessons_by_date(self, date: datetime) -> list[Lesson]:
        """Получить занятия на конкретную дату"""
        return [
            lesson for lesson in self.lessons
            if lesson.start.date() == date.date()
        ]

    def get_lessons_by_day(self) -> dict[str, list[Lesson]]:
        """Сгруппировать занятия по дням"""
        result = {}
        for lesson in self.lessons:
            day_key = lesson.start.strftime("%Y-%m-%d")
            if day_key not in result:
                result[day_key] = []
            result[day_key].append(lesson)
        return result


@dataclass
class GradeResult:
    """Результат оценки"""
    id: Optional[str]
    control_object_id: Optional[str]
    result_value: str
    created_ts: Optional[str]
    created_by: Optional[str]
    updated_ts: Optional[str]
    updated_by: Optional[str]


@dataclass
class CourseGrade:
    """Оценка по предмету"""
    control_object_id: str
    type_name: str
    type_short_name: str
    type_code: str
    order_index: int
    course_unit_realization_id: str
    course_unit_name: Optional[str]  # Название предмета
    main_grading_scale_code: str
    result_current: Optional[GradeResult]
    result_final: Optional[GradeResult]


@dataclass
class AttendanceRate:
    """Посещаемость по предмету"""
    course_unit_realization_id: str
    course_unit_name: Optional[str]  # Название предмета
    present_rate: float
    absent_rate: float
    undefined_rate: float


@dataclass
class Grades:
    """Оценки"""
    course_grades: list[CourseGrade]


@dataclass
class Attendance:
    """Посещаемость"""
    attendance_rates: list[AttendanceRate]
