import json

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

#Configuracion de la base de datos SQLITE
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metapython.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de la tabla log
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True) # type: ignore
    fecha_y_hora = db.Column(db.DateTime, default=datetime.utcnow) # type: ignore
    texto = db.Column(db.TEXT) # type: ignore

# Crear la tabla si no existe
with app.app_context():
    db.create_all()

    prueba1 = Log(texto='Mensaje de Prueba 1')
    prueba2 = Log(texto='Mensaje de Prueba 2')

    db.session.add(prueba1)
    db.session.add(prueba2)
    db.session.commit()

# Funcion para ordenar os registros por fecha y hora
def ordenar_por_fecha_y_hora(registros):
    return sorted(registros, key=lambda x: x.fecha_y_hora, reverse=True)

@app.route('/')
def index():
    #obtener todos los registros de la base de datos
    registros = Log.query.all()
    registros_ordenados = ordenar_por_fecha_y_hora(registros)
    return render_template('index.html', registros=registros_ordenados)

mensajes_log=[]

# FUNCION PARA AGREGAR MENSAJES Y GUARDAR EN LA BASE DE DATOS
def agregar_mensajes_log(texto):
    mensajes_log.append(texto)

    
# Token de verificacion para la configuraion
TOKEN_ANDERCODE = 'ANDERCODE'

@app.route('/webhook', methods=['GET', 'POST']) # type: ignore
def webhook():
    if request.method == 'POST':
        challenge = verificar_token(request)
        return challenge

def verificar_token(req):
    token = req.args.get('hub.verify_token')
    challenge = req.args.get('hub.challenge')

    if challenge and token == TOKEN_ANDERCODE:
        return challenge
    else:
        return jsonify({'error':'Token invalido'}),401

def recibir_mensaje(req):
    req = request.get_json()
    agregar_mensajes_log(req)
    return jsonify({'message':'EVENT_RECEIVED'})
    




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)