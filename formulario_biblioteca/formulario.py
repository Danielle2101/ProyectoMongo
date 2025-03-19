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


# Agregar libros
@app.route('/add_libro', methods=['POST'])
def add_libro():
    data = request.form
    db.libros.insert_one({
        "titulo": data['titulo'],
        "autor": data['autor'],
        "paginas": int(data['paginas']),
        "editorial": data['editorial']
    })
    return jsonify({"message": "Libro agregado correctamente"}), 201

# Agregar ejemplares (incluye id_libro)
@app.route('/add_ejemplar', methods=['POST'])
def add_ejemplar():
    data = request.form
    db.ejemplares.insert_one({
        "numero_ejemplar": data['numero_ejemplar'],
        "estado": data['estado'],
        "id_libro": data['id_libro']
    })
    return jsonify({"message": "Ejemplar agregado correctamente"}), 201

# Agregar usuarios
@app.route('/add_usuario', methods=['POST'])
def add_usuario():
    data = request.form
    db.usuarios.insert_one({
        "nombre": data['nombre'],
        "correo": data['correo'],
        "telefono": data['telefono'],
        "prestamos_activos": [],
        "reservas_activas": []
    })
    return jsonify({"message": "Usuario agregado correctamente"}), 201

# Agregar préstamos
@app.route('/add_prestamo', methods=['POST'])
def add_prestamo():
    data = request.form
    prestamo = {
        "id_ejemplar": data['id_ejemplar'],
        "id_usuario": data['id_usuario'],
        "fecha_recibido": data['fecha_recibido'],
        "fecha_entrega": None,
        "fecha_debe_entregar": data['fecha_debe_entregar'],
        "estado": "borrowed"
    }
    prestamo_id = db.prestamos.insert_one(prestamo).inserted_id
    db.ejemplares.update_one(
        {"_id": ObjectId(data['id_ejemplar'])},
        {"$set": {"estado": "borrowed"}}
    )
    db.usuarios.update_one(
        {"_id": ObjectId(data['id_usuario'])},
        {"$push": {"prestamos_activos": {
            "id_ejemplar": data['id_ejemplar'],
            "fecha_debe_entregar": data['fecha_debe_entregar']
        }}}
    )
    return jsonify({"message": "Préstamo agregado correctamente", "id": str(prestamo_id)}), 201

# Agregar reservas
@app.route('/add_reserva', methods=['POST'])
def add_reserva():
    data = request.form
    reserva_id = db.reservas.insert_one({
        "id_usuario": data['id_usuario'],
        "id_libro": data['id_libro'],
        "estado": "reserved",
        "fecha_solicitud": data['fecha_solicitud']
    }).inserted_id
    db.usuarios.update_one(
        {"_id": ObjectId(data['id_usuario'])},
        {"$push": {"reservas_activas": {
            "id_reserva": str(reserva_id),
            "fecha_reserva": data['fecha_solicitud']
        }}}
    )
    return jsonify({"message": "Reserva agregada correctamente", "id": str(reserva_id)}), 201

# Agregar historial
@app.route('/add_historial', methods=['POST'])
def add_historial():
    data = request.form
    db.historial.insert_one({
        "id_ejemplar": data['id_ejemplar'],
        "id_usuario": data['id_usuario'],
        "id_prestamo": data['id_prestamo'],
        "fecha_entrega": data['fecha_entrega'],
        "estado_libro": data['estado_libro']
    })
    return jsonify({"message": "Historial agregado correctamente"}), 201

# Obtener libros
@app.route('/libros', methods=['GET'])
def get_libros():
    libros = list(db.libros.find())
    for libro in libros:
        libro['_id'] = str(libro['_id'])
    return jsonify(libros), 200

# Obtener ejemplares
@app.route('/ejemplares', methods=['GET'])
def get_ejemplares():
    ejemplares = list(db.ejemplares.find())
    for ejemplar in ejemplares:
        ejemplar['_id'] = str(ejemplar['_id'])
    return jsonify(ejemplares), 200

# Obtener usuarios
@app.route('/usuarios', methods=['GET'])
def get_usuarios():
    usuarios = list(db.usuarios.find())
    for usuario in usuarios:
        usuario['_id'] = str(usuario['_id'])
    return jsonify(usuarios), 200

# Obtener préstamos (con conversión condicional)
@app.route('/prestamos', methods=['GET'])
def get_prestamos():
    prestamos = list(db.prestamos.find())
    for prestamo in prestamos:
        prestamo['_id'] = str(prestamo['_id'])
        if 'id_usuario' in prestamo:
            prestamo['id_usuario'] = str(prestamo['id_usuario'])
        if 'id_ejemplar' in prestamo:
            prestamo['id_ejemplar'] = str(prestamo['id_ejemplar'])
    return jsonify(prestamos), 200

# Obtener reservas (con conversión condicional)
@app.route('/reservas', methods=['GET'])
def get_reservas():
    reservas = list(db.reservas.find())
    for reserva in reservas:
        reserva['_id'] = str(reserva['_id'])
        if 'id_usuario' in reserva:
            reserva['id_usuario'] = str(reserva['id_usuario'])
        if 'id_libro' in reserva:
            reserva['id_libro'] = str(reserva['id_libro'])
    return jsonify(reservas), 200

# Obtener historial (con conversión condicional)
@app.route('/historial', methods=['GET'])
def get_historial():
    historial = list(db.historial.find())
    for item in historial:
        item['_id'] = str(item['_id'])
        if 'id_usuario' in item:
            item['id_usuario'] = str(item['id_usuario'])
        if 'id_ejemplar' in item:
            item['id_ejemplar'] = str(item['id_ejemplar'])
        if 'id_prestamo' in item:
            item['id_prestamo'] = str(item['id_prestamo'])
    return jsonify(historial), 200

# DELETE endpoints
@app.route('/libros/<id>', methods=['DELETE'])
def delete_libro(id):
    result = db.libros.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return jsonify({"message": "Libro eliminado correctamente"}), 200
    return jsonify({"message": "Libro no encontrado"}), 404

@app.route('/ejemplares/<id>', methods=['DELETE'])
def delete_ejemplar(id):
    result = db.ejemplares.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return jsonify({"message": "Ejemplar eliminado correctamente"}), 200
    return jsonify({"message": "Ejemplar no encontrado"}), 404

@app.route('/usuarios/<id>', methods=['DELETE'])
def delete_usuario(id):
    result = db.usuarios.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return jsonify({"message": "Usuario eliminado correctamente"}), 200
    return jsonify({"message": "Usuario no encontrado"}), 404

@app.route('/prestamos/<id>', methods=['DELETE'])
def delete_prestamo(id):
    result = db.prestamos.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return jsonify({"message": "Préstamo eliminado correctamente"}), 200
    return jsonify({"message": "Préstamo no encontrado"}), 404

@app.route('/reservas/<id>', methods=['DELETE'])
def delete_reserva(id):
    result = db.reservas.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return jsonify({"message": "Reserva eliminada correctamente"}), 200
    return jsonify({"message": "Reserva no encontrada"}), 404

@app.route('/historial/<id>', methods=['DELETE'])
def delete_historial(id):
    result = db.historial.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return jsonify({"message": "Historial eliminado correctamente"}), 200
    return jsonify({"message": "Historial no encontrado"}), 404

if __name__ == '__main__':
    app.run(debug=True)
