import asyncio
from app.db.mongodb import users_collection

async def run():
    res = await users_collection.update_many({"role":{"$exists":False}}, {"$set":{"role":"PATIENT"}})
    print(f"✅ Backfill: {res.modified_count} usuarios actualizados")

if __name__ == "__main__":
    asyncio.run(run())
