import paho.mqtt.client as mqtt
import json
import threading
import time
import ssl
from flask import Flask, render_template, jsonify

# --- Configurações da Impressora (EDITAR ESTAS LINHAS) ---
PRINTER_IP = "192.168.1.100"  # Substitua pelo IP da sua impressora
ACCESS_CODE = "16765148" # Substitua pelo seu Código de Acesso LAN
DEVICE_ID = "03919D4C1902856" # Substitua pelo Número de Série da sua impressora
# ---------------------------------------------------------

MQTT_PORT = 8883
MQTT_USER = "bblp"
MQTT_PASS = ACCESS_CODE
MQTT_CLIENT_ID = f"web_monitor_{int(time.time())}" # ID único do cliente

# Tópicos MQTT
TOPIC_REQUEST = f"device/{DEVICE_ID}/request"
TOPIC_REPORT = f"device/{DEVICE_ID}/report"

# Variável global para armazenar o último estado da impressora
printer_status = {}
status_lock = threading.Lock() # Para acesso seguro à variável entre threads

app = Flask(__name__)

# --- Funções MQTT ---

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback executado quando o cliente se conecta ao broker MQTT."""
    if rc == 0:
        print("Conectado ao Broker MQTT da Impressora com sucesso!")
        # Inscreve-se no tópico de report
        client.subscribe(TOPIC_REPORT)
        print(f"Inscrito no tópico: {TOPIC_REPORT}")
        # Solicita o status completo inicial
        request_full_status(client)
    else:
        print(f"Falha na conexão MQTT, código de retorno: {rc}")

def on_disconnect(client, userdata, rc, properties=None):
    """Callback executado quando o cliente se desconecta."""
    print(f"Desconectado do Broker MQTT (código: {rc}). Tentando reconectar...")
    # Nota: A biblioteca paho-mqtt tentará reconectar automaticamente

def on_message(client, userdata, msg):
    """Callback executado quando uma mensagem é recebida."""
    global printer_status
    # print(f"Mensagem recebida no tópico {msg.topic}: {msg.payload.decode()}") # Debug
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        # Atualiza o status global
        with status_lock:
            # A mensagem pode conter 'print' ou outros top-level keys
            if 'print' in payload:
                # Atualiza apenas a chave 'print' ou todo o status se for pushall?
                # Por simplicidade, vamos mesclar o que recebemos
                printer_status.update(payload)
                print("Status da impressora atualizado.")
            # Adicione outras chaves de nível superior se necessário (ex: 'info', 'system')
            elif 'system' in payload:
                 printer_status.update(payload)
                 print("Status do sistema atualizado.")
            elif 'info' in payload:
                 printer_status.update(payload)
                 print("Info atualizado.")
            # Adicione mais 'elif's se houver outras estruturas de mensagem importantes

    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON: {msg.payload.decode()}")
    except Exception as e:
        print(f"Erro ao processar mensagem MQTT: {e}")

def request_full_status(client):
    """Envia uma solicitação para obter o status completo da impressora."""
    request_payload = {
        "pushing": {
            "sequence_id": str(int(time.time())), # ID de sequência único
            "command": "pushall"
        }
    }
    payload_json = json.dumps(request_payload)
    print(f"Enviando solicitação 'pushall' para {TOPIC_REQUEST}")
    client.publish(TOPIC_REQUEST, payload_json)

def mqtt_thread_func():
    """Função executada na thread MQTT para lidar com a conexão e loop."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Configura autenticação e TLS
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    # AVISO: Ignorando a verificação do certificado TLS.
    # Isso é INSEGURO para produção fora de uma rede local confiável.
    # Idealmente, você deveria obter o certificado da impressora ou usar um CA conhecido.
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT, cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True) # Necessário porque o certificado é auto-assinado

    print(f"Tentando conectar a {PRINTER_IP}:{MQTT_PORT}...")
    try:
        client.connect(PRINTER_IP, MQTT_PORT, 60)
        # loop_forever() bloqueia a thread e lida com reconexões
        client.loop_forever()
    except Exception as e:
        print(f"Erro fatal na conexão/loop MQTT: {e}")

# --- Rotas Flask ---

@app.route('/')
def index():
    """Renderiza a página HTML principal."""
    return render_template('index.html')

@app.route('/status')
def get_status():
    """Retorna o último status conhecido da impressora em formato JSON."""
    with status_lock:
        # Retorna uma cópia para evitar problemas de concorrência
        current_status = printer_status.copy()
    return jsonify(current_status)

@app.route('/command', methods=['POST'])
def handle_command():
    """Recebe um comando para ser enviado à impressora."""
    data = request.get_json()
    command = data.get('command')
    sequence_id = str(int(time.time()))

    if command == 'gcode':
        gcode_line = data.get('line')
        if not gcode_line:
            return jsonify({"success": False, "error": "Linha G-code ausente."}), 400
        payload_to_send = {
            "print": {
                "sequence_id": sequence_id,
                "command": "gcode_line",
                "param": gcode_line
            }
        }
    elif command == 'set_nozzle_temp':
        value = data.get('value')
        if value is None or not isinstance(value, (int, float)) or value < 0 or value > 300:
            return jsonify({"success": False, "error": "Temperatura do bico inválida (0-300°C)."}), 400
        payload_to_send = {
            "print": {
                "sequence_id": sequence_id,
                "command": "gcode_line",
                "param": f"M104 S{value}"
            }
        }
    elif command == 'set_bed_temp':
        value = data.get('value')
        if value is None or not isinstance(value, (int, float)) or value < 0 or value > 120:
            return jsonify({"success": False, "error": "Temperatura da mesa inválida (0-120°C)."}), 400
        payload_to_send = {
            "print": {
                "sequence_id": sequence_id,
                "command": "gcode_line",
                "param": f"M140 S{value}"
            }
        }
    else:
        return jsonify({"success": False, "error": f"Comando desconhecido: {command}"}), 400

    payload_json = json.dumps(payload_to_send)
    print(f"Enviando comando '{command}' para {TOPIC_REQUEST}")
    client = mqtt.Client()
    client.connect(PRINTER_IP, MQTT_PORT, 60)
    client.publish(TOPIC_REQUEST, payload_json)
    client.disconnect()

    return jsonify({"success": True})

# --- Inicialização ---

if __name__ == '__main__':
    # Inicia a thread MQTT em background
    mqtt_thread = threading.Thread(target=mqtt_thread_func, daemon=True)
    mqtt_thread.start()

    # Inicia o servidor Flask
    # Use host='0.0.0.0' para torná-lo acessível na sua rede local
    print("Iniciando servidor Flask em http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False) # debug=True recarrega em mudanças 