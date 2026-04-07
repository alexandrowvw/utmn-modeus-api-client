"""
Пример получения расписания на неделю
"""

import asyncio
from datetime import datetime, timedelta
from modeus_client import ModeusClient


async def main():
    async with ModeusClient() as client:
        # Авторизация
        print("Авторизация...")
        success = await client.login(
            username="your_email@study.university.ru",
            password="your_password"
        )

        if not success:
            print("Ошибка авторизации!")
            return

        print("Авторизация успешна!\n")

        # Получаем расписание на неделю
        today = datetime.now()
        week_later = today + timedelta(days=7)

        print(f"Получение расписания с {today.strftime('%d.%m.%Y')} по {week_later.strftime('%d.%m.%Y')}...")
        timetable = await client.get_timetable(today, week_later)

        print(f"\nНайдено занятий: {len(timetable.lessons)}\n")

        # Группируем по дням
        by_day = timetable.get_lessons_by_day()

        # Выводим расписание
        print("="*80)
        print("РАСПИСАНИЕ НА НЕДЕЛЮ")
        print("="*80)

        for day, lessons in sorted(by_day.items()):
            day_date = datetime.strptime(day, "%Y-%m-%d")
            print(f"\n{day_date.strftime('%A, %d %B %Y')}:")
            print("-"*80)

            for lesson in lessons:
                print(f"\n  {lesson.start.strftime('%H:%M')} - {lesson.end.strftime('%H:%M')}")
                print(f"  {lesson.subject.name}")
                print(f"  Тип: {lesson.lesson_type or 'Не указан'}")

                if lesson.location and lesson.location.full:
                    print(f"  Аудитория: {lesson.location.full}")

                if lesson.teachers:
                    teachers = ", ".join(t.full_name for t in lesson.teachers)
                    print(f"  Преподаватели: {teachers}")

                if lesson.format:
                    print(f"  Формат: {lesson.format}")


if __name__ == "__main__":
    asyncio.run(main())
