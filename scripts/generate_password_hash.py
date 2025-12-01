"""
Script para generar el hash de una contraseña.
Útil para crear usuarios manualmente en MongoDB.
Ejecutar: python generate_password_hash.py
"""
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.auth import hash_password

def main():
    print("\n🔐 GENERADOR DE HASH DE CONTRASEÑA")
    print("=" * 50)
    
    password = input("Ingresa la contraseña: ").strip()
    
    if not password:
        print("❌ La contraseña no puede estar vacía")
        return
    
    if len(password) < 6:
        print("⚠️  Advertencia: La contraseña es muy corta (mínimo recomendado: 6 caracteres)")
    
    password_hash = hash_password(password)
    
    print("\n✅ Hash generado exitosamente:")
    print("=" * 50)
    print(password_hash)
    print("=" * 50)
    print("\n💡 Copia este hash para usar en MongoDB")
    print("💡 Campo: password_hash")

if __name__ == "__main__":
    main()
