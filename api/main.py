import os
import socket
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor

# Conexión usando el DNS interno de K8s: <service>.<namespace>.svc.cluster.local
DB_HOST = os.getenv("DB_HOST", "postgres-svc.parcial2-app.svc.cluster.local")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "parcialdb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres123")

# Función para obtener la conexión a la base de datos
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
        connect_timeout=3,
    )

# Definición del modelo de datos para la creación de un item
class ItemCreate(BaseModel):
    nombre: str
    descripcion: str

# Inicialización de la base de datos al iniciar la aplicación
def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    descripcion TEXT
                );
                """
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Esperando conexión a la BD en {DB_HOST}: {e}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="API REST - Parcial II", lifespan=lifespan)


# Endpoint para verificar la salud de la aplicación y la conexión a la base de datos
@app.get("/health")
def health_check():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        conn.close()
        return {
            "status": "healthy",
            "pod_replica": socket.gethostname(),
            "db_dns": DB_HOST,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB Error: {str(e)}")

# Endpoint para listar todos los items en la base de datos
@app.get("/items")
def listar_items():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM items ORDER BY id ASC;")
        items = cur.fetchall()
    conn.close()
    return {
        "pod_replica": socket.gethostname(),
        "items": items,
    }

# Endpoint para crear un nuevo item en la base de datos
@app.post("/items", status_code=201)
def crear_item(item: ItemCreate):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO items (nombre, descripcion) VALUES (%s, %s) RETURNING *;",
            (item.nombre, item.descripcion),
        )
        nuevo = cur.fetchone()
    conn.commit()
    conn.close()
    return {
        "pod_replica": socket.gethostname(),
        "item": nuevo,
    }