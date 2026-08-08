import asyncio
from httpx import AsyncClient

async def test():
    async with AsyncClient(base_url="http://localhost:8001/api/v1") as client:
        # User auth token or something? The endpoint requires AnyStaff.
        # But wait, without token we get 401 Unauthorized, not 500 Internal Server Error.
        # Let's hit the endpoint to see if it's 401 or 500.
        res = await client.get("/groups/353e900e-9ca9-4b6b-82a5-0b2a77ddb0cd/students")
        print("Status:", res.status_code)
        print("Body:", res.text)

if __name__ == "__main__":
    asyncio.run(test())
