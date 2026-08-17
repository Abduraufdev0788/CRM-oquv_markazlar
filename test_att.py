import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.iot import Attendance

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Attendance))
        atts = res.scalars().all()
        for a in atts:
            print(f"ID: {a.id}, Student: {a.student_id}, Lesson: {a.lesson_id}, Status: {a.status}")

asyncio.run(main())
