from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Leer la URI desde la variable de entorno
MONGO_URI = os.getenv("MONGO_URI")

# Validación mínima
if not MONGO_URI:
    raise RuntimeError("❌ MONGO_URI no está definida. Crea un archivo .env con la variable.")

# Definir nombre de base de datos y colección
MONGO_DB = "sign_language"
MONGO_COLLECTION = "predictions"
MONGO_STATS_COLLECTION = "prediction_stats"
USERS_COLLECTION = "users"
EXAMS_COLLECTION = "exams"
EXAM_ATTEMPTS_COLLECTION = "exam_attempts"

# Cliente y conexión
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]
stats_collection = db[MONGO_STATS_COLLECTION]
users_collection = db[USERS_COLLECTION]
exams_collection = db[EXAMS_COLLECTION]
exam_attempts_collection = db[EXAM_ATTEMPTS_COLLECTION]
