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
MQTT_USER = "bblp"
MQTT_PASS = ACCESS_CODE
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
    with status_lock:
        current_status = printer_status.copy()
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
    data = read_maintenance_data()
    return jsonify(data)

@app.route('/update_totals', methods=['POST'])
@login_required # Protege a atualização dos totais
def update_totals():
    """Atualiza os totais de horas e impressões."""
    try:
        req_data = request.get_json()
        if not req_data or 'hours' not in req_data or 'prints' not in req_data:
            return jsonify({"success": False, "error": "Payload inválido (esperado 'hours' e 'prints')."}), 400

        hours = req_data.get('hours')
        prints = req_data.get('prints')

        # Validação simples
        if not isinstance(hours, (int, float)) or hours < 0 or not isinstance(prints, int) or prints < 0:
             return jsonify({"success": False, "error": "Valores inválidos para horas ou impressões."}), 400

        maint_data = read_maintenance_data()
        maint_data['totals']['hours'] = hours
        maint_data['totals']['prints'] = prints
        maint_data['totals']['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if write_maintenance_data(maint_data):
            return jsonify({"success": True, "message": "Totais de manutenção atualizados."})
        else:
            return jsonify({"success": False, "error": "Falha ao salvar os totais."}), 500

    except Exception as e:
        print(f"Erro em /update_totals: {e}", flush=True)
        return jsonify({"success": False, "error": f"Erro interno: {e}"}), 500

@app.route('/log_maintenance', methods=['POST'])
@login_required # Protege o registro de manutenção
def log_maintenance():
    """Registra uma nova entrada de manutenção."""
    try:
        req_data = request.get_json()
        if not req_data or 'task' not in req_data:
             return jsonify({"success": False, "error": "Payload inválido (esperado 'task')."}), 400

        task = req_data.get('task')
        notes = req_data.get('notes', '') # Notas são opcionais

        maint_data = read_maintenance_data()
        current_totals = maint_data.get('totals', {"hours": 0, "prints": 0})

        new_log_entry = {
            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "task": task,
            "hours_at_log": current_totals.get('hours', 0),
            "prints_at_log": current_totals.get('prints', 0),
            "notes": notes
        }

        # Adiciona no início da lista para mostrar mais recentes primeiro
        maint_data['logs'].insert(0, new_log_entry) 

        if write_maintenance_data(maint_data):
            return jsonify({"success": True, "message": "Log de manutenção registrado."})
        else:
            return jsonify({"success": False, "error": "Falha ao salvar o log."}), 500

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

def mqtt_thread_func():
    """Função executada na thread MQTT para lidar com a conexão e loop."""
    # Cria o cliente DENTRO da thread
    local_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
    local_client.on_connect = on_connect
    local_client.on_message = on_message
    local_client.on_disconnect = on_disconnect

    local_client.username_pw_set(MQTT_USER, MQTT_PASS)
    local_client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT, cert_reqs=ssl.CERT_NONE)
    local_client.tls_insecure_set(True)

    print(f"Thread MQTT: Tentando conectar a {PRINTER_IP}:{MQTT_PORT}...", flush=True)
    try:
        # Conecta e entra no loop. on_connect definirá app.mqtt_client
        local_client.connect(PRINTER_IP, MQTT_PORT, 60)
        local_client.loop_forever()
    except Exception as e:
        print(f"Erro fatal na conexão/loop MQTT: {e}", flush=True)
        app.mqtt_client = None # Garante que app.mqtt_client seja None em caso de falha no loop
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

if __name__ == '__main__':
    # Inicia a thread MQTT em background
    mqtt_thread = threading.Thread(target=mqtt_thread_func, daemon=True)
    mqtt_thread.start()

    # Inicia o servidor Flask
    # Use host='0.0.0.0' para torná-lo acessível na sua rede local
    print("Iniciando servidor Flask em http://0.0.0.0:5000")
    # Use debug=False para produção ou para evitar logs excessivos de requisição
    app.run(host='0.0.0.0', port=5000, debug=False) 