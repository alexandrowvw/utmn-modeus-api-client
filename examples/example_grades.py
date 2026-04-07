"""
Пример получения оценок и посещаемости
"""

import asyncio
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

        # Получаем оценки
        print("Получение оценок...")
        grades = await client.get_grades()

        print(f"\nОценки по предметам: {len(grades.course_grades)}\n")

        # Выводим оценки
        print("="*60)
        print("ОЦЕНКИ ПО ПРЕДМЕТАМ")
        print("="*60)

        for grade in grades.course_grades:
            subject_name = grade.course_unit_name or "Неизвестный предмет"
            print(f"\n{subject_name}")
            print(f"  Тип: {grade.type_short_name} ({grade.type_name})")

            if grade.result_current:
                print(f"  Текущая оценка: {grade.result_current.result_value}")
                if grade.result_current.created_by:
                    print(f"  Выставил: {grade.result_current.created_by}")

            if grade.result_final:
                print(f"  Финальная оценка: {grade.result_final.result_value}")

        # Получаем посещаемость
        print("\n\nПолучение посещаемости...")
        attendance = await client.get_attendance()

        print(f"Посещаемость: {len(attendance.attendance_rates)}\n")

        # Выводим посещаемость
        print("="*60)
        print("ПОСЕЩАЕМОСТЬ")
        print("="*60)

        for att in attendance.attendance_rates:
            subject_name = att.course_unit_name or f"ID: {att.course_unit_realization_id[:8]}..."
            print(f"\n{subject_name}")
            print(f"  Присутствие: {att.present_rate * 100:.0f}%")
            print(f"  Отсутствие: {att.absent_rate * 100:.0f}%")
            print(f"  Не отмечено: {att.undefined_rate * 100:.0f}%")


if __name__ == "__main__":
    asyncio.run(main())
