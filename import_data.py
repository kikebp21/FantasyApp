import pandas as pd
from sqlalchemy import create_engine, text
from io import StringIO

# --- CONFIGURACIÓN DE LA IMPORTACIÓN ---
NOMBRE_LIGA = "Liga AKC 2025-26" 
NOMBRE_TEMPORADA = "2025/2026"

# Datos históricos de las primeras jornadas
# (Se han extraído y limpiado de tu archivo original)
DATOS_CSV = """Nombre,Jornada 1,Jornada 2,Jornada 3,Jornada 4,Jornada 5,Jornada 6,Jornada 7,Jornada 8,Jornada 9,Jornada 10,Jornada 11,Jornada 12
El Mago Ramón,94,66,94,76,75,81,58,82,74,77,68,56
Anil Murthy Asado,80,74,45,48,74,69,75,50,58,75,101,75
Guillermo Pellegrini,79,66,67,57,106,59,75,100,52,43,58,82
Matías Almendra,77,63,61,54,86,50,60,47,45,0,74,59
Batistuta9,73,71,67,38,72,96,53,84,88,59,71,80
Minilopera,63,34,40,29,51,27,63,54,42,32,42,42
"Abbondanzieri, Pato",59,110,60,82,37,52,68,34,72,69,73,96
Joota Jordi,57,50,58,31,80,73,75,34,79,71,62,31
La Peina Fazio,47,34,59,47,37,30,86,44,101,72,71,62
P4nchit0,32,0,35,0,0,0,37,17,17,11,18,61
"""

# Conexión a la BD
engine = create_engine('sqlite:///fantasy.db')

def obtener_o_crear_liga(nombre_liga, temporada):
    """Inserta la liga si no existe y devuelve su ID."""
    with engine.connect() as connection:
        liga_id = connection.execute(text(
            "SELECT id FROM Ligas WHERE nombre = :nombre"
        ), {"nombre": nombre_liga}).scalar()
        
        if liga_id is None:
            connection.execute(text(
                "INSERT INTO Ligas (nombre, temporada) VALUES (:nombre, :temporada)"
            ), {"nombre": nombre_liga, "temporada": temporada})
            connection.commit()
            liga_id = connection.execute(text(
                "SELECT id FROM Ligas WHERE nombre = :nombre"
            ), {"nombre": nombre_liga}).scalar()
            print(f"✅ Liga '{nombre_liga}' creada con ID: {liga_id}")
            
        return liga_id

def limpiar_datos_liga(liga_id, nombre_liga):
    """Elimina todos los puntos de una liga antes de la importación masiva."""
    with engine.connect() as connection:
        count = connection.execute(text(f"SELECT COUNT(id) FROM Puntos WHERE liga_id = {liga_id}")).scalar()
        
        if count > 0:
            print(f"🚨 Advertencia: Se encontraron {count} puntos existentes para la liga '{nombre_liga}'.")
            connection.execute(text(f"DELETE FROM Puntos WHERE liga_id = {liga_id}"))
            connection.commit()
            print(f"🗑️ Datos de puntos anteriores eliminados correctamente. Listo para re-importar.")
        
def importar_tabla_directa(csv_data, liga_id):
    """Procesa la cadena de texto CSV y la inserta en la tabla Puntos."""
    print("Iniciando la lectura de datos internos...")
    
    # Usamos StringIO para tratar la cadena de texto como un archivo CSV
    df = pd.read_csv(StringIO(csv_data), header=0, sep=',') 

    # --- Tubería de Limpieza y Transformación (MELT) ---
    df = df.fillna(0) 
    
    df_long = pd.melt(
        df, 
        id_vars=['Nombre'], 
        var_name='Jornada', 
        value_name='Puntos'
    )
    
    # Limpieza y conversión de tipos
    df_long['Jornada'] = df_long['Jornada'].astype(str).str.replace('Jornada ', '', regex=False).str.strip()
    df_long['Jornada'] = pd.to_numeric(df_long['Jornada'], errors='coerce').astype('Int64')
    df_long['Puntos'] = pd.to_numeric(df_long['Puntos'], errors='coerce').astype('Int64')
    
    df_long = df_long.dropna(subset=['Jornada', 'Puntos'])
    df_long = df_long[df_long['Jornada'] > 0]
    
    print(f"Se han preparado {len(df_long)} registros válidos para insertar.")
    
    # Preparar para la BD
    df_long = df_long.rename(columns={'Nombre': 'jugador', 'Jornada': 'jornada', 'Puntos': 'puntos'})
    df_long['liga_id'] = liga_id

    # Inserción en SQLite
    try:
        df_long.to_sql('Puntos', engine, if_exists='append', index=False)
        print(f"✅ ¡Éxito! {len(df_long)} puntos insertados en la liga ID {liga_id}.")
    except Exception as e:
        print(f"❌ ERROR al insertar en la BD: {e}")
        
if __name__ == '__main__':
    # 1. Obtener la liga ID (y crearla si no existe)
    liga_id = obtener_o_crear_liga(NOMBRE_LIGA, NOMBRE_TEMPORADA)
    
    # 2. Limpiar datos existentes antes de importar
    if liga_id:
        limpiar_datos_liga(liga_id, NOMBRE_LIGA)
        
    # 3. Importar los datos
    if liga_id:
        importar_tabla_directa(DATOS_CSV, liga_id)