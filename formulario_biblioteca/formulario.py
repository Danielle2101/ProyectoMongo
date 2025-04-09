from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import datetime
import json

app = Flask(__name__)
CORS(app)

# Configuración de la base de datos
def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='biblioteca'
        )
        return connection
    except Error as e:
        print(f"Error conectando a MySQL: {e}")
        return None

# ------------------- FUNCIONES AUXILIARES -------------------

def convert_ids(document):
    """Convierte los IDs numéricos a strings para mantener compatibilidad con el frontend"""
    if document:
        document['_id'] = str(document['id']) if 'id' in document else str(document.get('_id', ''))
        for key in ['id_usuario', 'id_ejemplar', 'id_libro', 'id_prestamo']:
            if key in document:
                document[key] = str(document[key])
    return document

def registrar_historial(accion, id_ejemplar=None, id_usuario=None, id_prestamo=None, id_libro=None, datos_adicionales=None):
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor()
            query = """
            INSERT INTO historial 
            (accion, id_ejemplar, id_usuario, id_prestamo, id_libro, fecha, datos_adicionales)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
            """
            cursor.execute(query, (
                accion,
                int(id_ejemplar) if id_ejemplar else None,
                int(id_usuario) if id_usuario else None,
                int(id_prestamo) if id_prestamo else None,
                int(id_libro) if id_libro else None,
                json.dumps(datos_adicionales) if datos_adicionales else None
            ))
            connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Error registrando historial: {e}")
            return None
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return None

def format_date(date_str):
    """Formatea la fecha para mostrarla de manera consistente"""
    if not date_str:
        return None
    try:
        if isinstance(date_str, datetime.datetime):
            return date_str.strftime("%Y-%m-%d")
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except:
        return date_str

# ------------------- ENDPOINTS POST -------------------

@app.route('/add_libro', methods=['POST'])
def add_libro():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        data = request.form
        cursor = connection.cursor()
        query = """
        INSERT INTO libros (titulo, autor, paginas, editorial)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['titulo'],
            data['autor'],
            int(data['paginas']),
            data['editorial']
        ))
        connection.commit()
        
        libro_id = cursor.lastrowid
        return jsonify({"message": "Libro agregado correctamente", "id": str(libro_id)}), 201
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/add_ejemplar', methods=['POST'])
def add_ejemplar():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        data = request.form
        numero_ejemplar = data.get('numero_total') or data.get('numero_ejemplar')
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, titulo FROM libros WHERE id = %s", (int(data['id_libro']),))
        libro = cursor.fetchone()
        
        if not libro:
            return jsonify({"error": "Libro no encontrado"}), 404
            
        query = """
        INSERT INTO ejemplares 
        (numero_total, ejemplares_prestados, estado, id_libro, titulo_libro)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            int(numero_ejemplar),
            0,
            data['estado'],
            int(data['id_libro']),
            libro['titulo']
        ))
        connection.commit()
        
        ejemplar_id = cursor.lastrowid
        return jsonify({"message": "Ejemplar agregado correctamente", "id": str(ejemplar_id)}), 201
        
    except Error as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": "ID de libro inválido"}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/add_usuario', methods=['POST'])
def add_usuario():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        data = request.form
        cursor = connection.cursor()
        query = """
        INSERT INTO usuarios 
        (nombre, correo, telefono, ejemplares_prestados, tiene_reserva)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['nombre'],
            data['correo'],
            data['telefono'],
            0,
            False
        ))
        connection.commit()
        
        usuario_id = cursor.lastrowid
        return jsonify({"message": "Usuario agregado correctamente", "id": str(usuario_id)}), 201
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/add_prestamo', methods=['POST'])
def add_prestamo():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        data = request.form
        id_ejemplar = int(data['id_ejemplar'])
        id_usuario = int(data['id_usuario'])
        
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
        SELECT e.*, l.titulo as titulo_libro 
        FROM ejemplares e
        JOIN libros l ON e.id_libro = l.id
        WHERE e.id = %s
        """, (id_ejemplar,))
        ejemplar = cursor.fetchone()
        
        if not ejemplar:
            connection.rollback()
            return jsonify({"error": "Ejemplar no encontrado"}), 404
            
        disponibles = ejemplar['numero_total'] - ejemplar['ejemplares_prestados']
        if disponibles <= 0:
            connection.rollback()
            return jsonify({
                "error": "No hay ejemplares disponibles",
                "detalle": {
                    "total_ejemplares": ejemplar['numero_total'],
                    "prestados": ejemplar['ejemplares_prestados']
                }
            }), 400

        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id_usuario,))
        usuario = cursor.fetchone()
        if not usuario:
            connection.rollback()
            return jsonify({"error": "Usuario no encontrado"}), 404

        cursor.execute("""
        UPDATE ejemplares 
        SET ejemplares_prestados = ejemplares_prestados + 1, 
            estado = 'borrowed' 
        WHERE id = %s
        """, (id_ejemplar,))

        cursor.execute("""
        UPDATE usuarios 
        SET ejemplares_prestados = ejemplares_prestados + 1 
        WHERE id = %s
        """, (id_usuario,))

        query = """
        INSERT INTO prestamos 
        (id_ejemplar, id_usuario, fecha_recibido, fecha_debe_entregar, estado)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            id_ejemplar,
            id_usuario,
            format_date(data['fecha_recibido']),
            format_date(data['fecha_debe_entregar']),
            'borrowed'
        ))
        prestamo_id = cursor.lastrowid
        connection.commit()

        registrar_historial(
            accion="prestamo",
            id_ejemplar=id_ejemplar,
            id_usuario=id_usuario,
            id_prestamo=prestamo_id,
            id_libro=ejemplar['id_libro'],
            datos_adicionales={
                "fecha_recibido": format_date(data['fecha_recibido']),
                "fecha_devolucion_prevista": format_date(data['fecha_debe_entregar']),
                "titulo_libro": ejemplar['titulo_libro'],
                "nombre_usuario": usuario['nombre']
            }
        )

        return jsonify({
            "message": "Préstamo registrado correctamente",
            "id": str(prestamo_id),
            "detalle": {
                "ejemplar": str(id_ejemplar),
                "ejemplares_disponibles": disponibles - 1
            }
        }), 201

    except ValueError as e:
        connection.rollback()
        return jsonify({"error": "ID inválido"}), 400
    except Error as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/devolver_prestamo/<id_prestamo>', methods=['POST'])
def devolver_prestamo(id_prestamo):
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        data = request.form
        estado_libro = data.get('estado_libro', 'bueno')
        
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
        SELECT p.*, e.id_libro, e.titulo_libro, u.nombre as nombre_usuario
        FROM prestamos p
        JOIN ejemplares e ON p.id_ejemplar = e.id
        JOIN usuarios u ON p.id_usuario = u.id
        WHERE p.id = %s
        """, (int(id_prestamo),))
        prestamo = cursor.fetchone()
        
        if not prestamo:
            connection.rollback()
            return jsonify({"error": "Préstamo no encontrado"}), 404

        if prestamo['estado'] == 'returned':
            connection.rollback()
            return jsonify({"error": "El préstamo ya fue devuelto"}), 400

        cursor.execute("""
        UPDATE ejemplares 
        SET ejemplares_prestados = ejemplares_prestados - 1, 
            estado = 'available' 
        WHERE id = %s
        """, (prestamo['id_ejemplar'],))

        cursor.execute("""
        UPDATE usuarios 
        SET ejemplares_prestados = ejemplares_prestados - 1 
        WHERE id = %s
        """, (prestamo['id_usuario'],))

        fecha_entrega = datetime.datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
        UPDATE prestamos 
        SET estado = 'returned', 
            fecha_entrega = %s, 
            estado_libro = %s 
        WHERE id = %s
        """, (fecha_entrega, estado_libro, int(id_prestamo)))
        
        connection.commit()

        registrar_historial(
            accion="devolucion",
            id_ejemplar=prestamo['id_ejemplar'],
            id_usuario=prestamo['id_usuario'],
            id_prestamo=id_prestamo,
            id_libro=prestamo['id_libro'],
            datos_adicionales={
                "estado_libro": estado_libro,
                "fecha_entrega": fecha_entrega,
                "titulo_libro": prestamo['titulo_libro'],
                "nombre_usuario": prestamo['nombre_usuario']
            }
        )

        return jsonify({"message": "Devolución registrada correctamente"}), 200

    except ValueError as e:
        connection.rollback()
        return jsonify({"error": "ID de préstamo inválido"}), 400
    except Error as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/add_reserva', methods=['POST'])
def add_reserva():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        data = request.form
        id_usuario = int(data['id_usuario'])
        id_libro = int(data['id_libro'])
        
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
        SELECT * FROM usuarios 
        WHERE id = %s AND tiene_reserva = FALSE
        """, (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario:
            connection.rollback()
            return jsonify({"error": "Usuario no encontrado o ya tiene una reserva activa"}), 400

        cursor.execute("""
        SELECT e.*, l.titulo as titulo_libro
        FROM ejemplares e
        JOIN libros l ON e.id_libro = l.id
        WHERE e.id_libro = %s AND e.estado = 'available'
        LIMIT 1
        """, (id_libro,))
        ejemplar = cursor.fetchone()

        if not ejemplar:
            connection.rollback()
            return jsonify({"error": "No hay ejemplares disponibles"}), 400

        cursor.execute("""
        UPDATE ejemplares 
        SET estado = 'reserved' 
        WHERE id = %s
        """, (ejemplar['id'],))

        cursor.execute("""
        UPDATE usuarios 
        SET tiene_reserva = TRUE 
        WHERE id = %s
        """, (id_usuario,))

        query = """
        INSERT INTO reservas 
        (id_usuario, id_libro, id_ejemplar, fecha_solicitud, estado)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            id_usuario,
            id_libro,
            ejemplar['id'],
            format_date(data['fecha_solicitud']),
            'pending'
        ))
        reserva_id = cursor.lastrowid
        connection.commit()

        registrar_historial(
            accion="reserva",
            id_usuario=id_usuario,
            id_libro=id_libro,
            id_ejemplar=ejemplar['id'],
            datos_adicionales={
                "fecha_solicitud": format_date(data['fecha_solicitud']),
                "titulo_libro": ejemplar['titulo_libro'],
                "nombre_usuario": usuario['nombre']
            }
        )

        return jsonify({
            "message": "Reserva creada correctamente",
            "id": str(reserva_id)
        }), 201

    except ValueError as e:
        connection.rollback()
        return jsonify({"error": "ID inválido"}), 400
    except Error as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# ------------------- ENDPOINTS GET -------------------

@app.route('/libros', methods=['GET'])
def get_libros():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM libros WHERE 1=1"
        params = []
        
        titulo = request.args.get('titulo')
        if titulo:
            query += " AND titulo LIKE %s"
            params.append(f"%{titulo}%")
            
        id_libro = request.args.get('_id')
        if id_libro:
            try:
                query += " AND id = %s"
                params.append(int(id_libro))
            except ValueError:
                return jsonify({"error": "ID de libro inválido"}), 400
        
        cursor.execute(query, params)
        libros = cursor.fetchall()
        
        for libro in libros:
            convert_ids(libro)
        
        return jsonify(libros), 200
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/ejemplares', methods=['GET'])
def get_ejemplares():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT e.*, 
               COUNT(p.id) as ejemplares_prestados,
               l.titulo as titulo_libro
        FROM ejemplares e
        LEFT JOIN prestamos p ON e.id = p.id_ejemplar AND p.estado = 'borrowed'
        JOIN libros l ON e.id_libro = l.id
        GROUP BY e.id
        """
        cursor.execute(query)
        ejemplares = cursor.fetchall()
        
        for ejemplar in ejemplares:
            convert_ids(ejemplar)
        
        return jsonify(ejemplares), 200
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/ejemplares_filtrados', methods=['GET'])
def get_ejemplares_filtrados():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT e.*, 
               COUNT(p.id) as ejemplares_prestados,
               l.titulo as titulo_libro
        FROM ejemplares e
        LEFT JOIN prestamos p ON e.id = p.id_ejemplar AND p.estado = 'borrowed'
        JOIN libros l ON e.id_libro = l.id
        WHERE 1=1
        """
        params = []
        
        nombre_libro = request.args.get('nombre_libro')
        if nombre_libro:
            query += " AND l.titulo LIKE %s"
            params.append(f"%{nombre_libro}%")
            
        id_libro = request.args.get('id_libro')
        if id_libro:
            try:
                query += " AND e.id_libro = %s"
                params.append(int(id_libro))
            except ValueError:
                return jsonify({"error": "ID de libro inválido"}), 400
        
        query += " GROUP BY e.id"
        cursor.execute(query, params)
        ejemplares = cursor.fetchall()
        
        for ejemplar in ejemplares:
            convert_ids(ejemplar)
        
        return jsonify(ejemplares), 200
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/usuarios', methods=['GET'])
def get_usuarios():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM usuarios WHERE 1=1"
        params = []
        
        nombre = request.args.get('nombre')
        if nombre:
            query += " AND nombre LIKE %s"
            params.append(f"%{nombre}%")
            
        id_usuario = request.args.get('_id')
        if id_usuario:
            try:
                query += " AND id = %s"
                params.append(int(id_usuario))
            except ValueError:
                return jsonify({"error": "ID de usuario inválido"}), 400
        
        cursor.execute(query, params)
        usuarios = cursor.fetchall()
        
        for usuario in usuarios:
            convert_ids(usuario)
        
        return jsonify(usuarios), 200
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/prestamos', methods=['GET'])
def get_prestamos():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT p.*, 
               e.titulo_libro, 
               u.nombre as nombre_usuario
        FROM prestamos p
        JOIN ejemplares e ON p.id_ejemplar = e.id
        JOIN usuarios u ON p.id_usuario = u.id
        """
        cursor.execute(query)
        prestamos = cursor.fetchall()
        
        for prestamo in prestamos:
            convert_ids(prestamo)
            # Formatear fechas
            prestamo['fecha_recibido'] = format_date(prestamo['fecha_recibido'])
            prestamo['fecha_debe_entregar'] = format_date(prestamo['fecha_debe_entregar'])
            if prestamo['fecha_entrega']:
                prestamo['fecha_entrega'] = format_date(prestamo['fecha_entrega'])
        
        return jsonify(prestamos), 200
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/reservas', methods=['GET'])
def get_reservas():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT r.*, 
               l.titulo as titulo_libro,
               u.nombre as nombre_usuario
        FROM reservas r
        JOIN libros l ON r.id_libro = l.id
        JOIN usuarios u ON r.id_usuario = u.id
        """
        cursor.execute(query)
        reservas = cursor.fetchall()
        
        for reserva in reservas:
            convert_ids(reserva)
            reserva['fecha_solicitud'] = format_date(reserva['fecha_solicitud'])
        
        return jsonify(reservas), 200
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/historial', methods=['GET'])
def get_historial():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        cursor = connection.cursor(dictionary=True)
        
        accion = request.args.get('accion')
        usuario = request.args.get('usuario')
        libro = request.args.get('libro')

        query = """
        SELECT 
            h.id,
            h.accion,
            h.fecha,
            h.datos_adicionales,
            u.nombre as nombre_usuario,
            l.titulo as titulo_libro,
            e.id as id_ejemplar,
            e.numero_total as numero_ejemplar,
            p.fecha_recibido,
            p.fecha_entrega,
            p.estado_libro
        FROM historial h
        LEFT JOIN usuarios u ON h.id_usuario = u.id
        LEFT JOIN libros l ON h.id_libro = l.id
        LEFT JOIN ejemplares e ON h.id_ejemplar = e.id
        LEFT JOIN prestamos p ON h.id_prestamo = p.id
        WHERE h.accion IN ('prestamo', 'devolucion', 'reserva')
        """
        params = []
        
        if accion and accion != 'todos':
            query += " AND h.accion = %s"
            params.append(accion)
            
        if usuario:
            query += " AND u.nombre LIKE %s"
            params.append(f"%{usuario}%")
            
        if libro:
            query += " AND l.titulo LIKE %s"
            params.append(f"%{libro}%")
        
        query += " ORDER BY h.fecha DESC LIMIT 100"
        cursor.execute(query, params)
        historial = cursor.fetchall()
        
        resultados = []
        for item in historial:
            datos_adicionales = json.loads(item['datos_adicionales']) if item['datos_adicionales'] else {}
            
            # Determinar acción para mostrar
            accion_mostrar = "prestado" if item['accion'] == "prestamo" else "devuelto" if item['accion'] == "devolucion" else item['accion']
            
            # Obtener fechas
            fecha_devolucion = format_date(item['fecha_entrega']) if item['accion'] == "devolucion" else None
            fecha_prestamo = format_date(item['fecha_recibido']) or datos_adicionales.get('fecha_recibido')
            
            # Formatear resultado
            resultado = {
                "_id": str(item['id']),
                "accion": accion_mostrar,
                "fecha_devolucion": fecha_devolucion if fecha_devolucion else '-',
                "libro": item['titulo_libro'] or datos_adicionales.get('titulo_libro', '-'),
                "ejemplar": str(item['numero_ejemplar']) if item['numero_ejemplar'] else '-',
                "usuario": item['nombre_usuario'] or datos_adicionales.get('nombre_usuario', '-'),
                "fecha_prestamo": fecha_prestamo if fecha_prestamo else '-',
                "id_usuario": str(item['id_usuario']) if 'id_usuario' in item and item['id_usuario'] else '-',
                "id_ejemplar": str(item['id_ejemplar']) if 'id_ejemplar' in item and item['id_ejemplar'] else '-',
                "estado_libro": item['estado_libro'] or datos_adicionales.get('estado_libro', '-')
            }
            resultados.append(resultado)
        
        return jsonify(resultados), 200
        
    except Error as e:
        print(f"Error en /historial: {str(e)}")
        return jsonify({"error": "Error al procesar el historial", "detalle": str(e)}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/<coleccion>/<id>', methods=['GET'])
def get_documento(coleccion, id):
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        colecciones_validas = ['libros', 'ejemplares', 'usuarios', 'prestamos', 'reservas', 'historial']
        if coleccion not in colecciones_validas:
            return jsonify({"error": "Colección inválida"}), 400

        cursor = connection.cursor(dictionary=True)
        query = f"SELECT * FROM {coleccion} WHERE id = %s"
        cursor.execute(query, (int(id),))
        documento = cursor.fetchone()

        if not documento:
            return jsonify({"error": f"{coleccion.capitalize()} no encontrado"}), 404

        convert_ids(documento)
        return jsonify(documento), 200
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# ------------------- ENDPOINTS DELETE -------------------

@app.route('/<coleccion>/<id>', methods=['DELETE'])
def delete_documento(coleccion, id):
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
        
    try:
        colecciones_validas = ['libros', 'ejemplares', 'usuarios', 'prestamos', 'reservas', 'historial']
        if coleccion not in colecciones_validas:
            return jsonify({"error": "Colección inválida"}), 400

        cursor = connection.cursor()
        query = f"DELETE FROM {coleccion} WHERE id = %s"
        cursor.execute(query, (int(id),))
        connection.commit()
        
        if cursor.rowcount > 0:
            return jsonify({"message": f"{coleccion.capitalize()} eliminado correctamente"}), 200
        else:
            return jsonify({"message": f"{coleccion.capitalize()} no encontrado"}), 404
            
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400
    except Error as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == '__main__':
    app.run(debug=True)