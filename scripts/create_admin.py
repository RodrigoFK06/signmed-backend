"""
Script para crear un usuario administrador en MongoDB.
Ejecutar: python create_admin.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from app.services.auth import hash_password
import asyncio

# Cargar variables de entorno
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("❌ Error: MONGO_URI no está configurado en .env")
    sys.exit(1)

async def create_admin_user():
    """Crear usuario administrador"""
    
    # Datos del admin
    print("\n🔐 CREACIÓN DE USUARIO ADMINISTRADOR")
    print("=" * 50)
    
    email = input("📧 Email del admin: ").strip().lower()
    if not email:
        print("❌ Email es requerido")
        return
    
    nickname = input("👤 Nickname del admin: ").strip()
    if not nickname:
        print("❌ Nickname es requerido")
        return
    
    password = input("🔑 Contraseña del admin: ").strip()
    if not password or len(password) < 6:
        print("❌ La contraseña debe tener al menos 6 caracteres")
        return
    
    # Conectar a MongoDB
    print("\n📡 Conectando a MongoDB...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["sign_language"]
    users_collection = db["users"]
    
    try:
        # Verificar si el email ya existe
        existing_user = await users_collection.find_one({"email": email})
        if existing_user:
            print(f"⚠️  Ya existe un usuario con el email: {email}")
            update = input("¿Deseas actualizar este usuario a ADMIN? (s/n): ").strip().lower()
            if update == 's':
                result = await users_collection.update_one(
                    {"email": email},
                    {"$set": {
                        "role": "ADMIN",
                        "status": "approved",
                        "updated_at": datetime.utcnow()
                    }}
                )
                if result.modified_count > 0:
                    print("✅ Usuario actualizado a ADMIN exitosamente")
                else:
                    print("❌ No se pudo actualizar el usuario")
            return
        
        # Crear nuevo usuario admin
        admin_doc = {
            "email": email,
            "password_hash": hash_password(password),
            "nickname": nickname,
            "role": "ADMIN",
            "status": "approved",
            "created_at": datetime.utcnow(),
        }
        
        result = await users_collection.insert_one(admin_doc)
        
        print("\n✅ Usuario administrador creado exitosamente!")
        print("\n📋 CREDENCIALES DEL ADMINISTRADOR:")
        print("=" * 50)
        print(f"📧 Email:    {email}")
        print(f"👤 Nickname: {nickname}")
        print(f"🔑 Password: {password}")
        print(f"🆔 ID:       {result.inserted_id}")
        print("=" * 50)
        print("\n⚠️  GUARDA ESTAS CREDENCIALES EN UN LUGAR SEGURO")
        print("💡 Ahora puedes iniciar sesión en /auth/login")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(create_admin_user())
