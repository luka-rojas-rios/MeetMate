import sqlite3
import psycopg2
from psycopg2 import sql

# --- 1. Conectar a SQLite ---
sqlite_conn = sqlite3.connect('meetmate.db')
sqlite_cursor = sqlite_conn.cursor()

# --- 2. Conectar a PostgreSQL ---
pg_conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database="MeetMate",  # nombre de la nueva base
    user="postgres",
    password="monica"  # <-- Pon tu contraseña aquí
)
pg_cursor = pg_conn.cursor()

# --- 3. Obtener todas las tablas en SQLite ---
sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = sqlite_cursor.fetchall()

for table_name_tuple in tables:
    table_name = table_name_tuple[0]
    print(f"Migrando tabla: {table_name}")

    # --- 4. Leer los datos de SQLite ---
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = sqlite_cursor.fetchall()
    columns = [col[1] for col in columns_info]  # nombre de columnas
    columns_def = ", ".join([f"{col[1]} TEXT" for col in columns_info])  # todo como texto por simplicidad

    # --- 5. Crear tabla en PostgreSQL ---
    create_table_query = sql.SQL(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_def});")
    pg_cursor.execute(create_table_query)

    # --- 6. Insertar los datos en PostgreSQL ---
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if rows:
        insert_query = sql.SQL(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})")
        pg_cursor.executemany(insert_query, rows)

    # Confirmar después de cada tabla
    pg_conn.commit()

# --- 7. Cerrar conexiones ---
sqlite_conn.close()
pg_cursor.close()
pg_conn.close()

print("✅ Migración completada con éxito.")
