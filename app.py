import paho.mqtt.client as mqtt
import json
import threading
import time
import ssl
import requests
import os
from flask import Flask, render_template, jsonify, Response, stream_with_context

# --- Carregar Configuração ---
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
config = {}
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    print(f"ERRO CRÍTICO: Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
    print("Por favor, copie 'config.json.example' para 'config.json' e preencha seus dados.")
    exit(1)
except json.JSONDecodeError:
    print(f"ERRO CRÍTICO: Arquivo de configuração '{CONFIG_FILE}' contém JSON inválido.")
    exit(1)
except Exception as e:
    print(f"ERRO CRÍTICO: Falha ao carregar '{CONFIG_FILE}': {e}")
    exit(1)

# Validações básicas de configuração
required_keys = ["PRINTER_IP", "ACCESS_CODE", "DEVICE_ID", "CAMERA_URL"]
missing_keys = [key for key in required_keys if key not in config or not config[key]]
if missing_keys:
    print(f"ERRO CRÍTICO: Chaves obrigatórias ausentes ou vazias em '{CONFIG_FILE}': {missing_keys}")
    exit(1)

# --- Usar Valores da Configuração ---
PRINTER_IP = config["PRINTER_IP"]
ACCESS_CODE = config["ACCESS_CODE"]
DEVICE_ID = config["DEVICE_ID"]
CAMERA_URL = config["CAMERA_URL"]
# -----------------------------------

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
    # print(f"Mensagem recebida no tópico {msg.topic}: {msg.payload.decode()}") # Debug (Removido)
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        # Atualiza o status global
        with status_lock:
            # Iterar sobre as chaves do payload (ex: 'print', 'system', 'info')
            for key, value in payload.items():
                if isinstance(value, dict): # Somente processa se o valor for um dicionário
                    if key in printer_status and isinstance(printer_status.get(key), dict):
                        # Se a chave já existe e é um dicionário, mescla o novo conteúdo
                        printer_status[key].update(value)
                    else:
                        # Se a chave não existe ou não era um dicionário, define/sobrescreve
                        printer_status[key] = value
                # Opcional: Lidar com valores que não são dicionários no nível superior, se necessário
                # else:
                #     printer_status[key] = value

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

# --- Rota para Proxy da Câmera ---

@app.route('/camera_proxy')
def camera_proxy():
    """Atua como proxy para o stream MJPEG da câmera da impressora."""
    try:
        # Faz a requisição para a câmera, mantendo o stream aberto
        req = requests.get(CAMERA_URL, stream=True, timeout=10) # Aumentar timeout um pouco
        req.raise_for_status() # Lança erro para respostas HTTP ruins (4xx, 5xx)

        # --- Extração robusta do Boundary ---
        content_type_header = req.headers.get('content-type', '')
        boundary = None
        if 'multipart/x-mixed-replace' not in content_type_header:
            print(f"Erro: Stream da câmera ({CAMERA_URL}) não parece ser MJPEG (multipart/x-mixed-replace). Content-Type: {content_type_header}")
            # Tentar retransmitir mesmo assim pode funcionar em alguns casos, mas idealmente deveria falhar
            # return Response(f"Erro: Stream da câmera não é MJPEG. Tipo: {content_type_header}", status=500)
            # Por ora, vamos tentar passar o content-type original e ver o que acontece
            pass # Deixa passar para o Response abaixo, usando o content_type original
        else:
            # Tenta extrair o boundary do Content-Type
            parts = content_type_header.split('boundary=')
            if len(parts) >= 2:
                boundary = parts[1].strip().strip('"') # Remove espaços e aspas extras
            else:
                print(f"Erro: Boundary não encontrado no cabeçalho Content-Type MJPEG ({CAMERA_URL}). Content-Type: {content_type_header}")
                return Response("Erro: Boundary MJPEG não encontrado no stream da câmera", status=500)
        # -------------------------------------

        # Retransmite o stream MJPEG para o cliente
        # Se o boundary foi encontrado, usa o mimetype formatado.
        # Se não era multipart ou não tinha boundary (e não retornamos erro antes),
        # repassa o content-type original da câmera.
        response_mimetype = content_type_header # Padrão: repassar o content_type original
        if boundary:
            response_mimetype = f'multipart/x-mixed-replace; boundary={boundary}'

        return Response(stream_with_context(req.iter_content(chunk_size=1024)),
                        mimetype=response_mimetype)

    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar à câmera ({CAMERA_URL}): {e}")
        return Response(f"Erro ao conectar à câmera: {e}", status=503) # Service Unavailable
    # Removido KeyError, pois o tratamento agora é mais explícito
    except Exception as e:
        print(f"Erro inesperado no proxy da câmera: {e}")
        return Response("Erro interno no proxy da câmera", status=500)


# --- Inicialização ---

if __name__ == '__main__':
    # Inicia a thread MQTT em background
    mqtt_thread = threading.Thread(target=mqtt_thread_func, daemon=True)
    mqtt_thread.start()

    # Inicia o servidor Flask
    # Use host='0.0.0.0' para torná-lo acessível na sua rede local
    print("Iniciando servidor Flask em http://0.0.0.0:5000")
    # Use debug=False para produção ou para evitar logs excessivos de requisição
    app.run(host='0.0.0.0', port=5000, debug=False) 