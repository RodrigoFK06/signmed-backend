"""
Asigna el rol PATIENT a los usuarios antiguos que no lo tienen.

Uso:
    python -m scripts.backfill_user_role
"""
import asyncio

from app.db.mongodb import get_collections


async def main() -> None:
    result = await get_collections().users.update_many(
        {"role": {"$exists": False}},
        {"$set": {"role": "PATIENT"}},
    )
    print(f"Usuarios actualizados: {result.modified_count}")


if __name__ == "__main__":
    asyncio.run(main())
