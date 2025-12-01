"""
Script para verificar los intentos de examen y sus usuarios.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

async def check_attempts():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.get_database("sign_language")
    
    exam_attempts_collection = db.exam_attempts
    users_collection = db.users
    
    print("\n🔍 Verificando intentos de examen...\n")
    
    async for attempt in exam_attempts_collection.find():
        attempt_id = str(attempt["_id"])
        user_id = attempt.get("user_id")
        exam_id = attempt.get("exam_id")
        
        print(f"📝 Intento: {attempt_id}")
        print(f"   User ID: {user_id} (tipo: {type(user_id)})")
        print(f"   Exam ID: {exam_id}")
        print(f"   Score: {attempt.get('score')}")
        print(f"   Completed: {attempt.get('completed_at')}")
        
        # Buscar usuario
        user = await users_collection.find_one({"_id": user_id})
        if user:
            print(f"   ✅ Usuario encontrado: {user.get('nickname')} ({user.get('email')})")
        else:
            print(f"   ❌ Usuario NO encontrado")
            print(f"   🔍 Buscando usuarios similares...")
            
            # Intentar buscar por string
            if isinstance(user_id, ObjectId):
                user_str = await users_collection.find_one({"_id": str(user_id)})
                if user_str:
                    print(f"      ⚠️ Encontrado como string: {user_str.get('nickname')}")
            
            # Listar todos los usuarios
            print(f"   📋 Usuarios disponibles:")
            async for u in users_collection.find():
                print(f"      - {u.get('nickname')} | ID: {u['_id']} (tipo: {type(u['_id'])})")
        
        print()
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_attempts())
