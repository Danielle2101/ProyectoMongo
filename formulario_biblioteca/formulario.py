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

if __name__ == '__main__':
    app.run(debug=True)