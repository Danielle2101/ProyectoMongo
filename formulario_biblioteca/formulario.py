from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime

app = Flask(__name__)
CORS(app)

client = MongoClient('mongodb://localhost:27017/')
db = client['biblioteca']

try:
    client.admin.command('ping')
    print("✅ Conectado a MongoDB")
except Exception as e:
    print("❌ Error conectando a MongoDB:", e)
    raise e

@app.route('/')
def index():
    return ('formulario.html')

# ------------------- FUNCIONES AUXILIARES -------------------

def parse_object_id(data, field):
    try:
        return ObjectId(data[field])
    except:
        raise ValueError(f"ID inválido para el campo '{field}'")

def convert_ids(document):
    document['_id'] = str(document['_id'])
    for key in ['id_usuario', 'id_ejemplar', 'id_libro', 'id_prestamo']:
        if key in document:
            document[key] = str(document[key])
    return document

def registrar_historial(accion, id_ejemplar=None, id_usuario=None, id_prestamo=None, id_libro=None, datos_adicionales=None):
    registro = {
        "accion": accion,
        "fecha": datetime.datetime.now(),
        "datos_adicionales": datos_adicionales or {}
    }
    
    if id_ejemplar:
        registro["id_ejemplar"] = str(id_ejemplar)
    if id_usuario:
        registro["id_usuario"] = str(id_usuario)
    if id_prestamo:
        registro["id_prestamo"] = str(id_prestamo)
    if id_libro:
        registro["id_libro"] = str(id_libro)
    
    db.historial.insert_one(registro)

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
        data = request.form  # Asegúrate que es request.form y no request.json
        numero_ejemplar = data.get('numero_total') or data.get('numero_ejemplar')
        
        # Verificar que el libro existe
        libro = db.libros.find_one({"_id": ObjectId(data['id_libro'])})
        if not libro:
            return jsonify({"error": "Libro no encontrado"}), 404
            
        ejemplar = {
            "numero_total": int(numero_ejemplar),
            "ejemplares_prestados": 0,
            "estado": data['estado'],
            "id_libro": data['id_libro'],
            "titulo_libro": libro['titulo']
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
            "ejemplares_prestados": 0,
            "tiene_reserva": False
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

        # 1. Verificar disponibilidad del ejemplar
        ejemplar = db.ejemplares.find_one({"_id": id_ejemplar})
        if not ejemplar:
            return jsonify({"error": "Ejemplar no encontrado"}), 404
            
        disponibles = int(ejemplar.get('numero_total', 1)) - int(ejemplar.get('ejemplares_prestados', 0))
        if disponibles <= 0:
            return jsonify({
                "error": "No hay ejemplares disponibles",
                "detalle": {
                    "total_ejemplares": ejemplar.get('numero_total'),
                    "prestados": ejemplar.get('ejemplares_prestados', 0)
                }
            }), 400

        # 2. Actualizar contadores
        db.ejemplares.update_one(
            {"_id": id_ejemplar},
            {
                "$inc": {"ejemplares_prestados": 1},
                "$set": {"estado": "borrowed"}
            }
        )

        # 3. Actualizar contador de usuario
        db.usuarios.update_one(
            {"_id": id_usuario},
            {"$inc": {"ejemplares_prestados": 1}}
        )

        # 4. Crear registro de préstamo
        prestamo = {
            "id_ejemplar": str(id_ejemplar),
            "id_usuario": str(id_usuario),
            "fecha_recibido": data['fecha_recibido'],
            "fecha_debe_entregar": data['fecha_debe_entregar'],
            "estado": "borrowed",
            "fecha_entrega": None,
            "estado_libro": None
        }

        prestamo_id = db.prestamos.insert_one(prestamo).inserted_id

        # 5. Registrar en historial
        registrar_historial(
            accion="prestamo",
            id_ejemplar=id_ejemplar,
            id_usuario=id_usuario,
            id_prestamo=prestamo_id,
            datos_adicionales={
                "fecha_recibido": data['fecha_recibido'],
                "fecha_devolucion_prevista": data['fecha_debe_entregar']
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

    except Exception as e:
        # Revertir cambios en caso de error
        if 'id_ejemplar' in locals():
            db.ejemplares.update_one(
                {"_id": id_ejemplar},
                {"$inc": {"ejemplares_prestados": -1}}
            )
        if 'id_usuario' in locals():
            db.usuarios.update_one(
                {"_id": id_usuario},
                {"$inc": {"ejemplares_prestados": -1}}
            )
        return jsonify({"error": str(e)}), 400

@app.route('/devolver_prestamo/<id_prestamo>', methods=['POST'])
def devolver_prestamo(id_prestamo):
    try:
        data = request.form
        prestamo = db.prestamos.find_one({"_id": ObjectId(id_prestamo)})
        
        if not prestamo:
            return jsonify({"error": "Préstamo no encontrado"}), 404

        # 1. Actualizar ejemplar (disminuir prestados)
        db.ejemplares.update_one(
            {"_id": ObjectId(prestamo['id_ejemplar'])},
            {
                "$inc": {"ejemplares_prestados": -1},
                "$set": {"estado": "available"}
            }
        )

        # 2. Actualizar usuario (disminuir contador)
        db.usuarios.update_one(
            {"_id": ObjectId(prestamo['id_usuario'])},
            {"$inc": {"ejemplares_prestados": -1}}
        )

        # 3. Actualizar préstamo
        db.prestamos.update_one(
            {"_id": ObjectId(id_prestamo)},
            {"$set": {
                "estado": "returned",
                "fecha_entrega": datetime.datetime.now().strftime("%Y-%m-%d"),
                "estado_libro": data.get('estado_libro', 'bueno')
            }}
        )

        # 4. Registrar en historial
        registrar_historial(
            accion="devolucion",
            id_ejemplar=prestamo['id_ejemplar'],
            id_usuario=prestamo['id_usuario'],
            id_prestamo=id_prestamo,
            datos_adicionales={
                "estado_libro": data.get('estado_libro', 'bueno'),
                "fecha_entrega": datetime.datetime.now().strftime("%Y-%m-%d")
            }
        )

        return jsonify({"message": "Devolución registrada correctamente"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/add_reserva', methods=['POST'])
def add_reserva():
    try:
        data = request.form
        id_usuario = parse_object_id(data, 'id_usuario')
        id_libro = parse_object_id(data, 'id_libro')

        # Buscar un ejemplar disponible de este libro
        ejemplar = db.ejemplares.find_one({
            "id_libro": str(id_libro),
            "estado": "available"
        })

        if not ejemplar:
            return jsonify({"error": "No hay ejemplares disponibles"}), 400

        # Marcar ejemplar como reservado
        db.ejemplares.update_one(
            {"_id": ejemplar['_id']},
            {"$set": {"estado": "reserved"}}
        )

        # Actualizar el estado del usuario
        db.usuarios.update_one(
            {"_id": id_usuario},
            {"$set": {"tiene_reserva": True}}
        )

        reserva = {
            "id_usuario": str(id_usuario),
            "id_libro": str(id_libro),
            "id_ejemplar": str(ejemplar['_id']),
            "fecha_solicitud": data['fecha_solicitud'],
            "estado": "pending"
        }

        registrar_historial(
            accion="reserva",
            id_usuario=id_usuario,
            id_libro=id_libro,
            id_ejemplar=ejemplar['_id'],
            datos_adicionales={
                "fecha_solicitud": data['fecha_solicitud']
            }
        )

        reserva_id = db.reservas.insert_one(reserva).inserted_id
        return jsonify({"message": "Reserva creada", "id": str(reserva_id)}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ------------------- ENDPOINTS GET -------------------

@app.route('/libros', methods=['GET'])
def get_libros():
    try:
        filtros = {}
        titulo = request.args.get('titulo')
        if titulo:
            filtros['titulo'] = {'$regex': titulo, '$options': 'i'}
            
        id_libro = request.args.get('_id')
        if id_libro:
            try:
                filtros['_id'] = ObjectId(id_libro)
            except:
                return jsonify({"error": "ID de libro inválido"}), 400
        
        libros = list(db.libros.find(filtros))
        return jsonify([convert_ids(libro) for libro in libros]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/ejemplares', methods=['GET'])
def get_ejemplares():
    try:
        ejemplares = list(db.ejemplares.find())
        return jsonify([convert_ids(ejemplar) for ejemplar in ejemplares]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/ejemplares_filtrados', methods=['GET'])
def get_ejemplares_filtrados():
    try:
        filtros = {}
        nombre_libro = request.args.get('nombre_libro')
        id_libro = request.args.get('id_libro')
        
        if nombre_libro:
            # Buscar IDs de libros que coincidan con el nombre
            libros_coincidentes = list(db.libros.find(
                {"titulo": {"$regex": nombre_libro, "$options": "i"}},
                {"_id": 1}
            ))
            ids_libros = [str(libro["_id"]) for libro in libros_coincidentes]
            filtros["id_libro"] = {"$in": ids_libros}
            
        if id_libro:
            try:
                filtros["id_libro"] = str(ObjectId(id_libro))
            except:
                return jsonify({"error": "ID de libro inválido"}), 400
        
        pipeline = [
            {"$match": filtros} if filtros else {"$match": {}},
            {
                "$lookup": {
                    "from": "prestamos",
                    "let": {"ejemplar_id": {"$toString": "$_id"}},
                    "pipeline": [
                        {"$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$id_ejemplar", "$$ejemplar_id"]},
                                    {"$eq": ["$estado", "borrowed"]}
                                ]
                            }
                        }}
                    ],
                    "as": "prestamos_activos"
                }
            },
            {
                "$addFields": {
                    "ejemplares_prestados": {"$size": "$prestamos_activos"},
                    "numero_total": "$numero_total"
                }
            }
        ]
        
        ejemplares = list(db.ejemplares.aggregate(pipeline))
        return jsonify([convert_ids(ejemplar) for ejemplar in ejemplares]), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/usuarios', methods=['GET'])
def get_usuarios():
    try:
        filtros = {}
        nombre = request.args.get('nombre')
        if nombre:
            filtros['nombre'] = {'$regex': nombre, '$options': 'i'}
            
        id_usuario = request.args.get('_id')
        if id_usuario:
            try:
                filtros['_id'] = ObjectId(id_usuario)
            except:
                return jsonify({"error": "ID de usuario inválido"}), 400
        
        usuarios = list(db.usuarios.find(filtros))
        return jsonify([convert_ids(usuario) for usuario in usuarios]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
    try:
        # Obtener parámetros de filtrado
        accion = request.args.get('accion')
        usuario = request.args.get('usuario')
        libro = request.args.get('libro')

        # Construir query de filtrado
        query = {}
        if accion and accion != 'todos':
            query['accion'] = accion
        if usuario:
            query['usuario'] = {'$regex': usuario, '$options': 'i'}
        if libro:
            query['libro'] = {'$regex': libro, '$options': 'i'}
        
        historial_crudo = list(db.historial.find(query).sort("fecha", -1).limit(100))
        
        resultados = []
        for item in historial_crudo:
            try:
                # Convertir fecha
                fecha = item['fecha'] if isinstance(item['fecha'], str) else item['fecha'].strftime("%Y-%m-%d %H:%M:%S")
                
                # Obtener datos relacionados
                prestamo_data = db.prestamos.find_one({"_id": ObjectId(item.get('id_prestamo', ''))}) or {}
                ejemplar_data = db.ejemplares.find_one({"_id": ObjectId(item.get('id_ejemplar', prestamo_data.get('id_ejemplar', '')))}) or {}
                libro_data = db.libros.find_one({"_id": ObjectId(ejemplar_data.get('id_libro', ''))}) or {}
                usuario_data = db.usuarios.find_one({"_id": ObjectId(item.get('id_usuario', prestamo_data.get('id_usuario', '')))}) or {}

                # Determinar acción para mostrar
                accion_mostrar = "prestado" if item.get('accion') == "prestamo" else "devuelto" if item.get('accion') == "devolucion" else item.get('accion', '-')
                
                # Obtener fecha préstamo (prioridad: datos_adicionales > prestamo_data > fecha actual)
                fecha_prestamo = item.get('datos_adicionales', {}).get('fecha_recibido', 
                                prestamo_data.get('fecha_recibido', 
                                datetime.datetime.now().strftime("%Y-%m-%d")))
                
                # Formatear resultado
                resultado = {
                    "_id": str(item['_id']),
                    "accion": accion_mostrar,
                    "fecha_devolucion": fecha if item.get('accion') == "devolucion" else '-',
                    "libro": libro_data.get('titulo', '-'),
                    "ejemplar": ejemplar_data.get('numero_total', ejemplar_data.get('numero_ejemplar', '-')),
                    "usuario": usuario_data.get('nombre', '-'),
                    "fecha_prestamo": fecha_prestamo,
                    "id_usuario": str(usuario_data.get('_id', '-')),
                    "id_ejemplar": str(ejemplar_data.get('_id', '-')),
                    "estado_libro": prestamo_data.get('estado_libro', item.get('datos_adicionales', {}).get('estado_libro', '-'))
                }
                resultados.append(resultado)
                
            except Exception as e:
                print(f"Error procesando documento {item.get('_id')}: {str(e)}")
                continue
        
        return jsonify(resultados), 200
        
    except Exception as e:
        print(f"Error en /historial: {str(e)}")
        return jsonify({"error": "Error al procesar el historial", "detalle": str(e)}), 500

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

        data = request.json
        if not data:
            return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400

        resultado = db[coleccion].update_one(
            {"_id": ObjectId(id)},
            {"$set": data}
        )

        if resultado.matched_count:
            if coleccion == 'prestamos' and 'estado' in data and data['estado'] == 'returned':
                prestamo = db.prestamos.find_one({"_id": ObjectId(id)})
                if prestamo:
                    registrar_historial(
                        accion="devolucion",
                        id_ejemplar=prestamo['id_ejemplar'],
                        id_usuario=prestamo['id_usuario'],
                        id_prestamo=id,
                        datos_adicionales={
                            "fecha_entrega": data.get('fecha_entrega', datetime.datetime.now().isoformat()),
                            "estado_libro": data.get('estado_libro', 'bueno')
                        }
                    )
            
            return jsonify({"message": f"{coleccion.capitalize()} actualizado correctamente"}), 200
        else:
            return jsonify({"message": f"{coleccion.capitalize()} no encontrado"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)