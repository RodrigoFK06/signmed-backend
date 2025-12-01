#!/usr/bin/env python3
"""
Script de verificación para diagnosticar problemas de startup en la API.
Ejecuta checks básicos sin cargar modelos pesados.
"""

import sys
import os
from pathlib import Path

def check_imports():
    """Verifica que se puedan importar los módulos principales sin errores."""
    print("🔍 Verificando imports básicos...")
    
    try:
        import fastapi
        print("✅ FastAPI: OK")
    except ImportError as e:
        print(f"❌ FastAPI: Error - {e}")
        return False
    
    try:
        from app.config import BASE_DIR, DATA_DIR, MODELS_DIR, DATASET_PATH
        print("✅ Config: OK")
        print(f"   BASE_DIR: {BASE_DIR}")
        print(f"   DATA_DIR: {DATA_DIR}")
        print(f"   MODELS_DIR: {MODELS_DIR}")
        print(f"   DATASET_PATH: {DATASET_PATH}")
    except ImportError as e:
        print(f"❌ Config: Error - {e}")
        return False
    
    try:
        from app.api.router import router
        print("✅ Router: OK")
    except ImportError as e:
        print(f"❌ Router: Error - {e}")
        return False
    
    return True

def check_paths():
    """Verifica que existan los directorios y archivos necesarios."""
    print("\n🔍 Verificando rutas y archivos...")
    
    try:
        from app.config import BASE_DIR, DATA_DIR, MODELS_DIR, DATASET_PATH
        
        # Verificar directorios
        for path, name in [(BASE_DIR, "BASE_DIR"), (DATA_DIR, "DATA_DIR"), (MODELS_DIR, "MODELS_DIR")]:
            if path.exists():
                print(f"✅ {name}: {path} - Existe")
            else:
                print(f"⚠️ {name}: {path} - No existe")
        
        # Verificar archivo de dataset
        if DATASET_PATH.exists():
            print(f"✅ Dataset: {DATASET_PATH} - Existe")
        else:
            print(f"⚠️ Dataset: {DATASET_PATH} - No existe")
            
    except Exception as e:
        print(f"❌ Error verificando rutas: {e}")
        return False
    
    return True

def check_environment():
    """Verifica variables de entorno importantes."""
    print("\n🔍 Verificando variables de entorno...")
    
    # Variables críticas
    env_vars = {
        "MONGO_URI": "Conexión a MongoDB",
        "MODEL_PATH": "Ruta del modelo (opcional)",
        "ENCODER_PATH": "Ruta del encoder (opcional)"
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            # Mostrar solo parte de las URIs sensibles
            if "URI" in var and len(value) > 20:
                display_value = value[:20] + "..."
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"⚠️ {var}: No definida - {description}")

def check_basic_api():
    """Verifica que se pueda crear la aplicación FastAPI básica."""
    print("\n🔍 Verificando creación de API...")
    
    try:
        from app.main import app
        print("✅ App FastAPI: Creada exitosamente")
        
        # Verificar rutas básicas
        routes = [route.path for route in app.routes]
        expected_routes = ["/", "/health"]
        
        for route in expected_routes:
            if route in routes:
                print(f"✅ Ruta {route}: Registrada")
            else:
                print(f"❌ Ruta {route}: No encontrada")
                
        return True
    except Exception as e:
        print(f"❌ Error creando app: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Ejecuta todos los checks de verificación."""
    print("🚀 VERIFICACIÓN DE STARTUP - Medical Sign Recognition API")
    print("=" * 60)
    
    checks = [
        ("Imports básicos", check_imports),
        ("Rutas y archivos", check_paths),  
        ("Variables de entorno", check_environment),
        ("API básica", check_basic_api)
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n📋 {name}")
        print("-" * 40)
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error en {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Todos los checks pasaron. La API debería iniciar correctamente.")
        return 0
    else:
        print("\n⚠️ Algunos checks fallaron. Revisa los errores antes del deployment.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
