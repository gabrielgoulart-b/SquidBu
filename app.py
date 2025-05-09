import paho.mqtt.client as mqtt
import json
import threading
import time
import ssl
import requests
import os
import datetime
from flask import Flask, render_template, jsonify, Response, stream_with_context, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash, check_password_hash
from pywebpush import webpush, WebPushException
import certifi

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

# Validações básicas de configuração (MQTT e Câmera)
required_keys_infra = ["PRINTER_IP", "ACCESS_CODE", "DEVICE_ID", "CAMERA_URL"]
missing_keys_infra = [key for key in required_keys_infra if key not in config or not config[key]]
if missing_keys_infra:
    print(f"ERRO CRÍTICO: Chaves de infraestrutura ausentes ou vazias em '{CONFIG_FILE}': {missing_keys_infra}")
    exit(1)

# Validações básicas de configuração (Login)
required_keys_login = ["SECRET_KEY", "LOGIN_USERNAME", "LOGIN_PASSWORD_HASH"]
missing_keys_login = [key for key in required_keys_login if key not in config or not config[key]]
if missing_keys_login:
     print(f"ERRO CRÍTICO: Chaves de login ausentes ou vazias em '{CONFIG_FILE}': {missing_keys_login}")
     print("Execute o passo de configuração para gerar a SECRET_KEY e o hash da senha.")
     exit(1)

# --- Usar Valores da Configuração ---
PRINTER_IP = config["PRINTER_IP"]
ACCESS_CODE = config["ACCESS_CODE"]
DEVICE_ID = config["DEVICE_ID"]
CAMERA_URL = config["CAMERA_URL"]
SECRET_KEY = config["SECRET_KEY"]
LOGIN_USERNAME = config["LOGIN_USERNAME"]
LOGIN_PASSWORD_HASH = config["LOGIN_PASSWORD_HASH"]
LIVE_SHARE_TOKEN = config.get("LIVE_SHARE_TOKEN")
VAPID_PUBLIC_KEY = config.get("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = config.get("VAPID_PRIVATE_KEY")
VAPID_MAILTO = config.get("VAPID_MAILTO", "mailto:example@example.com")
VAPID_ENABLED = config.get('VAPID_ENABLED', False)
# -----------------------------------

MQTT_PORT = 8883
# Comentando autenticação MQTT - Desabilitado para uso sem autenticação
MQTT_USER = None  # Antes: "bblp"
MQTT_PASS = None  # Antes: ACCESS_CODE
MQTT_CLIENT_ID = f"web_monitor_{int(time.time())}" # ID único do cliente

# Tópicos MQTT
TOPIC_REQUEST = f"device/{DEVICE_ID}/request"
TOPIC_REPORT = f"device/{DEVICE_ID}/report"

# Variável global para armazenar o último estado da impressora
printer_status = {}
status_lock = threading.Lock() # Para acesso seguro à variável entre threads

# Variável global para o sequence_id dos comandos (gerenciado pelo backend)
command_sequence_id = int(time.time()) # Inicializa com timestamp
sequence_lock = threading.Lock()

# Adicionar estas duas linhas
MAINTENANCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'maintenance_data.json')
maintenance_lock = threading.Lock()

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.mqtt_client = None # Atributo para armazenar o cliente MQTT

# --- Configuração Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Rota para redirecionar se o usuário não estiver logado
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info" # Categoria para mensagens flash

# --- Modelo de Usuário Simples ---
class User(UserMixin):
    def __init__(self, id):
        self.id = id # O ID do usuário será o próprio username

    # Método necessário pelo Flask-Login para obter o ID do usuário
    def get_id(self):
        return str(self.id)

# Guarda o único usuário permitido (carregado da config)
# Em uma aplicação real, isso viria de um banco de dados
the_user = User(id=LOGIN_USERNAME)

@login_manager.user_loader
def load_user(user_id):
    """Callback usado pelo Flask-Login para carregar um usuário pelo ID."""
    if user_id == LOGIN_USERNAME:
        return the_user
    return None

# --- Formulário de Login ---
class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(message="Nome de usuário é obrigatório.")])
    password = PasswordField('Senha', validators=[DataRequired(message="Senha é obrigatória.")])
    remember_me = BooleanField('Lembrar-me neste dispositivo')
    submit = SubmitField('Entrar')

# --- Rotas Flask ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Renderiza a página de login e processa o formulário."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        username_input = form.username.data
        password_input = form.password.data

        password_check_result = check_password_hash(LOGIN_PASSWORD_HASH, password_input)

        if username_input == LOGIN_USERNAME and password_check_result:
            login_user(the_user, remember=form.remember_me.data)
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')

    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout():
    """Desloga o usuário."""
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Renderiza a página HTML principal."""
    # Passa a chave pública VAPID e o token de compartilhamento para o template
    return render_template('index.html', 
                           vapid_public_key=VAPID_PUBLIC_KEY if VAPID_ENABLED else None, 
                           live_share_token=LIVE_SHARE_TOKEN)

@app.route('/status')
# @login_required # REMOVIDO - Acesso permitido para a página /live
def get_status():
    """Retorna o último status conhecido da impressora em formato JSON."""
    from db_manager import SensorManager
    
    with status_lock:
        current_status = printer_status.copy()
    
    # Adiciona os dados dos sensores ESP32 às bandejas do AMS
    try:
        # Busca os dados mais recentes dos sensores para cada caixa do ESP32
        esp32_data = {}
        for box_num in range(1, 5):  # Caixas de 1 a 4
            source = f"ESP32_Box{box_num}"
            
            # Obter entradas separadas para temperatura, umidade e peso restante
            # e usar a mais recente de cada uma
            temp_data = SensorManager.get_recent_sensor_data(source=source, limit=5)
            latest_temp = None
            latest_humidity = None
            latest_remaining = None
            
            # Processar os dados encontrando os valores mais recentes
            for data in temp_data:
                if data.temperature is not None and latest_temp is None:
                    latest_temp = data.temperature
                if data.humidity is not None and latest_humidity is None:
                    latest_humidity = data.humidity
                if data.ams_filament_remaining is not None and latest_remaining is None:
                    latest_remaining = data.ams_filament_remaining
                
                # Se encontrou todos os valores, podemos parar
                if latest_temp is not None and latest_humidity is not None and latest_remaining is not None:
                    break
            
            # Dados válidos apenas se todos os valores necessários existirem
            if latest_temp is not None or latest_humidity is not None or latest_remaining is not None:
                esp32_data[box_num-1] = {
                    'temperature': latest_temp,
                    'humidity': latest_humidity,
                    'remaining_g': latest_remaining
                }
        
        # Adiciona esses dados aos objetos de bandeja do AMS
        if 'print' in current_status:
            # Para AMS Lite (A1 Mini)
            if 'stg' in current_status['print'] and current_status['print']['stg']:
                for tray in current_status['print']['stg']:
                    if 'id' in tray:
                        # Converte id para inteiro para garantir compatibilidade
                        tray_id = int(tray['id']) if not isinstance(tray['id'], int) else tray['id']
                        if tray_id in esp32_data:
                            tray['dht_temp'] = esp32_data[tray_id]['temperature']
                            tray['dht_humidity'] = esp32_data[tray_id]['humidity']
                            
                            # Garante que remaining_g seja prioritário e substitua remain
                            if esp32_data[tray_id]['remaining_g'] is not None:
                                tray['remaining_g'] = esp32_data[tray_id]['remaining_g']
                                # Sobrescreve 'remain' para garantir que o frontend use remaining_g
                                if 'remain' in tray:
                                    # Se o remain existe, converte o remaining_g para porcentagem para manter consistência
                                    filament_max = 1000.0  # Valor padrão em gramas para um carretel completo
                                    remain_percent = min(100, max(0, (esp32_data[tray_id]['remaining_g'] / filament_max) * 100))
                                    tray['remain'] = remain_percent
            
            # Para AMS padrão (X1/P1)
            if 'ams' in current_status['print'] and current_status['print']['ams'] and 'ams' in current_status['print']['ams']:
                for unit in current_status['print']['ams']['ams']:
                    if 'tray' in unit:
                        for tray in unit['tray']:
                            if 'id' in tray:
                                # Converte id para inteiro para garantir compatibilidade
                                tray_id = int(tray['id']) if not isinstance(tray['id'], int) else tray['id']
                                if tray_id in esp32_data:
                                    tray['dht_temp'] = esp32_data[tray_id]['temperature']
                                    tray['dht_humidity'] = esp32_data[tray_id]['humidity']
                                    
                                    # Garante que remaining_g seja prioritário e substitua remain
                                    if esp32_data[tray_id]['remaining_g'] is not None:
                                        tray['remaining_g'] = esp32_data[tray_id]['remaining_g']
                                        # Sobrescreve 'remain' para garantir que o frontend use remaining_g
                                        if 'remain' in tray:
                                            # Se o remain existe, converte o remaining_g para porcentagem para manter consistência
                                            filament_max = 1000.0  # Valor padrão em gramas para um carretel completo
                                            remain_percent = min(100, max(0, (esp32_data[tray_id]['remaining_g'] / filament_max) * 100))
                                            tray['remain'] = remain_percent
    except Exception as e:
        print(f"Erro ao adicionar dados do ESP32 ao status: {e}", flush=True)
    
    return jsonify(current_status)

# --- Rota para Enviar Comandos MQTT ---
@app.route('/command', methods=['POST'])
@login_required # Protege o envio de comandos
def handle_command():
    """Recebe um comando para ser enviado à impressora."""
    # Log detalhado da requisição recebida
    print(f"--- Nova Requisição /command ---", flush=True)
    print(f"Content-Type: {request.content_type}", flush=True)
    print(f"Dados Brutos Recebidos: {request.data}", flush=True)
    # Tentar obter JSON silenciosamente para debug
    data = request.get_json(silent=True)
    print(f"Dados JSON Parseados (ou None): {data}", flush=True)
    # -------------------------------------

    if not app.mqtt_client:
        print("Erro: Cliente MQTT não conectado.", flush=True) # Log adicionado
        return jsonify({"success": False, "error": "Cliente MQTT não conectado."}), 503

    try:
        if not data or 'command' not in data:
            print(f"Erro: Payload JSON inválido ou comando ausente. Dados recebidos: {data}", flush=True) # Log adicionado
            return jsonify({"success": False, "error": "Payload inválido ou comando ausente."}), 400

        command = data.get('command')
        sequence_id = get_next_sequence_id()  # Usar a função que gera sequence_id incremental
        payload_to_send = None

        # Construir payload com base no comando
        if command == 'gcode':
            gcode_line = data.get('line')
            if not gcode_line:
                 print(f"Erro: Linha G-code ausente.", flush=True)
                 return jsonify({"success": False, "error": "Linha G-code ausente."}), 400
            payload_to_send = {
                "print": {
                    "sequence_id": sequence_id,
                    "command": "gcode_line",
                    "param": gcode_line
                }
            }
        elif command == 'pause':
            payload_to_send = {
                "print": {
                    "sequence_id": sequence_id,
                    "command": "pause"
                }
            }
        elif command == 'resume':
            payload_to_send = {
                "print": {
                    "sequence_id": sequence_id,
                    "command": "resume"
                }
            }
        elif command == 'stop':
            payload_to_send = {
                "print": {
                    "sequence_id": sequence_id,
                    "command": "stop"
                }
            }
        elif command == 'print_speed':
            value = data.get('value')
            if value not in ['1', '2', '3', '4']:
                return jsonify({"success": False, "error": "Valor de velocidade inválido. Use '1', '2', '3' ou '4'."}), 400
            payload_to_send = {
                "print": {
                    "sequence_id": sequence_id,
                    "command": "print_speed",
                    "param": value
                }
            }
        elif command == 'set_chamber_light':
            mode = data.get('mode') # Espera 'on' ou 'off'
            if mode not in ['on', 'off']:
                 return jsonify({"success": False, "error": "Modo inválido para luz da câmara ('on' ou 'off')."}), 400
            payload_to_send = {
                "system": {
                    "sequence_id": sequence_id,
                    "command": "ledctrl",
                    "led_node": "chamber_light",
                    "led_mode": mode,
                    "led_on_time": 500, # Valores padrão, não usados para on/off
                    "led_off_time": 500,
                    "loop_times": 1,
                    "interval_time": 1000
                }
            }
        elif command == 'set_work_light':
            mode = data.get('mode') # Espera 'on', 'off', ou 'flashing'
            if mode not in ['on', 'off', 'flashing']:
                 return jsonify({"success": False, "error": "Modo inválido para luz de trabalho ('on', 'off', 'flashing')."}), 400
            payload_to_send = {
                "system": {
                    "sequence_id": sequence_id,
                    "command": "ledctrl",
                    "led_node": "work_light",
                    "led_mode": mode,
                    # Valores padrão, podem ser ajustados se 'flashing' for usado com parâmetros específicos
                    "led_on_time": 500,
                    "led_off_time": 500,
                    "loop_times": 3 if mode == 'flashing' else 1, # Pisca 3 vezes como exemplo
                    "interval_time": 1000
                }
            }
        elif command == 'set_part_fan':
            value = data.get('value') # Espera 0-100 da UI
            
            # --- LÓGICA CORRIGIDA --- 
            # Valida se o input é um número entre 0 e 100
            if value is None or not isinstance(value, (int, float)) or not (0 <= value <= 100):
                print(f"Erro: Velocidade do fan inválida (value={value}). Esperado 0-100%.", flush=True)
                return jsonify({"success": False, "error": "Velocidade da ventoinha inválida (0-100%)."}), 400
            
            # Converte o valor percentual (0-100) para G-code (0-255)
            gcode_value = int(round(value * 2.55))
            # --- FIM CORREÇÃO ---
            
            payload_to_send = {
                "print": {
                    "sequence_id": sequence_id,
                    "command": "gcode_line",
                    "param": f"M106 P1 S{gcode_value}" # Fan de peça é P1
                }
            }
        else:
            print(f"Erro: Comando desconhecido recebido: {command}", flush=True)
            return jsonify({"success": False, "error": f"Comando desconhecido: {command}"}), 400

        # Publicar o comando MQTT
        if payload_to_send:
            payload_json = json.dumps(payload_to_send)
            print(f"Enviando comando '{command}' para {TOPIC_REQUEST}: {payload_json}", flush=True)
            result, mid = app.mqtt_client.publish(TOPIC_REQUEST, payload_json, qos=1)

            if result == mqtt.MQTT_ERR_SUCCESS:
                print(f"Comando {command} (seq: {sequence_id}) publicado com sucesso (MID: {mid}).", flush=True)
                return jsonify({"success": True, "message": f"Comando '{command}' enviado.", "sequence_id": sequence_id})
            else:
                print(f"Falha ao publicar comando {command} (seq: {sequence_id}), erro MQTT: {result}", flush=True)
                return jsonify({"success": False, "error": f"Falha ao enviar comando MQTT (erro {result})."}), 500
        else:
             # Este caso não deveria ocorrer se a lógica acima estiver correta
             print(f"Erro interno: Nenhum payload foi definido para o comando '{command}'", flush=True)
             return jsonify({"success": False, "error": "Erro interno ao processar comando."}), 500

    except Exception as e:
        print(f"Erro na rota /command: {e}", flush=True)
        return jsonify({"success": False, "error": f"Erro interno do servidor: {e}"}), 500

# --- Rota para Proxy da Câmera ---
@app.route('/camera_proxy')
# @login_required # REMOVIDO - Acesso permitido para a página /live
def camera_proxy():
    """Atua como um proxy para o stream da câmera, evitando problemas de CORS/Mixed Content."""
    try:
        # Faz a requisição para a câmera, mantendo o stream aberto
        req = requests.get(CAMERA_URL, stream=True, timeout=10) # Aumentar timeout um pouco
        req.raise_for_status() # Lança erro para respostas HTTP ruins (4xx, 5xx)

        # --- Extração robusta do Boundary ---
        content_type_header = req.headers.get('content-type', '')
        boundary = None
        if 'multipart/x-mixed-replace' not in content_type_header:
            print(f"Erro: Stream da câmera ({CAMERA_URL}) não parece ser MJPEG (multipart/x-mixed-replace). Content-Type: {content_type_header}", flush=True)
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
                print(f"Erro: Boundary não encontrado no cabeçalho Content-Type MJPEG ({CAMERA_URL}). Content-Type: {content_type_header}", flush=True)
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
        print(f"Erro ao conectar à câmera ({CAMERA_URL}): {e}", flush=True)
        return Response(f"Erro ao conectar à câmera: {e}", status=503) # Service Unavailable
    # Removido KeyError, pois o tratamento agora é mais explícito
    except Exception as e:
        print(f"Erro inesperado no proxy da câmera: {e}", flush=True)
        return Response("Erro interno no proxy da câmera", status=500)

# --- Rotas Flask de Manutenção ---

@app.route('/maintenance_data')
@login_required # Protege o acesso aos dados de manutenção
def get_maintenance_data():
    """Retorna os dados de manutenção atuais."""
    try:
        from db_manager import MaintenanceManager, StatsManager, UserManager
        
        # Obter as estatísticas da impressora
        app.logger.info("Obtendo estatísticas da impressora")
        stats = StatsManager.get_printer_stats()
        
        if not stats:
            app.logger.warning("Nenhuma estatística encontrada, criando estatísticas iniciais")
            # Criar estatísticas iniciais se não existirem
            StatsManager.update_printer_stats(hours=0, prints=0, power_on_hours=0)
            stats = StatsManager.get_printer_stats()
        
        # Obter os logs de manutenção
        app.logger.info("Obtendo logs de manutenção")
        logs = MaintenanceManager.get_maintenance_logs()
        
        # Formatar os dados no formato esperado pelo frontend
        logs_formatted = []
        for log in logs:
            # Buscar o nome do usuário se houver um user_id
            username = None
            if log.user_id:
                user = UserManager.get_user_by_id(log.user_id)
                username = user.username if user else None
                
            logs_formatted.append({
                "timestamp": log.performed_at.strftime('%Y-%m-%d %H:%M:%S'),
                "task": log.task,
                "hours_at_log": log.hours_at_log,
                "prints_at_log": log.prints_at_log,
                "user": username or "Sistema",
                "notes": log.notes or ""
            })
        
        # Criar o objeto de resposta
        response_data = {
            "totals": {
                "hours": stats.total_print_hours if stats else 0,
                "prints": stats.total_prints if stats else 0,
                "power_on_hours": stats.power_on_hours if stats else 0,
                "last_updated": stats.last_updated.strftime('%Y-%m-%d %H:%M:%S') if stats and stats.last_updated else None
            },
            "logs": logs_formatted
        }
        
        app.logger.info(f"Retornando dados de manutenção: estatísticas e {len(logs_formatted)} logs")
        return jsonify(response_data)
    except Exception as e:
        app.logger.error(f"Erro ao obter dados de manutenção: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"Erro ao obter dados: {str(e)}"}), 500

@app.route('/force_stats_update', methods=['POST'])
@login_required # Protege o acesso à atualização forçada
def force_stats_update():
    """Força uma atualização imediata das estatísticas da impressora."""
    try:
        app.logger.info("Solicitação para forçar atualização de estatísticas recebida")
        
        # Verificar se temos uma instância MQTT ativa
        if not hasattr(app, 'mqtt_integration') or not app.mqtt_integration:
            app.logger.error("Integração MQTT não disponível")
            return jsonify({"success": False, "error": "Integração MQTT não disponível"}), 500
        
        # Solicitar atualização
        success = app.mqtt_integration.force_stats_update()
        if success:
            app.logger.info("Solicitação de atualização de estatísticas enviada com sucesso")
            return jsonify({
                "success": True, 
                "message": "Solicitação de atualização enviada. Aguarde alguns segundos para que os dados sejam atualizados."
            })
        else:
            app.logger.warning("Falha ao solicitar atualização de estatísticas")
            return jsonify({"success": False, "error": "Falha ao solicitar atualização de estatísticas"}), 500
            
    except Exception as e:
        app.logger.error(f"Erro ao forçar atualização de estatísticas: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"Erro: {str(e)}"}), 500

@app.route('/log_maintenance', methods=['POST'])
@login_required # Protege o registro de manutenção
def log_maintenance():
    """Registra uma nova entrada de manutenção."""
    try:
        from db_manager import MaintenanceManager
        from flask_login import current_user
        
        req_data = request.get_json()
        if not req_data or 'task' not in req_data:
             return jsonify({"success": False, "error": "Payload inválido (esperado 'task')."}), 400

        task = req_data.get('task')
        notes = req_data.get('notes', '') # Notas são opcionais
        
        # Adicionar log de manutenção no banco de dados
        user_id = current_user.id if current_user.is_authenticated else None
        log = MaintenanceManager.add_maintenance_log(
            task=task,
            notes=notes,
            user_id=user_id
        )
        
        if log:
            return jsonify({"success": True, "message": "Log de manutenção registrado."})
        else:
            return jsonify({"success": False, "error": "Falha ao salvar o log no banco de dados."}), 500

    except Exception as e:
        print(f"Erro em /log_maintenance: {e}", flush=True)
        return jsonify({"success": False, "error": f"Erro interno: {e}"}), 500

# --- NOVA Rota para Visualização Compartilhada ---
@app.route('/live/<string:token>')
def live_view(token):
    """Exibe uma visualização simplificada se o token for válido."""
    if not LIVE_SHARE_TOKEN:
        print("AVISO: Tentativa de acesso a /live/ sem LIVE_SHARE_TOKEN configurado.", flush=True)
        return "Recurso não configurado.", 404

    if token == LIVE_SHARE_TOKEN:
        # Token válido, renderiza o template simplificado
        return render_template('live_view.html')
    else:
        # Token inválido
        print(f"AVISO: Tentativa de acesso a /live/ com token inválido: {token}", flush=True)
        return "Acesso não autorizado.", 403
# --- Fim da Nova Rota ---

# --- Armazenamento de Assinaturas Push ---
SUBSCRIPTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'subscriptions.json')
subscriptions_lock = threading.Lock()

def load_subscriptions():
    with subscriptions_lock:
        try:
            if os.path.exists(SUBSCRIPTIONS_FILE):
                with open(SUBSCRIPTIONS_FILE, 'r') as f:
                    # Carrega como lista de {endpoint: subscription_info}
                    # Usamos endpoint como chave para fácil remoção/atualização
                    # O valor pode ser o objeto subscription completo
                    subs_dict = json.load(f)
                    # Validar minimamente se é um dicionário
                    return subs_dict if isinstance(subs_dict, dict) else {}
            else:
                return {}
        except (IOError, json.JSONDecodeError) as e:
            print(f"Erro ao ler {SUBSCRIPTIONS_FILE}: {e}", flush=True)
            return {}

def save_subscriptions(subscriptions):
    with subscriptions_lock:
        try:
            with open(SUBSCRIPTIONS_FILE, 'w') as f:
                json.dump(subscriptions, f, indent=4)
        except IOError as e:
            print(f"Erro ao escrever {SUBSCRIPTIONS_FILE}: {e}", flush=True)

# Carrega assinaturas na inicialização
push_subscriptions = load_subscriptions()

# --- Variáveis de Estado para Detecção de Eventos ---
last_print_status = None # Armazena o estado anterior da impressão
status_lock = threading.Lock() # Reutiliza o lock existente

# --- Função para Enviar Notificações Push ---
def send_push_notification(title, body, icon=None, badge=None, data=None):
    if not VAPID_ENABLED:
        # print("Debug: VAPID desabilitado, não enviando push.", flush=True)
        return

    print(f"Preparando para enviar notificação: {title} - {body}", flush=True)
    notification_payload = json.dumps({
        "title": title,
        "body": body,
        "icon": icon or '/static/icons/android-chrome-192x192.png',
        "badge": badge or '/static/icons/favicon-96x96.png',
        "data": data or {"url": "/"} # URL padrão para abrir ao clicar
    })

    vapid_claims = {
        "sub": VAPID_MAILTO
    }

    subs_to_remove = []
    with subscriptions_lock:
        current_subs = push_subscriptions.copy() # Trabalha com uma cópia

    if not current_subs:
        print("Nenhuma assinatura push encontrada para enviar notificação.", flush=True)
        return

    print(f"Enviando para {len(current_subs)} assinaturas...", flush=True)
    for endpoint, sub_info in current_subs.items():
        try:
            # Verifica se sub_info é um dicionário válido com 'endpoint'
            if isinstance(sub_info, dict) and 'endpoint' in sub_info:
                webpush(
                    subscription_info=sub_info,
                    data=notification_payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims
                )
                # print(f"Notificação enviada para: {sub_info.get('endpoint')[:30]}...", flush=True)
            else:
                 print(f"AVISO: Assinatura inválida encontrada para endpoint {endpoint}, pulando.", flush=True)
                 subs_to_remove.append(endpoint) # Marcar para remoção se a estrutura estiver errada

        except WebPushException as ex:
            print(f"Erro ao enviar WebPush para {sub_info.get('endpoint', 'Desconhecido')[:30]}...: {ex}", flush=True)
            # Se a assinatura expirou ou é inválida (ex: 404, 410 Gone), marca para remover
            if ex.response and ex.response.status_code in [404, 410]:
                print(f"Marcando assinatura {endpoint} para remoção.", flush=True)
                subs_to_remove.append(endpoint)
        except Exception as e:
             print(f"Erro inesperado ao enviar WebPush para {sub_info.get('endpoint', 'Desconhecido')[:30]}...: {e}", flush=True)

    # Remove assinaturas inválidas/expiradas
    if subs_to_remove:
        print(f"Removendo {len(subs_to_remove)} assinaturas inválidas...", flush=True)
        with subscriptions_lock:
            for endpoint in subs_to_remove:
                push_subscriptions.pop(endpoint, None)
            save_subscriptions(push_subscriptions) # Salva o dicionário atualizado

# --- Callback MQTT Modificado para Detecção de Eventos ---
def on_message(client, userdata, msg):
    """Callback executado quando uma mensagem é recebida."""
    global printer_status, last_print_status
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        new_status_data = {} # Acumula dados recebidos nesta mensagem
        if isinstance(payload.get('print'), dict):
             new_status_data.update(payload['print'])
        # Adicione outros top-level keys se necessário (ex: 'system')
        # if isinstance(payload.get('system'), dict):
        #     new_status_data.update(payload['system'])

        with status_lock:
            # Atualiza o estado global
            for key, value in payload.items():
                if isinstance(value, dict):
                    if key in printer_status and isinstance(printer_status.get(key), dict):
                        printer_status[key].update(value)
                    else:
                        printer_status[key] = value
                # else: # Considerar atualizar chaves não-dicionário também? 
                #     printer_status[key] = value

            # Lógica de Detecção de Eventos de Impressão
            current_print_info = printer_status.get('print', {})
            current_mc_status = current_print_info.get('mc_print_stage')
            current_gcode_file = current_print_info.get('gcode_file', '')
            current_result = current_print_info.get('mc_print_result')

            previous_mc_status = last_print_status.get('mc_print_stage') if last_print_status else None
            previous_gcode_file = last_print_status.get('gcode_file', '') if last_print_status else ''

            # Evento: Impressão Iniciada
            if current_mc_status == 'PRINTING' and previous_mc_status != 'PRINTING':
                 if current_gcode_file:
                    filename = os.path.basename(current_gcode_file)
                    send_push_notification("Impressão Iniciada!", f"Arquivo: {filename}")
                 else:
                     send_push_notification("Impressão Iniciada!", "Um novo trabalho começou.")

            # Evento: Impressão Concluída/Falhou/Parou
            if previous_mc_status == 'PRINTING' and current_mc_status != 'PRINTING':
                 filename = os.path.basename(previous_gcode_file) if previous_gcode_file else "Trabalho anterior"
                 if current_result == 0: # Sucesso (código 0 geralmente indica sucesso)
                     send_push_notification("Impressão Concluída! ✅", f"Arquivo: {filename}")
                 elif current_result == 4: # Parada pelo usuário (comum para cancelamento)
                      send_push_notification("Impressão Parada ⏹️", f"Arquivo: {filename}")
                 else: # Outros resultados podem ser erros
                     error_code = current_result or "Desconhecido"
                     send_push_notification("Erro na Impressão! ❌", f"Arquivo: {filename}\nResultado/Erro: {error_code}")

            # Atualiza o último estado conhecido para a próxima comparação
            last_print_status = current_print_info.copy()

    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON: {msg.payload.decode()}", flush=True)
    except Exception as e:
        print(f"Erro ao processar mensagem MQTT ou enviar push: {e}", flush=True)

# --- Rotas Flask ---

# --- NOVA Rota para Salvar Assinaturas Push ---
@app.route('/save_subscription', methods=['POST'])
@login_required # Apenas usuários logados podem registrar notificações
def save_subscription():
    """Recebe e salva a assinatura push enviada pelo frontend."""
    if not VAPID_ENABLED:
        return jsonify({"success": False, "error": "Push notifications not enabled on server."}), 501

    subscription_data = request.json

    if not subscription_data:
        # Pode ser um pedido de cancelamento (frontend envia null)
        # Ou erro
        print("Recebido pedido para remover assinatura (payload null/vazio).", flush=True)
        # Idealmente, o frontend enviaria o endpoint a ser removido
        # Por enquanto, não fazemos nada se for null, o cancelamento é local
        # Se quiséssemos remover do backend, precisaríamos do endpoint.
        return jsonify({"success": True, "message": "Subscription removal request noted (no action taken server-side for null)."})

    # Validação mínima da assinatura recebida
    if not isinstance(subscription_data, dict) or 'endpoint' not in subscription_data:
        print(f"Erro: Dados de assinatura inválidos recebidos: {subscription_data}", flush=True)
        return jsonify({"success": False, "error": "Invalid subscription object"}), 400

    endpoint = subscription_data['endpoint']
    print(f"Recebida assinatura para endpoint: {endpoint[:50]}...", flush=True)

    with subscriptions_lock:
        push_subscriptions[endpoint] = subscription_data # Salva/Atualiza usando endpoint como chave
        save_subscriptions(push_subscriptions) # Salva no arquivo

    return jsonify({"success": True})

# --- Fim da Nova Rota ---

# --- Funções MQTT ---

def get_next_sequence_id():
    """Obtém o próximo sequence_id de forma thread-safe."""
    global command_sequence_id
    with sequence_lock:
        command_sequence_id += 1
        return str(command_sequence_id) # MQTT espera string

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback executado quando o cliente se conecta ao broker MQTT."""
    if rc == 0:
        print("Conectado ao Broker MQTT da Impressora com sucesso!", flush=True)
        # Armazena o cliente na aplicação Flask para uso posterior
        app.mqtt_client = client
        client.subscribe(TOPIC_REPORT)
        print(f"Inscrito no tópico: {TOPIC_REPORT}", flush=True)
        request_full_status(client)
    else:
        print(f"Falha na conexão MQTT, código de retorno: {rc}", flush=True)
        app.mqtt_client = None # Garante que não usemos um cliente inválido

def on_disconnect(client, userdata, rc, properties=None):
    """Callback executado quando o cliente se desconecta."""
    print(f"Desconectado do Broker MQTT (código: {rc}). Tentando reconectar...", flush=True)
    app.mqtt_client = None # Cliente não está mais conectado

def on_message(client, userdata, msg):
    """Callback executado quando uma mensagem é recebida."""
    global printer_status, last_print_status
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        new_status_data = {} # Acumula dados recebidos nesta mensagem
        if isinstance(payload.get('print'), dict):
             new_status_data.update(payload['print'])
        # Adicione outros top-level keys se necessário (ex: 'system')
        # if isinstance(payload.get('system'), dict):
        #     new_status_data.update(payload['system'])

        with status_lock:
            # Atualiza o estado global
            for key, value in payload.items():
                if isinstance(value, dict):
                    if key in printer_status and isinstance(printer_status.get(key), dict):
                        printer_status[key].update(value)
                    else:
                        printer_status[key] = value
                # else: # Considerar atualizar chaves não-dicionário também? 
                #     printer_status[key] = value

            # Lógica de Detecção de Eventos de Impressão
            current_print_info = printer_status.get('print', {})
            current_mc_status = current_print_info.get('mc_print_stage')
            current_gcode_file = current_print_info.get('gcode_file', '')
            current_result = current_print_info.get('mc_print_result')

            previous_mc_status = last_print_status.get('mc_print_stage') if last_print_status else None
            previous_gcode_file = last_print_status.get('gcode_file', '') if last_print_status else ''

            # Evento: Impressão Iniciada
            if current_mc_status == 'PRINTING' and previous_mc_status != 'PRINTING':
                 if current_gcode_file:
                    filename = os.path.basename(current_gcode_file)
                    send_push_notification("Impressão Iniciada!", f"Arquivo: {filename}")
                 else:
                     send_push_notification("Impressão Iniciada!", "Um novo trabalho começou.")

            # Evento: Impressão Concluída/Falhou/Parou
            if previous_mc_status == 'PRINTING' and current_mc_status != 'PRINTING':
                 filename = os.path.basename(previous_gcode_file) if previous_gcode_file else "Trabalho anterior"
                 if current_result == 0: # Sucesso (código 0 geralmente indica sucesso)
                     send_push_notification("Impressão Concluída! ✅", f"Arquivo: {filename}")
                 elif current_result == 4: # Parada pelo usuário (comum para cancelamento)
                      send_push_notification("Impressão Parada ⏹️", f"Arquivo: {filename}")
                 else: # Outros resultados podem ser erros
                     error_code = current_result or "Desconhecido"
                     send_push_notification("Erro na Impressão! ❌", f"Arquivo: {filename}\nResultado/Erro: {error_code}")

            # Atualiza o último estado conhecido para a próxima comparação
            last_print_status = current_print_info.copy()

    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON: {msg.payload.decode()}", flush=True)
    except Exception as e:
        print(f"Erro ao processar mensagem MQTT ou enviar push: {e}", flush=True)

def request_full_status(client):
    """Envia uma solicitação para obter o status completo da impressora."""
    sequence_id = get_next_sequence_id()
    request_payload = {
        "pushing": {
            "sequence_id": sequence_id,
            "command": "pushall"
        }
    }
    payload_json = json.dumps(request_payload)
    print(f"Enviando solicitação 'pushall' (seq: {sequence_id}) para {TOPIC_REQUEST}", flush=True)
    result = client.publish(TOPIC_REQUEST, payload_json)
    # print(f"Publish result: {result}") # Debug opcional
    
    # Solicitar informações da impressora
    request_printer_info(client)

def request_printer_info(client):
    """Envia uma solicitação para obter informações da impressora, incluindo estatísticas."""
    sequence_id = get_next_sequence_id()
    request_payload = {
        "info": {
            "sequence_id": sequence_id,
            "command": "get_version"
        }
    }
    payload_json = json.dumps(request_payload)
    print(f"Enviando solicitação 'get_version' (seq: {sequence_id}) para {TOPIC_REQUEST}", flush=True)
    result = client.publish(TOPIC_REQUEST, payload_json)
    
    # Também podemos tentar obter outros tipos de informações que a impressora forneça
    # Este é apenas um exemplo, pode ser expandido conforme necessário
    sequence_id = get_next_sequence_id()
    request_payload = {
        "system": {
            "sequence_id": sequence_id,
            "command": "get_printer_info"
        }
    }
    payload_json = json.dumps(request_payload)
    print(f"Enviando solicitação 'get_printer_info' (seq: {sequence_id}) para {TOPIC_REQUEST}", flush=True)
    client.publish(TOPIC_REQUEST, payload_json)

def mqtt_thread_func():
    """Função que executa em uma thread separada para gerenciar conexão MQTT."""
    print("Thread MQTT iniciada", flush=True)
    
    # Pequeno atraso para garantir que o aplicativo esteja totalmente inicializado
    time.sleep(2)
    
    # TLS é necessário para a Bambu Lab
    try:
        # Criar cliente MQTT local
        local_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
        
        # Configurar callbacks
        local_client.on_connect = on_connect
        local_client.on_disconnect = on_disconnect
        local_client.on_message = on_message
        
        # TLS é necessário para a Bambu Lab
        try:
            local_client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT, cert_reqs=ssl.CERT_NONE)
            local_client.tls_insecure_set(True)
            print(f"Conectando ao broker MQTT: {PRINTER_IP}:{MQTT_PORT}", flush=True)
            local_client.connect(PRINTER_IP, MQTT_PORT, 60)
        except Exception as e:
            print(f"Erro ao conectar ao broker MQTT: {e}", flush=True)
            print("Thread MQTT terminando.", flush=True)
            return
    except Exception as e:
        print(f"Erro ao iniciar thread MQTT: {e}", flush=True)
        print("Thread MQTT terminando.", flush=True)
        return

    # Loop MQTT
    try:
        local_client.loop_forever()
    except Exception as e:
        print(f"Erro no loop MQTT: {e}", flush=True)
    finally:
        print("Thread MQTT terminando.", flush=True)
        app.mqtt_client = None # Garante limpeza ao sair do loop

# --- Funções de Manutenção ---

def read_maintenance_data():
    """Lê os dados de manutenção do arquivo JSON de forma segura."""
    with maintenance_lock:
        try:
            if not os.path.exists(MAINTENANCE_FILE):
                # Cria arquivo padrão se não existir
                default_data = {"totals": {"hours": 0, "prints": 0, "last_updated": None}, "logs": []}
                with open(MAINTENANCE_FILE, 'w') as f:
                    json.dump(default_data, f, indent=4)
                return default_data
            else:
                with open(MAINTENANCE_FILE, 'r') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Erro ao ler/criar {MAINTENANCE_FILE}: {e}", flush=True)
            # Retorna padrão em caso de erro grave
            return {"totals": {"hours": 0, "prints": 0, "last_updated": None}, "logs": []}

def write_maintenance_data(data):
    """Escreve os dados de manutenção no arquivo JSON de forma segura."""
    with maintenance_lock:
        try:
            with open(MAINTENANCE_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except IOError as e:
            print(f"Erro ao escrever {MAINTENANCE_FILE}: {e}", flush=True)
            return False

# --- Inicialização ---

# Inicializar a integração MQTT para atualização de estatísticas
try:
    from mqtt_integration import MQTTIntegration
    
    # Função de callback para atualizar o printer_status
    def update_printer_status(data):
        """
        Atualiza o printer_status com os dados recebidos
        
        Args:
            data (dict): Dados a serem atualizados no printer_status
        """
        global printer_status
        with status_lock:
            for key, value in data.items():
                if isinstance(value, dict):
                    if key in printer_status and isinstance(printer_status.get(key), dict):
                        printer_status[key].update(value)
                    else:
                        printer_status[key] = value
                else:
                    printer_status[key] = value
    
    app.mqtt_integration = MQTTIntegration({
        'PRINTER_IP': PRINTER_IP,
        'ACCESS_CODE': ACCESS_CODE,
        'DEVICE_ID': DEVICE_ID
    })
    
    # Configura o callback
    app.mqtt_integration.set_update_callback(update_printer_status)
    
    print("Integração MQTT para estatísticas inicializada", flush=True)
except Exception as e:
    print(f"Erro ao inicializar integração MQTT para estatísticas: {e}", flush=True)
    app.mqtt_integration = None

if __name__ == '__main__':
    # Inicia a thread MQTT em background
    mqtt_thread = threading.Thread(target=mqtt_thread_func, daemon=True)
    mqtt_thread.start()

    # Inicia o servidor Flask
    # Use host='0.0.0.0' para torná-lo acessível na sua rede local
    print("Iniciando servidor Flask em http://0.0.0.0:5000", flush=True)
    # Use debug=False para produção ou para evitar logs excessivos de requisição
    app.run(host='0.0.0.0', port=5000, debug=False) 