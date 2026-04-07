"""
Асинхронный клиент для работы с MODEUS API
"""

import re
import json
import base64
from functools import wraps
from secrets import token_hex
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import Person, Lesson, Subject, Location, Timetable, Grades, CourseGrade, Attendance, AttendanceRate, GradeResult


def require_auth(func):
    """Декоратор для проверки авторизации и сессии"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.session:
            raise RuntimeError("Используйте async with для создания клиента")
        if not self.token:
            raise RuntimeError("Необходима авторизация")
        return await func(self, *args, **kwargs)
    return wrapper


class ModeusClient:
    """Асинхронный клиент для MODEUS API"""

    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self._base_url = "https://utmn.modeus.org"

    async def __aenter__(self):
        """Контекстный менеджер - вход"""
        self.session = httpx.AsyncClient(
            http2=True,
            timeout=30.0,
            follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход"""
        if self.session:
            await self.session.aclose()

    def _extract_token_from_url(self, url: str) -> Optional[str]:
        """Извлекает токен из URL"""
        match = re.search(r"id_token=([a-zA-Z0-9\-_.]+)", url)
        return match.group(1) if match else None

    def _decode_token(self, token: str) -> dict:
        """Декодирует JWT токен"""
        try:
            parts = token.split('.')
            if len(parts) >= 2:
                payload = parts[1]
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.urlsafe_b64decode(payload)
                return json.loads(decoded)
        except Exception:
            pass
        return {}

    async def _api_request(self, method: str, endpoint: str, **kwargs):
        """Универсальный метод для API запросов с авторизацией"""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"

        url = f"{self._base_url}{endpoint}"
        r = await self.session.request(method, url, headers=headers, **kwargs)

        if r.status_code != 200:
            raise RuntimeError(f"Ошибка API ({r.status_code}): {endpoint}")

        return r.json()

    async def login(self, username: str, password: str) -> bool:
        """
        Авторизация в MODEUS

        Args:
            username: Email пользователя (@study.utmn.ru)
            password: Пароль

        Returns:
            True если авторизация успешна, False иначе
        """
        if not self.session:
            raise RuntimeError("Используйте async with для создания клиента")

        try:
            # Получаем конфигурацию
            r = await self.session.get(
                f"{self._base_url}/schedule-calendar/assets/app.config.json"
            )
            config = r.json()["wso"]
            auth_url = config["loginUrl"]
            client_id = config["clientId"]

            # Инициируем авторизацию
            auth_params = {
                "client_id": client_id,
                "redirect_uri": f"{self._base_url}/",
                "response_type": "id_token",
                "scope": "openid",
                "nonce": token_hex(16),
                "state": token_hex(16),
            }

            r = await self.session.get(auth_url, params=auth_params)

            # Отправляем данные на ADFS
            r = await self.session.post(
                str(r.url),
                data={
                    "UserName": username,
                    "Password": password,
                    "AuthMethod": "FormsAuthentication"
                }
            )

            # Парсим форму
            html = BeautifulSoup(r.text, "lxml")

            # Проверяем ошибки
            error_tag = html.find(id="errorText")
            if error_tag and error_tag.text.strip():
                return False

            # Ищем форму ADFS
            form = html.find("form", id="loginForm")
            if form:
                form_action = form.get("action")
                r = await self.session.post(
                    f"https://fs.utmn.ru{form_action}",
                    data={
                        "UserName": username,
                        "Password": password,
                        "AuthMethod": "FormsAuthentication"
                    }
                )
                html = BeautifulSoup(r.text, "lxml")

            # Собираем скрытые поля формы
            form = html.find("form")
            if not form:
                return False

            auth_data = {}
            for input_field in form.find_all("input", type="hidden"):
                auth_data[input_field["name"]] = input_field["value"]

            # Отправляем на commonauth
            r = await self.session.post(
                "https://auth.modeus.org/commonauth",
                data=auth_data,
                follow_redirects=False
            )

            # Следуем редиректам для получения токена
            if "Location" in r.headers:
                location = r.headers["Location"]

                for _ in range(5):
                    r = await self.session.get(location, follow_redirects=False)

                    if r.status_code in (302, 303) and "Location" in r.headers:
                        location = r.headers["Location"]

                        if "id_token=" in location:
                            self.token = self._extract_token_from_url(location)
                            if self.token:
                                token_data = self._decode_token(self.token)
                                self.user_id = token_data.get("person_id")
                                return True
                    else:
                        break

            return False

        except Exception as e:
            raise RuntimeError(f"Ошибка авторизации: {e}")

    @require_auth
    async def get_timetable(
        self,
        from_date: datetime,
        to_date: datetime,
        person_id: Optional[str] = None
    ) -> Timetable:
        """
        Получить расписание

        Args:
            from_date: Начальная дата
            to_date: Конечная дата
            person_id: ID пользователя (если None, используется текущий пользователь)

        Returns:
            Объект Timetable с расписанием
        """
        target_person_id = person_id or self.user_id
        if not target_person_id:
            raise RuntimeError("Не указан ID пользователя")

        try:
            from_str = from_date.strftime("%Y-%m-%dT00:00:00") + "Z"
            to_str = to_date.strftime("%Y-%m-%dT23:59:59") + "Z"

            data = await self._api_request(
                "POST",
                "/schedule-calendar-v2/api/calendar/events/search",
                json={
                    "attendeePersonId": [target_person_id],
                    "size": 500,
                    "timeMin": from_str,
                    "timeMax": to_str,
                }
            )
            embedded = data.get("_embedded", {})
            events = embedded.get("events", [])

            # Парсим локации
            event_locations = {el["eventId"]: el for el in embedded.get("event-locations", [])}

            event_rooms_list = embedded.get("event-rooms", [])
            event_rooms = {}
            for er in event_rooms_list:
                event_href = er.get("_links", {}).get("event", {}).get("href", "")
                event_id = event_href.split("/")[-1] if event_href else None
                if event_id:
                    room_href = er.get("_links", {}).get("room", {}).get("href", "")
                    room_id = room_href.split("/")[-1] if room_href else None
                    event_rooms[event_id] = room_id

            rooms = {r["id"]: r for r in embedded.get("rooms", [])}

            # Парсим предметы (course-unit-realizations)
            course_units = {cu["id"]: cu for cu in embedded.get("course-unit-realizations", [])}

            # Парсим участников событий
            event_attendees_list = embedded.get("event-attendees", [])
            event_attendees = {}
            for ea in event_attendees_list:
                event_href = ea.get("_links", {}).get("event", {}).get("href", "")
                event_id = event_href.split("/")[-1] if event_href else None
                if event_id:
                    if event_id not in event_attendees:
                        event_attendees[event_id] = []
                    event_attendees[event_id].append(ea)

            # Парсим людей
            persons = {p["id"]: p for p in embedded.get("persons", [])}

            lessons = []
            for event in events:
                # Парсим предмет из course-unit-realizations
                subject_id = None
                subject_name = event.get("name", "")  # Тема урока как fallback
                subject_name_short = event.get("nameShort", "")

                # Пытаемся найти course-unit-realization
                links = event.get("_links", {})
                if "course-unit-realization" in links:
                    course_unit_id = links["course-unit-realization"]["href"].split("/")[-1]
                    if course_unit_id in course_units:
                        course_unit = course_units[course_unit_id]
                        subject_id = course_unit_id
                        subject_name = course_unit.get("name", subject_name)
                        subject_name_short = course_unit.get("nameShort", subject_name_short)

                subject = Subject(
                    id=subject_id or event.get("id"),
                    name=subject_name,
                    name_short=subject_name_short
                )

                # Парсим время
                start = datetime.fromisoformat(event.get("startsAt").replace("Z", "+00:00"))
                end = datetime.fromisoformat(event.get("endsAt").replace("Z", "+00:00"))

                # Парсим локацию
                location = None
                event_id = event.get("id")

                # Проверяем event-locations для customLocation
                if event_id in event_locations:
                    event_location = event_locations[event_id]
                    custom_location = event_location.get("customLocation")

                    if custom_location:
                        # Используем кастомную локацию
                        location = Location(
                            building_number=None,
                            building_address=None,
                            room=None,
                            full=custom_location
                        )
                    elif event_id in event_rooms:
                        # Ищем в event-rooms
                        room_id = event_rooms[event_id]
                        if room_id and room_id in rooms:
                            room_data = rooms[room_id]
                            building_data = room_data.get("building", {})

                            building_name = building_data.get("name")
                            building_address = building_data.get("address")
                            room_name = room_data.get("name")

                            location_full = f"{building_name}, {room_name}" if building_name else room_name

                            location = Location(
                                building_number=None,
                                building_address=building_address,
                                room=room_name,
                                full=location_full
                            )

                # Создаем занятие
                lesson = Lesson(
                    id=event.get("id"),
                    subject=subject,
                    name=event.get("name", ""),  # Тема урока
                    name_short=event.get("nameShort", ""),  # Короткое название темы
                    start=start,
                    end=end,
                    location=location,
                    description=event.get("description"),
                    lesson_type=links.get("type", {}).get("href", "").split("/")[-1] if "type" in links else None,
                    format=links.get("format", {}).get("href", "").split("/")[-1] if "format" in links else None,
                )

                # Добавляем преподавателей
                if event_id in event_attendees:
                    for attendee in event_attendees[event_id]:
                        # Проверяем роль - только преподаватели
                        role_id = attendee.get("roleId", "")
                        if role_id == "TEACH":
                            person_href = attendee.get("_links", {}).get("person", {}).get("href", "")
                            person_id = person_href.split("/")[-1] if person_href else None

                            if person_id and person_id in persons:
                                person_data = persons[person_id]
                                teacher = Person(
                                    id=person_data.get("id"),
                                    full_name=person_data.get("fullName", ""),
                                    first_name=person_data.get("firstName", ""),
                                    last_name=person_data.get("lastName", ""),
                                    middle_name=person_data.get("middleName"),
                                )
                                lesson.teachers.append(teacher)

                lessons.append(lesson)

            return Timetable(
                lessons=sorted(lessons, key=lambda x: x.start),
                from_date=from_date,
                to_date=to_date
            )

        except Exception as e:
            raise RuntimeError(f"Ошибка при получении расписания: {e}")

    @require_auth
    async def search_person(self, name: str, limit: int = 25) -> list[Person]:
        """
        Поиск пользователя по имени

        Args:
            name: Имя или фамилия для поиска
            limit: Максимальное количество результатов

        Returns:
            Список найденных пользователей
        """
        try:
            data = await self._api_request(
                "POST",
                "/schedule-calendar-v2/api/people/persons/search/",
                json={
                    "fullName": name,
                    "page": 0,
                    "size": limit,
                    "sort": "+fullName"
                }
            )

            embedded = data.get("_embedded", {})
            people_data = embedded.get("persons", [])

            people = []
            for person_data in people_data:
                person = Person(
                    id=person_data.get("id"),
                    full_name=person_data.get("fullName", ""),
                    first_name=person_data.get("firstName", ""),
                    last_name=person_data.get("lastName", ""),
                    middle_name=person_data.get("middleName"),
                )
                people.append(person)

            return people

        except Exception as e:
            raise RuntimeError(f"Ошибка при поиске: {e}")

    @require_auth
    async def get_person_info(self, person_id: str) -> Optional[Person]:
        """
        Получить информацию о пользователе по ID

        Args:
            person_id: ID пользователя

        Returns:
            Объект Person или None если не найден
        """
        try:
            data = await self._api_request(
                "POST",
                "/schedule-calendar-v2/api/people/persons/search/",
                json={
                    "id": [person_id],
                    "page": 0,
                    "size": 1,
                }
            )

            embedded = data.get("_embedded", {})
            people_data = embedded.get("persons", [])

            if not people_data:
                return None

            person_data = people_data[0]
            return Person(
                id=person_data.get("id"),
                full_name=person_data.get("fullName", ""),
                first_name=person_data.get("firstName", ""),
                last_name=person_data.get("lastName", ""),
                middle_name=person_data.get("middleName"),
            )

        except Exception:
            return None

    @require_auth
    async def get_grades(self, academic_period_id: Optional[str] = None) -> Grades:
        """
        Получить оценки и посещаемость

        Args:
            academic_period_id: ID академического периода (семестра). Если None, используется текущий.

        Returns:
            Объект Grades с оценками и посещаемостью
        """
        try:
            # Получаем информацию о студенте
            primary_data = await self._api_request(
                "GET",
                "/students-app/api/pages/student-card/my/primary"
            )

            person_id = primary_data.get("personId")
            student_id = primary_data.get("id")
            curriculum_flow_id = primary_data.get("curriculumFlow", {}).get("id")
            curriculum_plan_id = primary_data.get("curriculumFlow", {}).get("curriculumPlanId")

            # Если не указан период, берем текущий (последний активный)
            if not academic_period_id:
                periods = primary_data.get("academicPeriodRealizations", [])
                if not periods:
                    raise RuntimeError("Нет доступных академических периодов")

                # Берем текущий период (где текущая дата между startDate и endDate)
                from datetime import datetime
                today = datetime.now().date()

                for period in periods:
                    start = datetime.fromisoformat(period["startDate"]).date()
                    end = datetime.fromisoformat(period["endDate"]).date()
                    if start <= today <= end:
                        academic_period_id = period["id"]
                        break

                # Если не нашли текущий, берем последний
                if not academic_period_id:
                    academic_period_id = periods[-1]["id"]

            # Получаем список предметов для периода
            primary_table = await self._api_request(
                "POST",
                "/students-app/api/pages/student-card/my/academic-period-results-table/primary",
                json={
                    "personId": person_id,
                    "withMidcheckModulesIncluded": False,
                    "aprId": academic_period_id,
                    "studentId": student_id,
                    "curriculumFlowId": curriculum_flow_id,
                    "curriculumPlanId": curriculum_plan_id
                }
            )

            # Извлекаем ID предметов и курсов
            course_unit_ids = [cu["id"] for cu in primary_table.get("courseUnitRealizations", [])]
            academic_course_ids = [ac["id"] for ac in primary_table.get("academicCourses", [])]

            # Создаем словарь названий предметов
            course_unit_names = {cu["id"]: cu["name"] for cu in primary_table.get("courseUnitRealizations", [])}

            # Запрашиваем оценки
            grades_data = await self._api_request(
                "POST",
                "/students-app/api/pages/student-card/my/academic-period-results-table/secondary",
                json={
                    "courseUnitRealizationId": course_unit_ids,
                    "academicCourseId": academic_course_ids,
                    "personId": person_id,
                    "studentId": student_id
                }
            )

            # Парсим оценки по предметам
            course_grades = []
            for grade_data in grades_data.get("courseUnitRealizationControlObjects", []):
                course_unit_id = grade_data.get("courseUnitRealizationId", "")

                # Парсим текущий результат
                result_current = None
                if grade_data.get("resultCurrent"):
                    rc = grade_data["resultCurrent"]
                    result_current = GradeResult(
                        id=rc.get("id"),
                        control_object_id=rc.get("controlObjectId"),
                        result_value=rc.get("resultValue", ""),
                        created_ts=rc.get("createdTs"),
                        created_by=rc.get("createdBy"),
                        updated_ts=rc.get("updatedTs"),
                        updated_by=rc.get("updatedBy")
                    )

                # Парсим финальный результат
                result_final = None
                if grade_data.get("resultFinal"):
                    rf = grade_data["resultFinal"]
                    result_final = GradeResult(
                        id=rf.get("id"),
                        control_object_id=rf.get("controlObjectId"),
                        result_value=rf.get("resultValue", ""),
                        created_ts=rf.get("createdTs"),
                        created_by=rf.get("createdBy"),
                        updated_ts=rf.get("updatedTs"),
                        updated_by=rf.get("updatedBy")
                    )

                course_grade = CourseGrade(
                    control_object_id=grade_data.get("controlObjectId", ""),
                    type_name=grade_data.get("typeName", ""),
                    type_short_name=grade_data.get("typeShortName", ""),
                    type_code=grade_data.get("typeCode", ""),
                    order_index=grade_data.get("orderIndex", 0),
                    course_unit_realization_id=course_unit_id,
                    course_unit_name=course_unit_names.get(course_unit_id),
                    main_grading_scale_code=grade_data.get("mainGradingScaleCode", ""),
                    result_current=result_current,
                    result_final=result_final
                )
                course_grades.append(course_grade)

            return Grades(course_grades=course_grades)

        except Exception as e:
            raise RuntimeError(f"Ошибка при получении оценок: {e}")

    @require_auth
    async def get_attendance(self, academic_period_id: Optional[str] = None) -> Attendance:
        """
        Получить посещаемость

        Args:
            academic_period_id: ID академического периода (семестра). Если None, используется текущий.

        Returns:
            Объект Attendance с посещаемостью
        """
        try:
            # Получаем информацию о студенте
            primary_data = await self._api_request(
                "GET",
                "/students-app/api/pages/student-card/my/primary"
            )

            person_id = primary_data.get("personId")
            student_id = primary_data.get("id")
            curriculum_flow_id = primary_data.get("curriculumFlow", {}).get("id")
            curriculum_plan_id = primary_data.get("curriculumFlow", {}).get("curriculumPlanId")

            # Если не указан период, берем текущий
            if not academic_period_id:
                periods = primary_data.get("academicPeriodRealizations", [])
                if not periods:
                    raise RuntimeError("Нет доступных академических периодов")

                from datetime import datetime
                today = datetime.now().date()

                for period in periods:
                    start = datetime.fromisoformat(period["startDate"]).date()
                    end = datetime.fromisoformat(period["endDate"]).date()
                    if start <= today <= end:
                        academic_period_id = period["id"]
                        break

                if not academic_period_id:
                    academic_period_id = periods[-1]["id"]

            # Получаем список предметов для периода
            primary_table = await self._api_request(
                "POST",
                "/students-app/api/pages/student-card/my/academic-period-results-table/primary",
                json={
                    "personId": person_id,
                    "withMidcheckModulesIncluded": False,
                    "aprId": academic_period_id,
                    "studentId": student_id,
                    "curriculumFlowId": curriculum_flow_id,
                    "curriculumPlanId": curriculum_plan_id
                }
            )

            course_unit_ids = [cu["id"] for cu in primary_table.get("courseUnitRealizations", [])]
            academic_course_ids = [ac["id"] for ac in primary_table.get("academicCourses", [])]

            # Создаем словарь названий предметов
            course_unit_names = {cu["id"]: cu["name"] for cu in primary_table.get("courseUnitRealizations", [])}

            # Запрашиваем данные
            grades_data = await self._api_request(
                "POST",
                "/students-app/api/pages/student-card/my/academic-period-results-table/secondary",
                json={
                    "courseUnitRealizationId": course_unit_ids,
                    "academicCourseId": academic_course_ids,
                    "personId": person_id,
                    "studentId": student_id
                }
            )

            # Парсим посещаемость
            attendance_rates = []
            for att_data in grades_data.get("courseUnitRealizationAttendanceRates", []):
                course_unit_id = att_data.get("courseUnitRealizationId", "")
                attendance = AttendanceRate(
                    course_unit_realization_id=course_unit_id,
                    course_unit_name=course_unit_names.get(course_unit_id),
                    present_rate=att_data.get("presentRate", 0.0),
                    absent_rate=att_data.get("absentRate", 0.0),
                    undefined_rate=att_data.get("undefinedRate", 0.0)
                )
                attendance_rates.append(attendance)

            return Attendance(attendance_rates=attendance_rates)

        except Exception as e:
            raise RuntimeError(f"Ошибка при получении посещаемости: {e}")
