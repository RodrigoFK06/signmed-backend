"""
Script rápido para crear admin con credenciales predefinidas
"""
import sys
from pathlib import Path
from datetime import datetime
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
from motor.motor_asyncio import AsyncIOMotorClient
from app.services.auth import hash_password

load_dotenv()

async def create_quick_admin():
    # Credenciales predefinidas
    email = "admin@signmed.com"
    nickname = "admin"
    password = "Admin123456"
    
    MONGO_URI = os.getenv("MONGO_URI")
    if not MONGO_URI:
        print("❌ Error: MONGO_URI no está configurado")
        return
    
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["sign_language"]
    users_collection = db["users"]
    
    try:
        # Verificar si existe
        existing = await users_collection.find_one({"email": email})
        
        if existing:
            print(f"⚠️  Usuario {email} ya existe")
            # Actualizar a admin
            await users_collection.update_one(
                {"email": email},
                {"$set": {
                    "role": "ADMIN",
                    "status": "approved",
                    "password_hash": hash_password(password)
                }}
            )
            print("✅ Usuario actualizado a ADMIN")
        else:
            # Crear nuevo
            doc = {
                "email": email,
                "password_hash": hash_password(password),
                "nickname": nickname,
                "role": "ADMIN",
                "status": "approved",
                "created_at": datetime.utcnow(),
            }
            result = await users_collection.insert_one(doc)
            print(f"✅ Admin creado: {result.inserted_id}")
        
        print("\n" + "="*50)
        print("📋 CREDENCIALES:")
        print(f"📧 Email:    {email}")
        print(f"🔑 Password: {password}")
        print(f"👤 Nickname: {nickname}")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(create_quick_admin())
