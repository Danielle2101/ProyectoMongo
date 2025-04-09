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


if __name__ == '__main__':
    app.run(debug=True)