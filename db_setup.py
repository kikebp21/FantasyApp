from sqlalchemy import create_engine, text

# 1. Conexión a la BD (crea el archivo fantasy.db si no existe)
engine = create_engine('sqlite:///fantasy.db')

def setup_db():
    """Crea las tablas Ligas y Puntos si no existen."""
    with engine.connect() as connection:
        
        # 1. Tabla para gestionar múltiples Ligas
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS Ligas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                temporada TEXT
            );
        """))
        
        # 2. Tabla de Puntos (ahora incluye liga_id y puntos es INTEGER)
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS Puntos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                liga_id INTEGER NOT NULL,
                jugador TEXT NOT NULL,
                jornada INTEGER NOT NULL,
                puntos INTEGER NOT NULL,
                UNIQUE(liga_id, jugador, jornada),
                FOREIGN KEY (liga_id) REFERENCES Ligas(id)
            );
        """))
        connection.commit()
    print("Base de datos 'fantasy.db', y tablas 'Ligas' y 'Puntos' configuradas.")

if __name__ == '__main__':
    setup_db()
    print("Ejecuta 'python db_setup.py' en la terminal para crear la BD.")