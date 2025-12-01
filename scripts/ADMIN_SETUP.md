# 🚀 Setup Rápido del Administrador

## Método más rápido: MongoDB Compass

### Paso 1: Abre MongoDB Compass
- Conéctate a tu base de datos usando la URI de `.env`

### Paso 2: Navega a la colección
- Base de datos: `sign_language`
- Colección: `users`

### Paso 3: Inserta el documento
Click en "ADD DATA" → "Insert Document" y pega esto:

```json
{
  "email": "admin@signmed.com",
  "password_hash": "$pbkdf2-sha256$29000$3pvzPqd0Tmlt7V0rRehdCw$EqWLBWW7O.LuJlL9gLjYW0z0T4OQxZs5xYPq8LqTzlI",
  "nickname": "admin",
  "role": "ADMIN",
  "status": "approved",
  "created_at": { "$date": "2025-11-09T00:00:00.000Z" }
}
```

### Paso 4: Click en "Insert"

---

## 🔑 Credenciales Creadas

```
📧 Email:    admin@signmed.com
🔑 Password: Admin123456
👤 Nickname: admin
🎭 Role:     ADMIN
```

---

## 🧪 Probar el Login

1. Inicia el frontend: `npm run dev` (puerto 3000)
2. Ve a: `http://localhost:3000/auth/login`
3. Ingresa:
   - Email: `admin@signmed.com`
   - Password: `Admin123456`
4. Deberías ver el enlace "Administración" en el menú

---

## 🔄 Alternativa: Actualizar usuario existente

Si ya tienes un usuario y quieres hacerlo admin:

En MongoDB Compass, en la colección `users`:
1. Busca tu usuario por email
2. Click en editar (ícono de lápiz)
3. Cambia:
   - `"role": "ADMIN"`
   - `"status": "approved"`
4. Guarda los cambios

---

## ⚠️ Notas Importantes

- **CAMBIAR** la contraseña en producción
- El hash proporcionado es para la contraseña: `Admin123456`
- Solo crear 1-2 usuarios admin como máximo
- Los admins pueden:
  - Ver solicitudes de trabajadores de salud pendientes
  - Aprobar/rechazar solicitudes
  - Acceder a `/admin`

---

## 🐛 Si algo falla

### "No puedo ver el panel de admin"
- Verifica que el rol sea exactamente `"ADMIN"` (mayúsculas)
- Verifica que el status sea `"approved"`
- Cierra sesión y vuelve a iniciar sesión

### "El email ya existe"
- Usa el método de actualización de usuario
- O cambia el email del nuevo admin

### "No puedo iniciar sesión"
- Verifica que el password_hash sea correcto
- Prueba regenerando el hash con: `python scripts/generate_password_hash.py`
