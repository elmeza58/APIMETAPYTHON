from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import http.client
import json
import os

app = Flask(__name__)

# --- CONFIGURACIÓN DE BASE DE DATOS ---
# En macOS/Render, la base de datos se crea en la carpeta 'instance'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metapython.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de la tabla log para guardar el historial
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_y_hora = db.Column(db.DateTime, default=datetime.utcnow)
    texto = db.Column(db.TEXT)

# Crear la tabla automáticamente al arrancar
with app.app_context():
    db.create_all()

# --- FUNCIONES DE APOYO ---

def agregar_mensajes_log(texto):
    """Guarda cualquier texto o JSON en la base de datos SQLite."""
    nuevo_registro = Log(texto=texto)
    db.session.add(nuevo_registro)
    db.session.commit()

def ordenar_por_fecha_y_hora(registros):
    return sorted(registros, key=lambda x: x.fecha_y_hora, reverse=True)

# --- RUTAS ---

@app.route('/')
def index():
    """Muestra el historial de mensajes en el navegador."""
    registros = Log.query.all()
    registros_ordenados = ordenar_por_fecha_y_hora(registros)
    return render_template('index.html', registros=registros_ordenados)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Punto de conexión para Meta."""
    if request.method == 'GET':
        return verificar_token(request)
    elif request.method == 'POST':
        return recibir_mensajes(request)

def verificar_token(req):
    """Valida el webhook en el panel de Meta (hub.challenge)."""
    token = req.args.get('hub.verify_token')
    challenge = req.args.get('hub.challenge')
    
    # Token configurado en el panel de Meta
    if challenge and token == "ANDERCODE":
        return challenge, 200
    else:
        return jsonify({'error': 'Token Invalido'}), 401

def recibir_mensajes(req):
    """Procesa los mensajes entrantes de WhatsApp."""
    try:
        req_data = request.get_json()
        entry = req_data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        # IMPORTANTE: Solo procesamos si la llave 'messages' existe
        # Esto evita que el código falle con las notificaciones de 'leído' (statuses)
        if 'messages' in value:
            messages = value['messages'][0]
            numero = messages["from"]
            tipo = messages.get("type")

            # Guardamos el mensaje crudo en el Log para ver el JSON en el index
            agregar_mensajes_log(json.dumps(messages))

            # Procesar según el tipo de mensaje
            if tipo == "text":
                text = messages["text"]["body"]
                enviar_mensajes_whatsapp(text, numero)

            elif tipo == "interactive":
                tipo_interactivo = messages["interactive"]["type"]
                # Extrae el ID del botón o de la lista seleccionada
                text = messages["interactive"][tipo_interactivo]["id"]
                enviar_mensajes_whatsapp(text, numero)

        return jsonify({'message': 'EVENT_RECEIVED'}), 200

    except Exception as e:
        # Imprime el error en los logs de Render para depuración técnica
        print(f"Error en recibir_mensajes: {e}")
        return jsonify({'message': 'EVENT_RECEIVED'}), 200

def enviar_mensajes_whatsapp(texto, number):
    """Envía la respuesta automática a través de la Graph API."""
    texto = texto.lower()

    # --- LÓGICA DEL MENÚ ---
    if "hola" in texto:
        body_text = "🚀 Hola, ¿Cómo estás? Bienvenido al bot de prueba."
    elif "1" in texto:
        body_text = "Has seleccionado: Información del curso. Es un curso de Python con Meta."
    elif "2" in texto:
        # Ejemplo de respuesta de ubicación (Opcional: puedes cambiar el tipo a 'location')
        body_text = "📍 Nuestra ubicación es: Estadio Nacional del Perú."
    elif "3" in texto:
        body_text = "📄 En breve recibirás el temario en PDF."
    elif "0" in texto:
        body_text = "🚀 Regresando al menú...\n1. Info\n2. Ubicación\n3. PDF\n0. Menú"
    else:
        body_text = "🚀 Hola!\n\n📌 Ingresa un número para ayudarte:\n1️⃣ Info Curso\n2️⃣ Ubicación\n3️⃣ Temario PDF\n0️⃣ Menú"

    # Estructura del JSON de respuesta
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
    
    # Payload convertido a JSON string
    payload = json.dumps(data)

    # REEMPLAZA ESTE TOKEN por el más reciente de tu dashboard
    token_acceso = "EAAS261hbLIMBQ6pdVS2bixx3WEI5C4cuFgAUXLJSW32mMH4SOWbPnO9Ua3MoKpeog48yAyYccn0s5DVUhgVfZB9xVCUDC73VWet2b97Im7YtJ1HHZAU7Tu6BC70IaWVZBerLrd1MX8kGj0SoCy5xfYOtspgjK8ZA2hapz2b1WBtbAV5LDoLStZBWcFq69VVj3PSuCi1jl6ZCuasL8bK7PeXBg33R8eBWCKowMCRjKX3EcTY2w6hb1qPGxkaDZB1goDPFBiotGrx2KQhEU6A4MZBOZAQZDZD"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token_acceso}"
    }

    # Conexión segura con Meta
    connection = http.client.HTTPSConnection("graph.facebook.com")

    try:
        # USANDO TU ID CORRECTO: 1077626325424911
        endpoint = "/v19.0/1077626325424911/messages"
        connection.request("POST", endpoint, payload, headers)
        
        response = connection.getresponse()
        # Imprime el resultado en Render para verificar si fue 200 OK o error (400, 401)
        print(f"Respuesta de Meta: {response.status} {response.reason}")
        
    except Exception as e:
        print(f"Error al conectar con Meta: {e}")
    finally:
        connection.close()

# --- ARRANQUE DEL SERVIDOR ---
if __name__ == '__main__':
    # Render asigna el puerto dinámicamente, por eso usamos os.environ
    port = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=port, debug=True)