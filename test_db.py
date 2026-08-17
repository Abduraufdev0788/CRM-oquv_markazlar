import asyncio
import pytz
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select
from app.models.academic import Group, Room, GroupStatus
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL)

async def test_logic():
    async with AsyncSession(engine) as db:
        tz = pytz.timezone('Asia/Tashkent')
        now = datetime.now(tz)
        current_day = now.strftime("%A").lower()
        current_time = now.strftime("%H:%M")
        print(f"Current Day: {current_day}, Current Time: {current_time}")

        active_groups = (await db.execute(
            select(Group).where(Group.status != GroupStatus.ARCHIVED, Group.room_id.is_not(None))
        )).scalars().all()
        
        print(f"Total non-archived groups with rooms: {len(active_groups)}")

        occupied_room_ids = []
        for g in active_groups:
            print(f"Group: {g.name}, Room ID: {g.room_id}, Schedule: {g.schedule}")
            if not isinstance(g.schedule, list):
                continue
            for s in g.schedule:
                if s.get("day") == current_day:
                    start_time = s.get("start", "")[:5]
                    end_time = s.get("end", "")[:5]
                    print(f"  -> Match day: start={start_time}, end={end_time}, current={current_time}")
                    if start_time and end_time and start_time <= current_time <= end_time:
                        occupied_room_ids.append(g.room_id)
                        print(f"  -> OCCUPIED! Room ID: {g.room_id}")
                        break
                        
        print(f"Occupied Room IDs: {occupied_room_ids}")
        
        query = select(Room)
        if occupied_room_ids:
            query = query.where(Room.id.not_in(occupied_room_ids))
            
        rooms = (await db.execute(query)).scalars().all()
        print(f"Available Rooms returned: {len(rooms)}")
        for r in rooms:
            print(f" - {r.name}")

if __name__ == "__main__":
    asyncio.run(test_logic())
