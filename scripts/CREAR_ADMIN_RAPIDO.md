# 🔐 Guía Rápida: Crear Usuario Administrador

## Opción 1: Script Python (Recomendado)

### Paso 1: Navegar al directorio del proyecto
```powershell
cd "d:\Desktop\MachineLearning definitivo\PythonProject\machinelear"
```

### Paso 2: Activar el entorno virtual (si aplica)
```powershell
# Si usas venv
.\venv\Scripts\Activate.ps1

# O si usas conda
conda activate tu_entorno
```

### Paso 3: Ejecutar el script
```powershell
python scripts/create_admin.py
```

### Paso 4: Ingresar los datos
El script te pedirá:
- 📧 Email del admin
- 👤 Nickname del admin
- 🔑 Contraseña del admin (mínimo 6 caracteres)

### Ejemplo de uso:
```
📧 Email del admin: admin@signmed.com
👤 Nickname del admin: admin
🔑 Contraseña del admin: Admin123456
```

---

## Opción 2: MongoDB Compass / MongoDB Shell

### Usando MongoDB Compass:

1. Abre MongoDB Compass y conéctate a tu base de datos
2. Ve a la base de datos `sign_language`
3. Selecciona la colección `users`
4. Click en "Insert Document"
5. Pega el siguiente JSON (reemplaza los valores):

```json
{
  "email": "admin@signmed.com",
  "password_hash": "$pbkdf2-sha256$29000$...",
  "nickname": "admin",
  "role": "ADMIN",
  "status": "approved",
  "created_at": {"$date": "2025-11-09T00:00:00.000Z"}
}
```

**⚠️ IMPORTANTE:** Necesitas generar el hash de la contraseña primero.

### Para generar el hash de la contraseña:

```powershell
python scripts/generate_password_hash.py
```

---

## Opción 3: Usando MongoDB Shell

```javascript
use sign_language

db.users.insertOne({
  "email": "admin@signmed.com",
  "password_hash": "$pbkdf2-sha256$29000$...", // Genera esto primero
  "nickname": "admin",
  "role": "ADMIN",
  "status": "approved",
  "created_at": new Date()
})
```

---

## 🧪 Verificar la creación

### Opción A: MongoDB Compass
1. Busca en la colección `users`
2. Filtra por: `{ "role": "ADMIN" }`

### Opción B: Python
```python
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def check_admin():
    client = AsyncIOMotorClient("tu_mongo_uri")
    db = client["sign_language"]
    admin = await db.users.find_one({"role": "ADMIN"})
    print(admin)
    client.close()

asyncio.run(check_admin())
```

---

## 🎯 Iniciar Sesión

Una vez creado el usuario admin:

1. Ve a la aplicación: `http://localhost:3000/auth/login`
2. Ingresa las credenciales:
   - Email: `admin@signmed.com`
   - Password: `[tu contraseña]`
3. Una vez autenticado, verás el enlace "Administración" en el menú
4. Click en "Administración" para acceder al panel de admin en `/admin`

---

## 🔒 Credenciales de Ejemplo

**⚠️ SOLO PARA DESARROLLO - CAMBIAR EN PRODUCCIÓN**

```
Email: admin@signmed.com
Password: Admin123456
Nickname: admin
Role: ADMIN
```

---

## 🐛 Solución de Problemas

### Error: "MONGO_URI no está configurado"
- Verifica que el archivo `.env` existe
- Verifica que `MONGO_URI` está definido en `.env`

### Error: "Email ya existe"
- El script te preguntará si quieres actualizar el usuario existente a ADMIN
- Responde `s` para actualizar

### Error de conexión a MongoDB
- Verifica que MongoDB está corriendo
- Verifica que la URI es correcta
- Verifica que tienes conexión a internet (si usas MongoDB Atlas)

---

## 📝 Notas de Seguridad

1. **Nunca** compartas las credenciales de admin
2. **Cambia** la contraseña predeterminada en producción
3. **Usa** contraseñas fuertes (mínimo 12 caracteres, mayúsculas, minúsculas, números y símbolos)
4. **Limita** el número de usuarios con rol ADMIN
5. **Monitorea** las acciones de los administradores
