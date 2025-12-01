# Script PowerShell para generar hash de contraseña
# Uso: .\generate_password_hash.ps1

Write-Host "`n🔐 GENERADOR DE HASH DE CONTRASEÑA" -ForegroundColor Cyan
Write-Host ("=" * 50) -ForegroundColor Gray

$password = Read-Host "Ingresa la contraseña"

if ([string]::IsNullOrWhiteSpace($password)) {
    Write-Host "❌ La contraseña no puede estar vacía" -ForegroundColor Red
    exit
}

if ($password.Length -lt 6) {
    Write-Host "⚠️  Advertencia: La contraseña es muy corta (mínimo recomendado: 6 caracteres)" -ForegroundColor Yellow
}

# Instalar Passlib si no está instalado
Write-Host "`n📦 Verificando dependencias..." -ForegroundColor Cyan

# Comando Python para generar el hash
$pythonScript = @"
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')
print(pwd_context.hash('$password'))
"@

try {
    $hash = python -c $pythonScript
    
    Write-Host "`n✅ Hash generado exitosamente:" -ForegroundColor Green
    Write-Host ("=" * 50) -ForegroundColor Gray
    Write-Host $hash -ForegroundColor White
    Write-Host ("=" * 50) -ForegroundColor Gray
    Write-Host "`n💡 Copia este hash para usar en MongoDB" -ForegroundColor Yellow
    Write-Host "💡 Campo: password_hash" -ForegroundColor Yellow
    
    # Copiar al portapapeles si está disponible
    if (Get-Command Set-Clipboard -ErrorAction SilentlyContinue) {
        $hash | Set-Clipboard
        Write-Host "`n📋 Hash copiado al portapapeles!" -ForegroundColor Green
    }
}
catch {
    Write-Host "`n❌ Error al generar el hash: $_" -ForegroundColor Red
    Write-Host "💡 Asegúrate de tener Python y passlib instalados" -ForegroundColor Yellow
    Write-Host "   Instalar con: pip install passlib" -ForegroundColor Gray
}
