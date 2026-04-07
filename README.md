# MODEUS API Client

Асинхронный Python клиент для работы с API системы MODEUS.

## Возможности

- Авторизация в системе MODEUS
- Получение расписания занятий
- Получение оценок и результатов обучения
- Получение данных о посещаемости
- Поиск пользователей
- Асинхронная работа с API

## Установка

```bash
pip install -r requirements.txt
```

## Быстрый старт

```python
import asyncio
from datetime import datetime, timedelta
from modeus_client import ModeusClient

async def main():
    async with ModeusClient() as client:
        # Авторизация
        await client.login(
            username="your_email@study.university.ru",
            password="your_password"
        )
        
        # Получение расписания на неделю
        today = datetime.now()
        week_later = today + timedelta(days=7)
        timetable = await client.get_timetable(today, week_later)
        
        # Вывод расписания
        for lesson in timetable.lessons:
            print(f"{lesson.start.strftime('%d.%m %H:%M')} - {lesson.subject.name}")
            print(f"  Аудитория: {lesson.location.full if lesson.location else 'Не указана'}")
            print(f"  Преподаватели: {', '.join(t.full_name for t in lesson.teachers)}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Примеры использования

### Получение расписания

```python
from datetime import datetime, timedelta
from modeus_client import ModeusClient

async with ModeusClient() as client:
    await client.login(username="...", password="...")
    
    # Расписание на неделю
    today = datetime.now()
    week_later = today + timedelta(days=7)
    timetable = await client.get_timetable(today, week_later)
    
    # Группировка по дням
    by_day = timetable.get_lessons_by_day()
    for day, lessons in by_day.items():
        print(f"\n{day}:")
        for lesson in lessons:
            print(f"  {lesson.start.strftime('%H:%M')} - {lesson.name}")
```

### Получение оценок

```python
from modeus_client import ModeusClient

async with ModeusClient() as client:
    await client.login(username="...", password="...")
    
    # Получение оценок
    grades = await client.get_grades()
    
    for grade in grades.course_grades:
        print(f"\n{grade.course_unit_name}")
        print(f"  Тип: {grade.type_short_name}")
        if grade.result_current:
            print(f"  Текущая оценка: {grade.result_current.result_value}")
        if grade.result_final:
            print(f"  Финальная оценка: {grade.result_final.result_value}")
```

### Получение посещаемости

```python
from modeus_client import ModeusClient

async with ModeusClient() as client:
    await client.login(username="...", password="...")
    
    # Получение посещаемости
    attendance = await client.get_attendance()
    
    for att in attendance.attendance_rates:
        print(f"\n{att.course_unit_name}")
        print(f"  Присутствие: {att.present_rate * 100:.0f}%")
        print(f"  Отсутствие: {att.absent_rate * 100:.0f}%")
```

### Поиск пользователей

```python
from modeus_client import ModeusClient

async with ModeusClient() as client:
    await client.login(username="...", password="...")
    
    # Поиск по имени
    people = await client.search_person("Иванов")
    
    for person in people:
        print(f"{person.full_name} (ID: {person.id})")
```

## API Reference

### ModeusClient

Основной класс для работы с API MODEUS.

#### Методы

- `login(username: str, password: str) -> bool` - Авторизация в системе
- `get_timetable(from_date: datetime, to_date: datetime, person_id: Optional[str] = None) -> Timetable` - Получение расписания
- `get_grades(academic_period_id: Optional[str] = None) -> Grades` - Получение оценок
- `get_attendance(academic_period_id: Optional[str] = None) -> Attendance` - Получение посещаемости
- `search_person(name: str, limit: int = 25) -> list[Person]` - Поиск пользователей
- `get_person_info(person_id: str) -> Optional[Person]` - Получение информации о пользователе

### Модели данных

#### Lesson
Информация о занятии:
- `id` - ID занятия
- `subject` - Предмет (Subject)
- `name` - Название занятия
- `start` - Время начала
- `end` - Время окончания
- `location` - Местоположение (Location)
- `teachers` - Список преподавателей (list[Person])
- `lesson_type` - Тип занятия
- `format` - Формат проведения

#### Timetable
Расписание:
- `lessons` - Список занятий
- `from_date` - Начальная дата
- `to_date` - Конечная дата
- `get_lessons_by_date(date)` - Получить занятия на дату
- `get_lessons_by_day()` - Сгруппировать по дням

#### CourseGrade
Оценка по предмету:
- `course_unit_name` - Название предмета
- `type_name` - Тип контроля
- `type_short_name` - Краткое название типа
- `result_current` - Текущая оценка (GradeResult)
- `result_final` - Финальная оценка (GradeResult)

#### AttendanceRate
Посещаемость по предмету:
- `course_unit_name` - Название предмета
- `present_rate` - Процент присутствия (0.0-1.0)
- `absent_rate` - Процент отсутствия (0.0-1.0)
- `undefined_rate` - Процент неотмеченных (0.0-1.0)

## Требования

- Python 3.8+
- aiohttp
- beautifulsoup4

## Лицензия

Этот проект распространяется под лицензией MIT. Подробности см. в файле [LICENSE](LICENSE).

## Примечание

Этот клиент предназначен только для образовательных целей. Используйте его ответственно и в соответствии с правилами использования системы MODEUS вашего учебного заведения.
