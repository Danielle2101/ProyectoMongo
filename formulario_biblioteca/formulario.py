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

if __name__ == '__main__':
    app.run(debug=True)