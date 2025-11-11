import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import streamlit_authenticator as stauth
from config import USER_CONFIG # Importamos la configuración de roles/usuarios

# --- CONEXIÓN A LA BASE DE DATOS ---
engine = create_engine('sqlite:///fantasy.db')

# --- FUNCIONES DE CACHÉ Y OBTENCIÓN DE DATOS ---
@st.cache_data(ttl=600)
def obtener_ligas():
    """Obtiene la lista de todas las ligas disponibles."""
    try:
        df = pd.read_sql("SELECT id, nombre FROM Ligas ORDER BY nombre", engine)
        return {row['nombre']: row['id'] for index, row in df.iterrows()}
    except:
        return {}
    
# Cuenta los participantes directamente desde la base de datos
@st.cache_data(ttl=600)
def contar_participantes_por_liga(liga_id):
    """Obtiene el número de participantes (jugadores) en una liga."""
    try:
        # Consulta SQL optimizada para contar jugadores distintos
        query = f"SELECT COUNT(DISTINCT jugador) FROM Puntos WHERE liga_id = {liga_id}"
        count = pd.read_sql(query, engine).iloc[0, 0]
        return int(count)
    except Exception as e:
        # Maneja el caso donde la liga_id no existe o la tabla está vacía
        # st.error(f"Error al contar participantes: {e}") # Puedes descomentar esto para debug
        return 0

@st.cache_data(ttl=600)
def obtener_jugadores(liga_id):
    """Obtiene la lista de jugadores de la liga activa."""
    try:
        # Se incluye el jugador que tenga 0 puntos en la primera jornada para que aparezca
        df = pd.read_sql(f"SELECT DISTINCT jugador FROM Puntos WHERE liga_id = {liga_id} ORDER BY jugador", engine)
        return df['jugador'].tolist()
    except:
        return []

@st.cache_data(ttl=600)
def obtener_max_jornada(liga_id):
    """Obtiene el número de la última jornada registrada para la liga activa."""
    try:
        with engine.connect() as connection:
            max_j = connection.execute(text(f"SELECT MAX(jornada) FROM Puntos WHERE liga_id = {liga_id}")).scalar()
            return int(max_j) if max_j else 0
    except:
        return 0

def guardar_puntos(liga_id, jugador, jornada, puntos):
    """Inserta o actualiza los puntos en la BD."""
    try:
        with engine.connect() as connection:
            connection.execute(
                text("""
                    INSERT INTO Puntos (liga_id, jugador, jornada, puntos) 
                    VALUES (:liga_id, :jugador, :jornada, :puntos)
                    ON CONFLICT(liga_id, jugador, jornada) DO UPDATE SET puntos = :puntos;
                """),
                {"liga_id": liga_id, "jugador": jugador, "jornada": jornada, "puntos": puntos}
            )
            connection.commit()
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"❌ Error al guardar en la BD: {e}")
        return False

# --- PÁGINAS DE LA APLICACIÓN ---

def gestionar_ligas(ligas_map):
    st.header("⚙️ Gestión de Ligas")
    
    tab1, tab2 = st.tabs(["➕ Crear Liga", "🗑️ Eliminar Liga"])

    with tab1:
        st.subheader("Crear una Nueva Liga")
        nombre_liga = st.text_input("Nombre de la Liga (ej: 'Liga Subliga Pago'):")
        temporada = st.text_input("Temporada (ej: '2025/2026'):")
        
        if st.button("Crear Liga"):
            if nombre_liga and nombre_liga not in ligas_map:
                try:
                    with engine.connect() as connection:
                        connection.execute(text(
                            "INSERT INTO Ligas (nombre, temporada) VALUES (:nombre, :temporada)"
                        ), {"nombre": nombre_liga, "temporada": temporada})
                        connection.commit()
                    st.cache_data.clear()
                    st.success(f"¡Liga '{nombre_liga}' creada con éxito!")
                except Exception as e:
                    st.error(f"Error al crear la liga: {e}")
            elif nombre_liga in ligas_map:
                 st.warning("Esta liga ya existe.")
            else:
                st.error("El nombre de la liga no puede estar vacío.")

    with tab2:
        st.subheader("Eliminar una Liga")
        liga_a_eliminar_nombre = st.selectbox("Selecciona liga a eliminar (¡Peligro!):", list(ligas_map.keys()))
        liga_a_eliminar_id = ligas_map.get(liga_a_eliminar_nombre)
        
        st.warning("Eliminar una liga borrará TODOS sus jugadores y puntos asociados.")
        if st.button("🔴 ELIMINAR LIGA PERMANENTEMENTE"):
            if liga_a_eliminar_id:
                with engine.connect() as connection:
                    # Borrar puntos primero (dependientes)
                    connection.execute(text("DELETE FROM Puntos WHERE liga_id = :id"), {"id": liga_a_eliminar_id})
                    # Borrar la liga
                    connection.execute(text("DELETE FROM Ligas WHERE id = :id"), {"id": liga_a_eliminar_id})
                    connection.commit()
                st.cache_data.clear()
                st.success(f"¡La liga '{liga_a_eliminar_nombre}' ha sido eliminada!")


def gestionar_jugadores(liga_id, nombre_liga):
    st.header(f"👤 Gestión de Participantes de la Liga: {nombre_liga}")
    jugadores_actuales = obtener_jugadores(liga_id)
    
    tab1, tab2, tab3 = st.tabs(["➕ Nuevo Jugador", "➖ Eliminar Jugador", "✏️ Renombrar Jugador"])

    with tab1:
        st.subheader("Crear un Nuevo Jugador")
        nuevo_nombre = st.text_input("Nombre del nuevo participante:", key="nuevo_jugador_input")
        
        if st.button("Crear Jugador", key="btn_crear_jugador"):
            if nuevo_nombre and nuevo_nombre not in jugadores_actuales:
                # Insertamos un punto ficticio (0) en la jornada 1 para que aparezca en la lista
                # Nota: Esto resuelve el problema de que el jugador aparezca en las listas, sin depender del ID inicial.
                guardar_puntos(liga_id, nuevo_nombre, 1, 0)
                st.success(f"¡{nuevo_nombre} añadido a la liga!")
            elif nuevo_nombre in jugadores_actuales:
                 st.warning(f"Este jugador ya existe en la liga: '{nombre_liga}'.")
            else:
                st.error("El nombre no puede estar vacío.")

    with tab2:
        st.subheader("Eliminar un Jugador")
        jugador_a_eliminar = st.selectbox("Selecciona participante a eliminar:", jugadores_actuales, key="jugador_eliminar_select")
        
        if st.button("🔴 ELIMINAR PERMANENTEMENTE", help="Borrará todos sus datos de esta liga."):
            with engine.connect() as connection:
                connection.execute(text(
                    "DELETE FROM Puntos WHERE jugador = :j AND liga_id = :id"
                ), {"j": jugador_a_eliminar, "id": liga_id})
                connection.commit()
            st.cache_data.clear()
            st.success(f"¡{jugador_a_eliminar} y todos sus puntos han sido eliminados de esta liga!")


    with tab3:
        st.subheader("Renombrar un Jugador")
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            jugador_antiguo = st.selectbox("Selecciona jugador a renombrar:", jugadores_actuales, key="jugador_antiguo_select")
        
        with col_r2:
            nuevo_nombre_jugador = st.text_input("Nuevo nombre:", key="nuevo_nombre_jugador_input")

        if st.button("✏️ Renombrar"):
            if nuevo_nombre_jugador and jugador_antiguo:
                if nuevo_nombre_jugador in jugadores_actuales:
                    st.error("Ya existe un jugador con ese nombre.")
                else:
                    # Actualiza la columna 'jugador' en la tabla Puntos
                    with engine.connect() as connection:
                        connection.execute(text(
                            "UPDATE Puntos SET jugador = :nuevo WHERE jugador = :antiguo AND liga_id = :id"
                        ), {"nuevo": nuevo_nombre_jugador, "antiguo": jugador_antiguo, "id": liga_id})
                        connection.commit()
                    st.cache_data.clear()
                    st.success(f"¡{jugador_antiguo} renombrado a {nuevo_nombre_jugador} con éxito!")
            else:
                st.error("Debes seleccionar un jugador y proporcionar un nuevo nombre.")


def interfaz_entrada_multiple(liga_id, jugadores):
    st.subheader("➕ Entrada/Modificación de Puntos")
    st.markdown("**Modo rápido:** Introduce la jornada y los puntos de todos los jugadores a la vez. El valor **0** es válido.")
    
    max_jornada = obtener_max_jornada(liga_id)
    
    with st.form("form_puntos_multiple", clear_on_submit=True):
        
        col1, col2 = st.columns([1, 2])
        with col1:
            jornada_actual = st.number_input(
                "Jornada a introducir/modificar:", 
                min_value=1, step=1, 
                value=max_jornada + 1 if max_jornada > 0 else 1
            )
        with col2:
            st.info(f"Última jornada registrada: **J-{max_jornada}**")

        nuevos_puntos = {}
        st.subheader(f"Puntos de la Jornada {int(jornada_actual)}")
        
        puntos_actuales = {}
        if jornada_actual:
             # Obtener los puntos actuales de la jornada y liga para precargar el formulario (para modificación)
             df_actual = pd.read_sql(f"SELECT jugador, puntos FROM Puntos WHERE liga_id = {liga_id} AND jornada = {int(jornada_actual)}", engine)
             puntos_actuales = df_actual.set_index('jugador')['puntos'].to_dict()
        
        cols = st.columns(3)
        for i, jugador in enumerate(jugadores):
            col = cols[i % 3]
            default_value = puntos_actuales.get(jugador, 0)
            
            # Puntos es INTEGER
            nuevos_puntos[jugador] = col.number_input(
                f"{jugador}:", 
                min_value=0, step=1, 
                value=int(default_value), # Aseguramos que sea entero
                key=f"puntos_{jugador}_{jornada_actual}"
            )
            
        submitted = st.form_submit_button("💾 GUARDAR/MODIFICAR PUNTOS DE LA JORNADA")
        
        if submitted:
            exito = True
            for jugador, puntos in nuevos_puntos.items():
                if not guardar_puntos(liga_id, jugador, int(jornada_actual), int(puntos)):
                    exito = False
                    break
            
            if exito:
                st.success(f"✅ ¡Puntos de la Jornada {int(jornada_actual)} guardados/modificados con éxito!")


def interfaz_rendimiento_jugador(liga_id, jugadores):
    st.header("🧠 Rendimiento Individual y Estadísticas")
    
    # 1. CONSULTA DE FRECUENCIA DE PUNTOS CON DETALLE
    st.subheader("1. Frecuencia de Puntos y Jornadas Detalladas")
    st.markdown("Busca cuántas veces un jugador ha cumplido un criterio de puntuación y qué jornadas fueron.")
    
    colA, colB, colC = st.columns([2, 1, 1])
    
    with colA:
        jugador_sel = st.selectbox("Selecciona Participante:", jugadores, key="jug_rend")
        
    with colB:
        operador = st.selectbox("Operador:", ["> Mayor que", "< Menor que", "= Igual a"], key="op_rend")
        op_simbolo = operador.split(' ')[0] # Extraer solo el >, < o =
        
    with colC:
        puntos_crit = st.number_input("Puntos de Criterio (X):", min_value=0, step=1, value=50, key="pts_rend")
        
    if jugador_sel and st.button("Buscar Rendimiento", key="btn_buscar_rendimiento"):
        
        # 1a. Consulta para OBTENER EL DETALLE de las jornadas
        consulta_detalle = f"""
            SELECT 
                jugador, 
                jornada, 
                puntos 
            FROM Puntos 
            WHERE liga_id = {liga_id}
            AND jugador = '{jugador_sel}'
            AND puntos {op_simbolo} {int(puntos_crit)}
            ORDER BY jornada ASC;
        """
        df_detalle = pd.read_sql(consulta_detalle, engine)
        
        # 1b. Obtener el total de jornadas (igual al número de filas en el detalle)
        resultado = len(df_detalle)
        
        # Mostrar el resultado resumido
        st.success(f"**{jugador_sel}** ha conseguido **{resultado}** jornadas con **{operador} {int(puntos_crit)} puntos**.")

        # Mostrar la tabla con el detalle (si hay resultados)
        if not df_detalle.empty:
            st.markdown("##### Jornadas que cumplen el criterio:")
            st.dataframe(
                df_detalle.rename(columns={'jornada': 'Jornada', 'puntos': 'Puntos'}), 
                use_container_width=True, 
                hide_index=True,
                column_order=("Jornada", "Puntos") # Quitamos la columna 'jugador' que es obvia
            )
        else:
            st.info("No se encontraron jornadas que cumplan este criterio.")


    # 2. CONSULTA INTERESANTE: JORNADA DE ORO
    st.markdown("---")
    st.subheader("2. Jornada de Oro (Récord de la Liga)")
    
    df_record = pd.read_sql(f"""
        SELECT 
            jugador, 
            jornada, 
            puntos 
        FROM Puntos 
        WHERE liga_id = {liga_id} 
        ORDER BY puntos DESC 
        LIMIT 5;
    """, engine)
    
    if not df_record.empty:
        mejor_jugador = df_record.iloc[0]['jugador']
        mejor_puntos = df_record.iloc[0]['puntos']
        mejor_jornada = df_record.iloc[0]['jornada']
        
        st.metric(
            label="Mejor Puntuación Histórica", 
            value=f"{int(mejor_puntos)} puntos", 
            delta=f"Logrado por {mejor_jugador} en la J-{int(mejor_jornada)}"
        )
        
        st.info("Top 5 Puntuaciones Individuales:")
        st.dataframe(df_record, use_container_width=True, hide_index=True)


def interfaz_pivote_completo(liga_id, nombre_liga):
    st.header("📋 Tabla Detallada de Puntos")
    st.markdown(f"Visualización de todos los jugadores y sus puntos por jornada en la liga: {nombre_liga}.")
    
    # 1. Traer todos los puntos de la liga
    df_long = pd.read_sql(f"""
        SELECT 
            jugador, 
            jornada, 
            puntos 
        FROM Puntos 
        WHERE liga_id = {liga_id}
        ORDER BY jornada ASC
    """, engine)
    
    if df_long.empty:
        st.warning("No hay datos de puntos en esta liga.")
        return

    # 2. Pivotar el DataFrame (de formato largo a formato ancho)
    # Índice: Jugador
    # Columnas: Jornada
    # Valores: Puntos
    df_pivot = df_long.pivot(index='jugador', columns='jornada', values='puntos').fillna(0).astype(int)

    # 3. Calcular la columna de Totales
    df_pivot['TOTAL'] = df_pivot.sum(axis=1)
    
    # 4. Convertir el índice (Jugadores) en una columna regular. 
    #    Esto fuerza a Streamlit a renderizar los nombres como datos y no como índice, 
    #    solucionando el problema de color.
    df_final = df_pivot.reset_index()

    # 5. Ordenar por la columna TOTAL (clasificación)
    df_final = df_final.sort_values(by='TOTAL', ascending=False)
    
    # 6. Renombrar las columnas de jornada
    # Nota: Aplicamos el renombramiento a df_final, que ahora incluye 'jugador'
    df_final.columns = [f"J{col}" if isinstance(col, (int, float)) and col != 'TOTAL' else col for col in df_final.columns]
    
    # 7. Renombrar la columna 'jugador' para mejor visualización
    df_final = df_final.rename(columns={'jugador': 'Jugador'})
    
    # Mostrar el DataFrame final (sin el índice por defecto)
    st.dataframe(df_final, use_container_width=True, hide_index=True)


def interfaz_consultas(liga_id):
    # Muestra la clasificación general y por rango
    st.header("📊 Clasificación y Estadísticas")
    
    # 1. CLASIFICACIÓN GENERAL (TOTAL)
    st.subheader("1. Clasificación General")
    df_puntos_total = pd.read_sql(f"""
        SELECT 
            jugador, 
            SUM(puntos) as "Puntos Totales", 
            COUNT(DISTINCT jornada) as "Jornadas Jugadas",
            ROUND(CAST(SUM(puntos) AS REAL) / COUNT(DISTINCT jornada), 2) as "Media/Jornada"
        FROM Puntos 
        WHERE liga_id = {liga_id}
        GROUP BY jugador 
        ORDER BY "Puntos Totales" DESC
    """, engine)
    st.dataframe(df_puntos_total, use_container_width=True, hide_index=True) 
    st.bar_chart(df_puntos_total.set_index('jugador')['Puntos Totales'])
    
    # 2. CONSULTA PERSONALIZADA POR RANGO DE JORNADAS
    st.markdown("---")
    st.subheader("2. Clasificación por Rango de Jornadas")
    
    max_jornada = obtener_max_jornada(liga_id)
    
    if max_jornada > 0:
        
        colA, colB = st.columns(2)
        with colA:
            j_inicio = st.number_input("Jornada Inicial (incluida):", min_value=1, max_value=max_jornada, value=1, key="j_inicio_rango")
        with colB:
            j_fin = st.number_input("Jornada Final (incluida):", min_value=1, max_value=max_jornada, value=max_jornada, key="j_fin_rango")

        if j_inicio <= j_fin:
            # Consulta SQL dinámica
            df_rango = pd.read_sql(f"""
                SELECT 
                    jugador, 
                    SUM(puntos) as "Puntos en el Rango",
                    COUNT(DISTINCT jornada) as "Jornadas Contadas"
                FROM Puntos 
                WHERE liga_id = {liga_id} AND jornada BETWEEN {int(j_inicio)} AND {int(j_fin)}
                GROUP BY jugador 
                ORDER BY "Puntos en el Rango" DESC
            """, engine)
            
            st.dataframe(df_rango, use_container_width=True, hide_index=True)
            st.bar_chart(df_rango.set_index('jugador')['Puntos en el Rango'])
        else:
            st.warning("La Jornada Inicial debe ser menor o igual que la Jornada Final.")
    else:
        st.info("No hay datos de jornadas para mostrar rangos.")

    # 3. MEDIA DE PUNTOS DE LA LIGA POR JORNADA
    st.markdown("---")
    st.subheader("3. Evolución de la Media de Puntos de la Liga")
    
    df_media = pd.read_sql(f"""
        SELECT 
            jornada, 
            ROUND(AVG(puntos), 2) as "Media de la Jornada"
        FROM Puntos 
        WHERE liga_id = {liga_id}
        GROUP BY jornada 
        ORDER BY jornada ASC
    """, engine)
    
    if not df_media.empty:
        st.dataframe(df_media, use_container_width=True, hide_index=True)
        st.line_chart(df_media.set_index('jornada')['Media de la Jornada'])
    else:
        st.info("No hay suficientes datos para calcular la media por jornada.")


# --- PÁGINA PRINCIPAL ---
def interfaz_home(ligas_map):
    # Asumimos que el user_role está disponible en st.session_state
    user_role = st.session_state.get('user_role', 'User') 

    st.markdown("## TUS LIGAS <span style='color:#FF4B4B;'>FANTASY</span>", unsafe_allow_html=True)
    
    if not ligas_map:
        st.warning("Actualmente no tienes ligas registradas. Ve a la sección 'Gestión de Ligas' en el menú lateral para crear la primera.")
        return None

    st.info("Selecciona una liga para ver sus opciones en el menú de navegación.")
    
    # Construir la lista de ligas con el conteo de participantes
    
    datos_ligas = []
    for nombre, id_liga in ligas_map.items():
        # Llamamos a la función optimizada para obtener el conteo
        num_participantes = contar_participantes_por_liga(id_liga)
        
        # Lógica Condicional: Mostrar el ID solo si el rol es Admin
        id_display = id_liga if user_role == 'Admin' else 'Oculto'
        
        datos_ligas.append({
            'Nombre': nombre,
            'ID': id_display, # Aquí usamos el valor condicional
            'Participantes': num_participantes
        })
    
    # Crea el DataFrame final
    df_ligas = pd.DataFrame(datos_ligas)

    # Mostrar el resumen en un formato de tabla limpio

    # Renombrar columnas para la presentación final
    df_presentacion = df_ligas.rename(columns={
        'Nombre': 'Nombre de la Liga',
        'Participantes': '👥 Participantes'
    })
    
    # Si no es Admin, ocultamos completamente la columna ID del DataFrame
    if user_role != 'Admin':
        df_presentacion = df_presentacion.drop(columns=['ID'])
    
    st.dataframe(
        df_presentacion, 
        use_container_width=True, 
        hide_index=True,
        # Ordenar columnas (quitamos 'ID' si el usuario no es Admin, Streamlit lo maneja)
        column_order=['Nombre de la Liga', '👥 Participantes', 'ID'] if user_role == 'Admin' else ['Nombre de la Liga', '👥 Participantes']
    )
    
    # El selector de liga se mantiene en el sidebar

# --- NUEVAS FUNCIONES DE GESTIÓN DE PUNTOS ---
def guardar_punto_individual(liga_id, jugador, jornada, puntos):
    """Actualiza los puntos de un jugador/jornada. Si el registro no existe, lo crea."""
    with engine.connect() as connection:
        # 1. Intentar actualizar el registro existente
        # Esto funciona para correcciones de puntos ya existentes
        update_result = connection.execute(text(
            "UPDATE Puntos SET puntos = :puntos WHERE liga_id = :id AND jugador = :jugador AND jornada = :jornada"
        ), {"puntos": puntos, "id": liga_id, "jugador": jugador, "jornada": jornada})
        
        # 2. Si no se actualizó ninguna fila (registro no existía), insertamos uno nuevo
        # Esto funciona para jugadores olvidados en la entrada original
        if update_result.rowcount == 0:
            connection.execute(text(
                "INSERT INTO Puntos (liga_id, jugador, jornada, puntos) VALUES (:id, :jugador, :jornada, :puntos)"
            ), {"id": liga_id, "jugador": jugador, "jornada": jornada, "puntos": puntos})
            
        connection.commit()
    st.cache_data.clear()


def interfaz_entrada_individual(liga_id, jugadores):
    """Interfaz para añadir/modificar puntos de un único jugador en una jornada."""
    st.subheader("✏️ Modificar Puntos de un Jugador Específico")
    st.markdown("Utiliza esta opción para corregir puntos o añadir jugadores que se te olvidaron, sin afectar al resto.")

    max_jornada = obtener_max_jornada(liga_id)
    # Sugerir la siguiente jornada
    jornada_default = max(1, max_jornada + 1)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        jugador_sel = st.selectbox("Participante:", jugadores, key="jug_indiv_sel")
    with col2:
        jornada_sel = st.number_input("Jornada:", min_value=1, step=1, value=jornada_default, key="jornada_indiv_sel")
    with col3:
        current_points = 0
        # Intentar obtener puntos actuales para precargar el campo (si existen)
        if jornada_sel > 0 and jugador_sel:
            with engine.connect() as connection:
                current_points = connection.execute(text(
                    "SELECT puntos FROM Puntos WHERE liga_id = :id AND jugador = :jugador AND jornada = :jornada"
                ), {"id": liga_id, "jugador": jugador_sel, "jornada": jornada_sel}).scalar()
            # Si no hay puntos, usamos 0
            current_points = current_points if current_points is not None else 0

        puntos_sel = st.number_input("Puntos:", min_value=0, step=1, value=current_points, key="puntos_indiv_sel")

    if st.button("Guardar/Actualizar Punto Individual", key="btn_save_indiv"):
        if jugador_sel and jornada_sel >= 1 and puntos_sel >= 0:
            guardar_punto_individual(liga_id, jugador_sel, jornada_sel, puntos_sel)
            st.success(f"✅ Puntos de {jugador_sel} actualizados a {int(puntos_sel)} en Jornada {int(jornada_sel)}.")
            
        else:
            st.error("Por favor, verifica los datos de la jornada y puntos.")


def interfaz_eliminar_jornada(liga_id):
    """Interfaz para eliminar todos los puntos de una jornada."""
    st.subheader("🗑️ Eliminar Puntos de una Jornada Completa")
    st.markdown("Esta acción **eliminará permanentemente** todos los puntos de la jornada seleccionada para todos los participantes.")
    
    max_jornada = obtener_max_jornada(liga_id)

    if max_jornada == 0:
        st.info("Aún no hay puntos registrados en esta liga.")
        return

    # Obtener todas las jornadas registradas para el selectbox
    with engine.connect() as connection:
        jornadas_registradas = connection.execute(text(
            f"SELECT DISTINCT jornada FROM Puntos WHERE liga_id = {liga_id} ORDER BY jornada DESC"
        )).scalars().all()
    
    jornada_a_eliminar = st.selectbox(
        "Selecciona la jornada a eliminar:", 
        jornadas_registradas,
        key="jornada_elim_select"
    )

    if st.button(f"🔴 CONFIRMAR ELIMINACIÓN DE JORNADA {jornada_a_eliminar}"):
        with engine.connect() as connection:
            connection.execute(text(
                "DELETE FROM Puntos WHERE liga_id = :id AND jornada = :jornada"
            ), {"id": liga_id, "jornada": jornada_a_eliminar})
            connection.commit()
        st.cache_data.clear()
        st.success(f"✅ ¡Jornada {jornada_a_eliminar} eliminada completamente!")
        st.rerun() # Recarga la página para actualizar las listas de jornadas


def interfaz_gestion_puntos(liga_id, jugadores):
    """Wrapper que contiene todas las opciones de gestión de puntos."""
    st.header("📝 Gestión de Puntos de Jornada")
    
    # Usamos tabs para organizar las tres funcionalidades
    tab1, tab2, tab3 = st.tabs(["➕ Entrada Múltiple", "✏️ Entrada Individual", "🗑️ Eliminar Jornada"])

    with tab1:
        # Llamamos a tu función original para entrada masiva
        interfaz_entrada_multiple(liga_id, jugadores) 
    with tab2:
        # Nueva entrada individual
        interfaz_entrada_individual(liga_id, jugadores) 
    with tab3:
        # Nueva eliminación por jornada
        interfaz_eliminar_jornada(liga_id)


# --- ESTRUCTURA PRINCIPAL DE LA APP ---
def main():
    st.set_page_config(layout="wide", page_title="Gestor Fantasy", initial_sidebar_state="expanded")
    
    # Inicializar el estado de la sesión si es la primera carga
    if 'authentication_status' not in st.session_state:
        st.session_state['authentication_status'] = None
        st.session_state['username'] = None
        st.session_state['name'] = None
        st.session_state['user_role'] = None

    # -----------------------------------------------------
    # ENCABEZADO PERSONALIZADO
    # -----------------------------------------------------
    st.markdown("""
        <div style='text-align: center;'>
            <h1 style='margin: 0;'>GESTOR DE LIGAS <span style='color:#FF4B4B;'>FANTASY</span></h1>
        </div>
    """, unsafe_allow_html=True)
    
    # -----------------------------------------------------
    # AUTENTICACIÓN Y ROLES
    # -----------------------------------------------------
    authenticator = stauth.Authenticate(
        USER_CONFIG['credentials'],
        USER_CONFIG['cookie']['name'],
        USER_CONFIG['cookie']['key'],
        USER_CONFIG['cookie']['expiry_days']
    )

    # -----------------------------------------------------
    # LÓGICA DE LOGIN O CONTENIDO
    # -----------------------------------------------------
    
    if st.session_state['authentication_status']:
        # **********************************************
        # 1. USUARIO AUTENTICADO: RENDERIZAR LA APP COMPLETA
        # **********************************************
        
        # Obtener datos de sesión
        name = st.session_state['name']
        user_role = st.session_state['user_role']
        username = st.session_state['username'] # Añadido para buscar ligas permitidas

        # 1. Configurar el sidebar y logout
        authenticator.logout('Logout', 'sidebar')
        st.sidebar.markdown(f"<p style='font-size: small; margin-top: 0.5rem;'>Rol: <strong>{user_role}</strong></p>", unsafe_allow_html=True)

        # 2. Cargar todas las ligas
        todas_las_ligas_map = obtener_ligas()
        
        # OBTENER LIGAS PERMITIDAS SEGÚN EL ROL Y ASIGNACIÓN
        ligas_permitidas = todas_las_ligas_map.copy()

        # Si el usuario NO es Admin, filtar por las ligas asignadas en config.py
        if user_role != 'Admin':
            # Obtener la lista de ligas permitidas para el usuario
            allowed_names = USER_CONFIG['credentials']['usernames'][username]['allowed_leagues']
            
            # Filtrar el mapa de ligas
            ligas_permitidas = {
                nombre: id_liga
                for nombre, id_liga in todas_las_ligas_map.items()
                if nombre in allowed_names
            }

        ligas_map = ligas_permitidas
        liga_id_activa = None
        jugadores = []

        # 3. Selector de Liga Activa en el Sidebar
        nombre_liga_activa = ""
        if ligas_map:
            # Si solo hay una liga asignada, la seleccionamos automáticamente.
            # Si hay varias, mostramos el selectbox.
            
            nombre_liga_activa = st.sidebar.selectbox("🎯 Liga Activa:", list(ligas_map.keys()), key="liga_select")
            liga_id_activa = ligas_map[nombre_liga_activa]
            if user_role == 'Admin':
                st.sidebar.markdown(f"**{nombre_liga_activa}** (ID: {liga_id_activa})")
            else:
                # Mostrar solo el nombre si no es Admin
                st.sidebar.markdown(f"**{nombre_liga_activa}**")
            jugadores = obtener_jugadores(liga_id_activa)
        else:
            st.sidebar.warning("No hay ligas. Crea una en 'Gestión de Ligas'.")

        # 4. Menú de Navegación (Depende del rol)
        menu_base = ["Home", "Clasificación", "Rendimiento Individual", "Tabla Completa"]
        
        # Añadir opciones sensibles solo si es Admin
        if user_role == 'Admin':
            menu_admin = ["Gestión de Puntos", "Gestión de Participantes", "Gestión de Ligas"]
            menu = menu_base + menu_admin
        else:
            menu = menu_base
            
        choice = st.sidebar.selectbox("Menú de Navegación:", menu)

        # 5. Renderizado de Páginas (Depende del rol y la selección)
        
        if choice == "Home":
            st.markdown(f"## 👋 Bienvenido, {name}")
            st.markdown(f"**Tu Rol:** `{user_role}`")
            
            if ligas_map:
                interfaz_home(ligas_map)
            else:
                 st.info("¡Bienvenido! Como no hay ligas creadas, el administrador debe ir a 'Gestión de Ligas' para empezar.")
            
        elif choice == "Gestión de Ligas" and user_role == 'Admin':
            gestionar_ligas(ligas_map)
            
        elif liga_id_activa is None and choice != "Gestión de Ligas":
            st.warning("Selecciona una liga en el menú lateral para acceder a estas opciones.")
                 
        # Opciones protegidas para ADMIN
        elif user_role != 'Admin' and choice in ["Gestión de Puntos", "Gestión de Participantes", "Gestión de Ligas"]:
            st.error("🚨 Acceso Denegado. Solo los administradores pueden acceder a la gestión de datos.")
            
        # Opciones disponibles para todos (Admin y User)
        elif choice == "Clasificación":
            interfaz_consultas(liga_id_activa)
            
        elif choice == "Rendimiento Individual":
            if jugadores:
                interfaz_rendimiento_jugador(liga_id_activa, jugadores)
            else:
                st.warning("Añade jugadores primero.")
                
        elif choice == "Tabla Completa":
            if liga_id_activa:
                interfaz_pivote_completo(liga_id_activa, nombre_liga_activa)
            else:
                st.warning("Selecciona una liga.")
                
        # Opciones de Admin
        elif choice == "Gestión de Puntos":
            if jugadores:
                interfaz_gestion_puntos(liga_id_activa, jugadores) 
            else:
                st.warning("Añade jugadores primero en la sección 'Gestión de Participantes'.")
                
        elif choice == "Gestión de Participantes":
            gestionar_jugadores(liga_id_activa, nombre_liga_activa)
    
    else:
        # **********************************************
        # 2. USUARIO NO AUTENTICADO: MOSTRAR FORMULARIO DE LOGIN
        # **********************************************
        
        # Se muestra solo el login, en el main, sin usar el sidebar
        col1, col2, col3 = st.columns([1,2,1])
        
        with col2:
            st.header("🔐 Acceso Restringido")
            
            with st.form(key='login_form', clear_on_submit=False):
                st.subheader("Ingresa tus credenciales")
                
                login_username = st.text_input('Usuario', key='login_user')
                login_password = st.text_input('Contraseña', type='password', key='login_pass')
                
                if st.form_submit_button('Entrar'):
                    # Buscar credenciales en la configuración
                    if login_username in USER_CONFIG['credentials']['usernames']:
                        
                        user_info = USER_CONFIG['credentials']['usernames'][login_username]
                        hashed_password = user_info['password']
                        
                        # Validar la contraseña usando el Hasher (requiere que el Hasher esté correctamente hasheado)
                        if stauth.Hasher().check_pw(login_password, hashed_password):
                            st.session_state['authentication_status'] = True
                            st.session_state['username'] = login_username
                            st.session_state['name'] = user_info['name']
                            st.session_state['user_role'] = user_info['role']
                            
                            st.success(f"¡Bienvenido, {user_info['name']}!")
                            st.rerun() # Recarga para mostrar el contenido
                            
                        else:
                            st.error('Usuario o Contraseña incorrecta.')
                            
                    else:
                        st.error('Usuario o Contraseña incorrecta.')

if __name__ == '__main__':
    main()