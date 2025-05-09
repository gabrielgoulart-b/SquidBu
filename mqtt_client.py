#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import logging
from datetime import datetime
import threading
import paho.mqtt.client as mqtt

from db_manager import SensorManager

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mqtt_client')

class MQTTClient:
    """
    Cliente MQTT para se comunicar com sensores ESP32 e outros dispositivos
    """
    
    def __init__(self, host='localhost', port=1883, username=None, password=None):
        """
        Inicializa o cliente MQTT
        
        Args:
            host (str): Endereço do servidor MQTT
            port (int): Porta do servidor MQTT
            username (str, optional): Nome de usuário para autenticação
            password (str, optional): Senha para autenticação
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # Configurar autenticação se fornecida
        if username and password:
            logger.info("Autenticação MQTT configurada")
            self.client.username_pw_set(username, password)
        else:
            logger.info("Autenticação MQTT desabilitada - conexão anônima")
            
        # Flag para controlar o loop de conexão
        self.running = False
        self.connected = False
        
        # Tópicos padrão para subscrever
        self.topics = [
            "filament/box/+/temperature",
            "filament/box/+/humidity",
            "filament/box/+/usage_mm",
            "filament/box/+/remaining_g",
            "filament/box/+/remaining_percent",
            # Adicionando tópicos compatíveis com o ESP32
            "filament_monitor/temperature/+",
            "filament_monitor/humidity/+",
            "filament_monitor/usage/+",
            "filament_monitor/remaining_weight/+",
            "filament_monitor/remaining_percentage/+",
            "filament_monitor/density/+",
            "filament_monitor/weight/+",
            "filament_monitor/status",
            "filament_monitor/system/#"
        ]
        
        # Últimos dados recebidos
        self.last_data = {}
        self.last_data_time = {}
        
        # Thread para o loop MQTT
        self.thread = None
    
    def start(self):
        """
        Inicia o cliente MQTT e a thread do loop
        
        Returns:
            bool: True se iniciado com sucesso
        """
        try:
            self.running = True
            logger.info(f"Conectando ao servidor MQTT em {self.host}:{self.port}")
            self.client.connect_async(self.host, self.port, 60)
            
            # Iniciar o loop em uma thread separada
            self.thread = threading.Thread(target=self._run_loop)
            self.thread.daemon = True
            self.thread.start()
            
            # Esperar pela conexão (com timeout)
            timeout = 10  # segundos
            start_time = time.time()
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                logger.warning("Timeout ao conectar ao servidor MQTT")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Erro ao iniciar cliente MQTT: {str(e)}")
            self.running = False
            return False
    
    def stop(self):
        """
        Interrompe o cliente MQTT e a thread do loop
        """
        self.running = False
        if self.client.is_connected():
            self.client.disconnect()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
    
    def _run_loop(self):
        """
        Executa o loop MQTT em uma thread separada
        """
        # Usar loop_start em vez de loop_forever para melhor controle
        self.client.loop_start()
        
        while self.running:
            # Verificar se a conexão está ativa
            if not self.client.is_connected():
                logger.warning("Conexão MQTT perdida, tentando reconectar...")
                try:
                    self.client.reconnect()
                except Exception as e:
                    logger.error(f"Falha ao reconectar: {str(e)}")
                    time.sleep(5)  # Esperar antes de tentar novamente
            
            time.sleep(1)  # Evitar uso excessivo da CPU
        
        self.client.loop_stop()
    
    def on_connect(self, client, userdata, flags, rc):
        """
        Callback quando o cliente se conecta ao servidor
        
        Args:
            client: Cliente MQTT
            userdata: Dados do usuário
            flags: Flags de conexão
            rc: Código de retorno da conexão
        """
        if rc == 0:
            self.connected = True
            logger.info("Conectado ao servidor MQTT")
            
            # Subscrever aos tópicos relevantes
            for topic in self.topics:
                client.subscribe(topic)
                logger.info(f"Subscrito ao tópico: {topic}")
        else:
            self.connected = False
            logger.error(f"Falha ao conectar ao servidor MQTT, código {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """
        Callback quando o cliente se desconecta do servidor
        
        Args:
            client: Cliente MQTT
            userdata: Dados do usuário
            rc: Código de retorno da desconexão
        """
        self.connected = False
        if rc != 0:
            logger.warning(f"Desconexão inesperada do MQTT, código {rc}")
    
    def on_message(self, client, userdata, msg):
        """
        Callback quando uma mensagem é recebida
        
        Args:
            client: Cliente MQTT
            userdata: Dados do usuário
            msg: Mensagem recebida
        """
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        try:
            # Armazenar o último valor recebido
            self.last_data[topic] = payload
            self.last_data_time[topic] = datetime.now()
            
            # Log para todos os tópicos recebidos
            if 'filament_monitor' in topic:
                print(f">>> MQTT ESP32: Tópico={topic}, Valor={payload}", flush=True)
            
            # Processar a mensagem
            self._process_message(topic, payload)
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem MQTT: {str(e)}")
    
    def _process_message(self, topic, payload):
        """
        Processa uma mensagem MQTT recebida, salvando no banco de dados
        
        Args:
            topic (str): Tópico da mensagem
            payload (str): Conteúdo da mensagem
        """
        # Análise do tópico para extrair informações
        try:
            # Tópicos no formato "filament/box/N/medida"
            parts = topic.split('/')
            
            # Processar no formato antigo (filament/box/N/medida)
            if len(parts) >= 4 and parts[0] == 'filament' and parts[1] == 'box':
                box_number = int(parts[2])
                metric = parts[3]
                value = float(payload)
                
                logger.debug(f"Recebido: Box {box_number}, {metric} = {value}")
                
                # Atualizamos usando um único registro para cada leitura
                source = f"ESP32_Box{box_number}"
                ams_slot = box_number - 1  # Converte para base 0
                
                # Obter dados recentes para esta fonte/slot para manter outros valores
                recent_data = SensorManager.get_recent_sensor_data(source=source, limit=1)
                
                # Valores padrão
                temperature = None
                humidity = None
                ams_filament_remaining = None
                
                # Se houver dados recentes, usar como base
                if recent_data and len(recent_data) > 0:
                    temperature = recent_data[0].temperature
                    humidity = recent_data[0].humidity
                    ams_filament_remaining = recent_data[0].ams_filament_remaining
                
                # Atualizar o valor específico
                if metric == 'temperature':
                    temperature = value
                elif metric == 'humidity':
                    humidity = value
                elif metric in ['remaining_g', 'remaining_percent', 'total_weight']:
                    # Processar peso restante com lógica melhorada
                    if metric == 'remaining_g':
                        # Valor direto em gramas (prioritário)
                        print(f">>> Filament Box {box_number}: Registrando peso restante direto: {value}g", flush=True)
                        ams_filament_remaining = value
                    elif metric == 'total_weight' and ams_filament_remaining is None:
                        # Se não temos valor de remaining_g, usamos total_weight como fallback
                        print(f">>> Filament Box {box_number}: Usando peso total como restante: {value}g", flush=True)
                        ams_filament_remaining = value
                    elif metric == 'remaining_percent' and ams_filament_remaining is None:
                        # Tentativa de calcular gramas baseado na porcentagem e no peso padrão
                        last_weight = self.last_data.get(f"filament/box/{box_number}/total_weight")
                        if last_weight:
                            try:
                                filament_total = float(last_weight)
                                percentage = float(value)
                                ams_filament_remaining = (percentage / 100.0) * filament_total
                                print(f">>> Filament Box {box_number}: Calculando restante de {percentage}% de {filament_total}g = {ams_filament_remaining}g", flush=True)
                            except (ValueError, TypeError):
                                print(f">>> Filament Box {box_number}: Erro ao calcular peso restante de {value}% de {last_weight}g", flush=True)
                                # Fallback para valor padrão se o cálculo falhar
                                filament_max = 1000.0  # Gramas em um carretel completo
                                ams_filament_remaining = (float(value) / 100.0) * filament_max
                        else:
                            # Se não temos o peso total, usamos um valor padrão
                            filament_max = 1000.0  # Gramas em um carretel completo
                            ams_filament_remaining = (float(value) / 100.0) * filament_max
                            print(f">>> Filament Box {box_number}: Estimando restante com peso padrão: {value}% de 1000g = {ams_filament_remaining}g", flush=True)
                
                # Registrar dados consolidados
                SensorManager.record_sensor_data(
                    source=source,
                    temperature=temperature,
                    humidity=humidity,
                    ams_slot=ams_slot,
                    ams_filament_remaining=ams_filament_remaining
                )
                
            # Processar no formato do ESP32 (filament_monitor/medida/N)
            elif len(parts) >= 3 and parts[0] == 'filament_monitor':
                metric = parts[1]
                box_number = int(parts[2])
                value = float(payload)
                
                logger.debug(f"Recebido do ESP32: Box {box_number}, {metric} = {value}")
                
                # Atualizamos usando um único registro para cada leitura
                source = f"ESP32_Box{box_number}"
                ams_slot = box_number - 1  # Converte para base 0
                
                # Obter dados recentes para esta fonte/slot para manter outros valores
                recent_data = SensorManager.get_recent_sensor_data(source=source, limit=1)
                
                # Valores padrão
                temperature = None
                humidity = None
                ams_filament_remaining = None
                
                # Se houver dados recentes, usar como base
                if recent_data and len(recent_data) > 0:
                    temperature = recent_data[0].temperature
                    humidity = recent_data[0].humidity
                    ams_filament_remaining = recent_data[0].ams_filament_remaining
                
                # Atualizar o valor específico
                if metric == 'temperature':
                    temperature = value
                elif metric == 'humidity':
                    humidity = value
                elif metric in ['remaining_weight', 'remaining_percentage', 'weight']:
                    # Processar peso restante com lógica melhorada
                    if metric == 'remaining_weight':
                        # Valor direto em gramas (prioritário)
                        print(f">>> ESP32 Box {box_number}: Registrando peso restante direto: {value}g", flush=True)
                        ams_filament_remaining = value
                    elif metric == 'weight' and ams_filament_remaining is None:
                        # Se não temos valor de remaining_weight, usamos weight como fallback
                        # Isto considera que o ESP está enviando o peso total do filamento
                        print(f">>> ESP32 Box {box_number}: Usando peso total como restante: {value}g", flush=True)
                        ams_filament_remaining = value
                    elif metric == 'remaining_percentage' and ams_filament_remaining is None:
                        # Tentativa de calcular gramas baseado na porcentagem e no peso padrão
                        last_weight = self.last_data.get(f"filament_monitor/weight/{box_number}")
                        if last_weight:
                            try:
                                filament_total = float(last_weight)
                                percentage = float(value)
                                ams_filament_remaining = (percentage / 100.0) * filament_total
                                print(f">>> ESP32 Box {box_number}: Calculando restante de {percentage}% de {filament_total}g = {ams_filament_remaining}g", flush=True)
                            except (ValueError, TypeError):
                                print(f">>> ESP32 Box {box_number}: Erro ao calcular peso restante de {value}% de {last_weight}g", flush=True)
                                # Fallback para valor padrão se o cálculo falhar
                                filament_max = 1000.0  # Gramas em um carretel completo
                                ams_filament_remaining = (float(value) / 100.0) * filament_max
                        else:
                            # Se não temos o peso total, usamos um valor padrão
                            filament_max = 1000.0  # Gramas em um carretel completo
                            ams_filament_remaining = (float(value) / 100.0) * filament_max
                            print(f">>> ESP32 Box {box_number}: Estimando restante com peso padrão: {value}% de 1000g = {ams_filament_remaining}g", flush=True)
                
                # Registrar dados consolidados
                SensorManager.record_sensor_data(
                    source=source,
                    temperature=temperature,
                    humidity=humidity,
                    ams_slot=ams_slot,
                    ams_filament_remaining=ams_filament_remaining
                )
                
            # Processar mensagens de status do ESP32
            elif topic == 'filament_monitor/status':
                logger.info(f"Status do ESP32: {payload}")
            
            # Processar informações do sistema do ESP32
            elif topic.startswith('filament_monitor/system/'):
                system_metric = parts[2]
                logger.debug(f"Informação do sistema ESP32: {system_metric} = {payload}")
                
        except ValueError:
            logger.warning(f"Valor inválido no tópico {topic}: {payload}")
        except Exception as e:
            logger.error(f"Erro ao processar tópico {topic}: {str(e)}")
    
    def publish(self, topic, message):
        """
        Publica uma mensagem em um tópico
        
        Args:
            topic (str): Tópico para publicar
            message (str): Mensagem para publicar
            
        Returns:
            bool: True se publicado com sucesso
        """
        try:
            if not self.client.is_connected():
                logger.warning("Cliente MQTT não está conectado, mensagem não publicada")
                return False
                
            result = self.client.publish(topic, message)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"Falha ao publicar mensagem: {result.rc}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Erro ao publicar mensagem: {str(e)}")
            return False
    
    def send_command(self, box_number, command, value=None):
        """
        Envia um comando para uma caixa específica
        
        Args:
            box_number (int): Número da caixa (base 1)
            command (str): Comando a enviar
            value (str, optional): Valor do comando
            
        Returns:
            bool: True se enviado com sucesso
        """
        topic = f"filament/box/{box_number}/command/{command}"
        payload = "1" if value is None else str(value)
        
        return self.publish(topic, payload)
    
    def get_last_data(self, topic=None):
        """
        Retorna os últimos dados recebidos
        
        Args:
            topic (str, optional): Tópico específico ou None para todos
            
        Returns:
            dict: Últimos dados recebidos
        """
        if topic:
            return self.last_data.get(topic)
        return self.last_data
    
    def is_connected(self):
        """
        Verifica se o cliente está conectado
        
        Returns:
            bool: True se conectado
        """
        return self.connected and self.client.is_connected()

# Cliente global compartilhado
mqtt_client = None

def init_mqtt_client(config=None):
    """
    Inicializa e retorna um cliente MQTT com base na configuração
    
    Args:
        config (dict, optional): Configuração de MQTT
        
    Returns:
        MQTTClient: Cliente MQTT inicializado
    """
    global mqtt_client, mqtt_thread
    
    if mqtt_client:
        logger.warning("Cliente MQTT já inicializado, retornando instância existente")
        return mqtt_client
    
    # Configuração padrão ou fornecida
    if not config:
        config = {}
    
    mqtt_host = config.get('MQTT_HOST', 'localhost')
    mqtt_port = config.get('MQTT_PORT', 1883)
    mqtt_user = config.get('MQTT_USER', None)
    mqtt_pass = config.get('MQTT_PASSWORD', None)
    
    # Iniciar o cliente MQTT
    try:
        if mqtt_user and mqtt_pass:
            logger.info(f"Iniciando cliente MQTT em {mqtt_host}:{mqtt_port} com autenticação")
        else:
            logger.info(f"Iniciando cliente MQTT em {mqtt_host}:{mqtt_port} SEM autenticação")
            
        mqtt_client = MQTTClient(mqtt_host, mqtt_port, mqtt_user, mqtt_pass)
        
        if mqtt_client.start():
            logger.info("Cliente MQTT iniciado com sucesso")
            return mqtt_client
        else:
            logger.error("Falha ao iniciar cliente MQTT")
            mqtt_client = None
            return None
            
    except Exception as e:
        logger.error(f"Erro ao inicializar cliente MQTT: {str(e)}")
        mqtt_client = None
        return None

def get_mqtt_client():
    """
    Retorna o cliente MQTT global, inicializando se necessário
    
    Returns:
        MQTTClient: Cliente MQTT
    """
    global mqtt_client
    if mqtt_client is None:
        mqtt_client = init_mqtt_client()
    return mqtt_client

def shutdown_mqtt_client():
    """
    Desliga o cliente MQTT global
    """
    global mqtt_client
    if mqtt_client is not None:
        mqtt_client.stop()
        mqtt_client = None
        logger.info("Cliente MQTT desligado")

if __name__ == "__main__":
    # Teste simples
    client = init_mqtt_client()
    logger.info(f"Cliente MQTT conectado: {client.is_connected()}")
    
    try:
        # Manter ativo por um tempo para receber mensagens
        for i in range(60):
            time.sleep(1)
            if i % 10 == 0:
                logger.info(f"Conectado: {client.is_connected()}, dados recebidos: {len(client.last_data)}")
    except KeyboardInterrupt:
        logger.info("Teste interrompido pelo usuário")
    finally:
        shutdown_mqtt_client() 