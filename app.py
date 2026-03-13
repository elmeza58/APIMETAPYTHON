from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import http.client
import json
import os # Necesario para el puerto en Render

app = Flask(__name__)

# Configuración de la base de datos SQLITE
# En macOS/Render la ruta relativa funciona bien para el archivo .db
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metapython.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de la tabla log
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_y_hora = db.Column(db.DateTime, default=datetime.utcnow)
    texto = db.Column(db.TEXT)

# Crear la tabla si no existe
with app.app_context():
    db.create_all()

# Función para ordenar los registros por fecha y hora
def ordenar_por_fecha_y_hora(registros):
    return sorted(registros, key=lambda x: x.fecha_y_hora, reverse=True)

@app.route('/')
def index():
    # Obtener todos los registros de la base de datos
    registros = Log.query.all()
    registros_ordenados = ordenar_por_fecha_y_hora(registros)
    return render_template('index.html', registros=registros_ordenados)

# Función para agregar mensajes y guardar en la base de datos
def agregar_mensajes_log(texto):
    nuevo_registro = Log(texto=texto)
    db.session.add(nuevo_registro)
    db.session.commit()

# Token de verificación para la configuración en Meta
TOKEN_ANDERCODE = "ANDERCODE"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        challenge = verificar_token(request)
        return challenge
    elif request.method == 'POST':
        # CORRECCIÓN: Se cambió 'reponse' por 'response' para evitar NameError
        response = recibir_mensajes(request)
        return response

def verificar_token(req):
    token = req.args.get('hub.verify_token')
    challenge = req.args.get('hub.challenge')

    if challenge and token == TOKEN_ANDERCODE:
        return challenge
    else:
        return jsonify({'error': 'Token Invalido'}), 401

def recibir_mensajes(req):
    try:
        req_data = request.get_json()
        
        # Log para depuración en la consola de Render
        print(f"JSON RECIBIDO: {json.dumps(req_data)}")
        
        entry = req_data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        # CORRECCIÓN CRÍTICA: Validar si existen mensajes. 
        # Si Meta envía un 'status' (leído/entregado), 'messages' no existe y el código fallaría.
        if 'messages' in value:
            messages = value['messages'][0]
            numero = messages["from"]
            
            # Guardar el log del mensaje entrante
            agregar_mensajes_log(json.dumps(messages))

            if "type" in messages:
                tipo = messages["type"]

                # Manejo de mensajes interactivos (Botones/Listas)
                if tipo == "interactive":
                    tipo_interactivo = messages["interactive"]["type"]
                    # Obtener el ID de la respuesta
                    text = messages["interactive"][tipo_interactivo]["id"]
                    enviar_mensajes_whatsapp(text, numero)

                # Manejo de mensajes de texto
                elif tipo == "text":
                    text = messages["text"]["body"]
                    enviar_mensajes_whatsapp(text, numero)

        return jsonify({'message': 'EVENT_RECEIVED'}), 200
    except Exception as e:
        # Imprime el error exacto en los logs de Render
        print(f"ERROR EN RECIBIR_MENSAJES: {str(e)}")
        return jsonify({'message': 'EVENT_RECEIVED'}), 200

def enviar_mensajes_whatsapp(texto, number):
    texto = texto.lower()

    # Lógica de respuestas
    if "hola" in texto:
        body_text = "🚀 Hola, ¿Cómo estás? Bienvenido."
    elif "1" in texto:
        body_text = "Información del Curso: Python con Meta API."
    elif "2" in texto:
        # Ejemplo de respuesta de ubicación
        return enviar_ubicacion(number)
    else:
        body_text = "🚀 Hola!\n\n📌 Ingresa un número:\n1️⃣. Info Curso\n2️⃣. Ubicación\n0️⃣. Menú"

    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": body_text
        }
    }
    
    ejecutar_envio(data)

def enviar_ubicacion(number):
    data = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "location",
        "location": {
            "latitude": "-12.067158831865067",
            "longitude": "-77.03377940839486",
            "name": "Estadio Nacional del Perú",
            "address": "Cercado de Lima"
        }
    }
    ejecutar_envio(data)

def ejecutar_envio(data):
    # Convertir el diccionario a formato JSON
    payload = json.dumps(data)

    # IMPORTANTE: Asegúrate de que el token sea el generado hoy en el dashboard
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer EAAS261hbLIMBQ6pdVS2bixx3WEI5C4cuFgAUXLJSW32mMH4SOWbPnO9Ua3MoKpeog48yAyYccn0s5DVUhgVfZB9xVCUDC73VWet2b97Im7YtJ1HHZAU7Tu6BC70IaWVZBerLrd1MX8kGj0SoCy5xfYOtspgjK8ZA2hapz2b1WBtbAV5LDoLStZBWcFq69VVj3PSuCi1jl6ZCuasL8bK7PeXBg33R8eBWCKowMCRjKX3EcTY2w6hb1qPGxkaDZB1goDPFBiotGrx2KQhEU6A4MZBOZAQZDZD"
    }

    connection = http.client.HTTPSConnection("graph.facebook.com")

    try:
        # Endpoint usando TU ID de número de teléfono: 1077626325424911
        connection.request("POST", "/v19.0/1077626325424911/messages", payload, headers)
        response = connection.getresponse()
        # Imprime el resultado en Render: 200 es éxito, 401 es token expirado, 400 es error de JSON
        print(f"ESTADO ENVÍO: {response.status} {response.reason}")
    except Exception as e:
        print(f"ERROR DE CONEXIÓN: {e}")
        agregar_mensajes_log(f"Error de envío: {str(e)}")
    finally:
        connection.close()

if __name__ == '__main__':
    # CORRECCIÓN: Render usa puertos dinámicos. os.environ.get('PORT') es obligatorio.
    port = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=port, debug=True)