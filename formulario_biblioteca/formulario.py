from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas las rutas

client = MongoClient('mongodb://localhost:27017/')
db = client['biblioteca']

@app.route('/')
def index():
    return "¡Bienvenido a la gestión de la biblioteca!"


# ------------------- FUNCIONES AUXILIARES -------------------

def parse_object_id(data, field):
    """Convierte a ObjectId si es válido, sino lanza error"""
    try:
        return ObjectId(data[field])
    except:
        raise ValueError(f"ID inválido para el campo '{field}'")

def convert_ids(document):
    """Convierte ObjectId en string para cualquier documento"""
    document['_id'] = str(document['_id'])
    for key in ['id_usuario', 'id_ejemplar', 'id_libro', 'id_prestamo']:
        if key in document:
            document[key] = str(document[key])
    return document


# ------------------- ENDPOINTS POST -------------------

@app.route('/add_libro', methods=['POST'])
def add_libro():
    try:
        data = request.form
        libro = {
            "titulo": data['titulo'],
            "autor": data['autor'],
            "paginas": int(data['paginas']),
            "editorial": data['editorial']
        }
        db.libros.insert_one(libro)
        return jsonify({"message": "Libro agregado correctamente"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/add_ejemplar', methods=['POST'])
def add_ejemplar():
    try:
        data = request.form
        ejemplar = {
            "numero_ejemplar": data['numero_ejemplar'],
            "estado": data['estado'],
            "id_libro": data['id_libro']
        }
        db.ejemplares.insert_one(ejemplar)
        return jsonify({"message": "Ejemplar agregado correctamente"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/add_usuario', methods=['POST'])
def add_usuario():
    try:
        data = request.form
        usuario = {
            "nombre": data['nombre'],
            "correo": data['correo'],
            "telefono": data['telefono'],
            "prestamos_activos": [],
            "reservas_activas": []
        }
        db.usuarios.insert_one(usuario)
        return jsonify({"message": "Usuario agregado correctamente"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/add_prestamo', methods=['POST'])
def add_prestamo():
    try:
        data = request.form
        id_ejemplar = parse_object_id(data, 'id_ejemplar')
        id_usuario = parse_object_id(data, 'id_usuario')

        prestamo = {
            "id_ejemplar": str(id_ejemplar),
            "id_usuario": str(id_usuario),
            "fecha_recibido": data['fecha_recibido'],
            "fecha_entrega": None,
            "fecha_debe_entregar": data['fecha_debe_entregar'],
            "estado": "borrowed"
        }

        prestamo_id = db.prestamos.insert_one(prestamo).inserted_id

        db.ejemplares.update_one(
            {"_id": id_ejemplar},
            {"$set": {"estado": "borrowed"}}
        )

        db.usuarios.update_one(
            {"_id": id_usuario},
            {"$push": {"prestamos_activos": {
                "id_ejemplar": str(id_ejemplar),
                "fecha_debe_entregar": data['fecha_debe_entregar']
            }}}
        )

        return jsonify({"message": "Préstamo agregado correctamente", "id": str(prestamo_id)}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/add_reserva', methods=['POST'])
def add_reserva():
    try:
        data = request.form
        id_usuario = parse_object_id(data, 'id_usuario')
        reserva = {
            "id_usuario": str(id_usuario),
            "id_libro": data['id_libro'],
            "estado": "reserved",
            "fecha_solicitud": data['fecha_solicitud']
        }

        reserva_id = db.reservas.insert_one(reserva).inserted_id

        db.usuarios.update_one(
            {"_id": id_usuario},
            {"$push": {"reservas_activas": {
                "id_reserva": str(reserva_id),
                "fecha_reserva": data['fecha_solicitud']
            }}}
        )

        return jsonify({"message": "Reserva agregada correctamente", "id": str(reserva_id)}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/add_historial', methods=['POST'])
def add_historial():
    try:
        data = request.form
        historial = {
            "id_ejemplar": data['id_ejemplar'],
            "id_usuario": data['id_usuario'],
            "id_prestamo": data['id_prestamo'],
            "fecha_entrega": data['fecha_entrega'],
            "estado_libro": data['estado_libro']
        }
        db.historial.insert_one(historial)
        return jsonify({"message": "Historial agregado correctamente"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------- ENDPOINTS GET -------------------

@app.route('/libros', methods=['GET'])
def get_libros():
    libros = list(db.libros.find())
    return jsonify([convert_ids(libro) for libro in libros]), 200

@app.route('/ejemplares', methods=['GET'])
def get_ejemplares():
    ejemplares = list(db.ejemplares.find())
    return jsonify([convert_ids(ejemplar) for ejemplar in ejemplares]), 200

@app.route('/usuarios', methods=['GET'])
def get_usuarios():
    usuarios = list(db.usuarios.find())
    return jsonify([convert_ids(usuario) for usuario in usuarios]), 200

@app.route('/prestamos', methods=['GET'])
def get_prestamos():
    prestamos = list(db.prestamos.find())
    return jsonify([convert_ids(prestamo) for prestamo in prestamos]), 200

@app.route('/reservas', methods=['GET'])
def get_reservas():
    reservas = list(db.reservas.find())
    return jsonify([convert_ids(reserva) for reserva in reservas]), 200

@app.route('/historial', methods=['GET'])
def get_historial():
    historial = list(db.historial.find())
    return jsonify([convert_ids(item) for item in historial]), 200


@app.route('/<coleccion>/<id>', methods=['GET'])
def get_documento(coleccion, id):
    try:
        colecciones_validas = ['libros', 'ejemplares', 'usuarios', 'prestamos', 'reservas', 'historial']
        if coleccion not in colecciones_validas:
            return jsonify({"error": "Colección inválida"}), 400

        documento = db[coleccion].find_one({"_id": ObjectId(id)})
        if not documento:
            return jsonify({"error": f"{coleccion.capitalize()} no encontrado"}), 404

        return jsonify(convert_ids(documento)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------- ENDPOINTS DELETE -------------------

@app.route('/<coleccion>/<id>', methods=['DELETE'])
def delete_documento(coleccion, id):
    try:
        colecciones_validas = ['libros', 'ejemplares', 'usuarios', 'prestamos', 'reservas', 'historial']
        if coleccion not in colecciones_validas:
            return jsonify({"error": "Colección inválida"}), 400

        resultado = db[coleccion].delete_one({"_id": ObjectId(id)})

        if resultado.deleted_count:
            return jsonify({"message": f"{coleccion.capitalize()} eliminado correctamente"}), 200
        else:
            return jsonify({"message": f"{coleccion.capitalize()} no encontrado"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------- ENDPOINT PUT (EDITAR) -------------------


@app.route('/<coleccion>/<id>', methods=['PUT'])
def editar_documento(coleccion, id):
    try:
        colecciones_validas = ['libros', 'ejemplares', 'usuarios', 'prestamos', 'reservas', 'historial']
        if coleccion not in colecciones_validas:
            return jsonify({"error": "Colección inválida"}), 400

        data = request.json  # JSON con los campos a actualizar
        if not data:
            return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400

        resultado = db[coleccion].update_one(
            {"_id": ObjectId(id)},
            {"$set": data}
        )

        if resultado.matched_count:
            return jsonify({"message": f"{coleccion.capitalize()} actualizado correctamente"}), 200
        else:
            return jsonify({"message": f"{coleccion.capitalize()} no encontrado"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------- INICIO DE LA APP -------------------

if __name__ == '__main__':
    app.run(debug=True)
