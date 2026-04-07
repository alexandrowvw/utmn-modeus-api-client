"""
Пример поиска пользователей
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

        # Поиск пользователя
        search_query = input("Введите имя или фамилию для поиска: ")

        print(f"\nПоиск '{search_query}'...")
        people = await client.search_person(search_query, limit=10)

        if not people:
            print("Никого не найдено")
            return

        print(f"\nНайдено: {len(people)}\n")
        print("="*80)

        for i, person in enumerate(people, 1):
            print(f"\n{i}. {person.full_name}")
            print(f"   ID: {person.id}")
            print(f"   Имя: {person.first_name}")
            print(f"   Фамилия: {person.last_name}")
            if person.middle_name:
                print(f"   Отчество: {person.middle_name}")


if __name__ == "__main__":
    asyncio.run(main())
