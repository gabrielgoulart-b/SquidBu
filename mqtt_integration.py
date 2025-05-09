#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import threading
import time
import ssl
from datetime import datetime, timedelta

from mqtt_client import init_mqtt_client, get_mqtt_client
from db_manager import SensorManager

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mqtt_integration')

class MQTTIntegration:
    """
    Classe para integrar o cliente MQTT com a aplicação Flask
    """
    
    def __init__(self, config=None):
        """
        Inicializa a integração MQTT
        
        Args:
            config (dict, optional): Configuração MQTT ou None para usar config.json
        """
        self.client = None
        self.config = config
        self.thread = None
        self.running = False
        self.last_data_check = datetime.now()
        self.bambu_client = None
        self.bambu_connected = False
        self.update_callback = None  # Callback para atualizar printer_status
        
        # Tenta inicializar cliente MQTT
        self.init_client()
        # Tenta inicializar cliente MQTT da Bambu Lab
        self.init_bambu_client()
        
        # Inicia o monitoramento
        self.start_monitoring()
    
    def init_client(self):
        """
        Inicializa o cliente MQTT
        
        Returns:
            bool: True se inicializado com sucesso
        """
        try:
            self.client = init_mqtt_client(self.config)
            return self.client is not None and self.client.is_connected()
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente MQTT: {str(e)}")
            return False
    
    def init_bambu_client(self):
        """
        Inicializa o cliente MQTT para a impressora Bambu Lab
        
        Returns:
            bool: True se inicializado com sucesso
        """
        try:
            # Carregar configuração
            if self.config is None:
                try:
                    with open('config.json', 'r') as f:
                        self.config = json.load(f)
                except Exception as e:
                    logger.error(f"Erro ao carregar configuração para Bambu MQTT: {str(e)}")
                    return False
            
            import paho.mqtt.client as mqtt
            
            # Obter configurações da impressora Bambu
            printer_ip = self.config.get('PRINTER_IP')
            access_code = self.config.get('ACCESS_CODE')
            device_id = self.config.get('DEVICE_ID')
            
            if not printer_ip or not access_code or not device_id:
                logger.error("Configuração incompleta para Bambu MQTT")
                return False
            
            # Criar cliente MQTT para Bambu
            self.bambu_client = mqtt.Client()
            self.bambu_client.on_connect = self._on_bambu_connect
            self.bambu_client.on_message = self._on_bambu_message
            self.bambu_client.on_disconnect = self._on_bambu_disconnect
            
            # Configurar autenticação e TLS
            self.bambu_client.username_pw_set("bblp", access_code)
            self.bambu_client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT, cert_reqs=ssl.CERT_NONE)
            self.bambu_client.tls_insecure_set(True)
            
            # Tópicos e informações da Bambu
            self.bambu_topic_report = f"device/{device_id}/report"
            self.bambu_topic_request = f"device/{device_id}/request"
            
            # Conectar ao broker Bambu em uma thread separada
            import threading
            bambu_thread = threading.Thread(target=self._bambu_connect_thread, args=(printer_ip,))
            bambu_thread.daemon = True
            bambu_thread.start()
            
            logger.info(f"Cliente MQTT Bambu inicializado para {printer_ip}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente MQTT Bambu: {str(e)}")
            return False
    
    def _bambu_connect_thread(self, printer_ip):
        """Thread para conectar ao broker MQTT da Bambu"""
        try:
            # Porta MQTT padrão da Bambu
            mqtt_port = 8883
            
            # Configuração do cliente MQTT
            logger.info(f"Conectando ao broker MQTT da Bambu em {printer_ip}:{mqtt_port}")
            
            # Conectar ao broker
            self.bambu_client.connect(printer_ip, mqtt_port, 60)
            
            # Iniciar loop em segundo plano
            self.bambu_client.loop_forever()
        except Exception as e:
            logger.error(f"Erro na thread de conexão Bambu: {e}")
            print(f"<<< ERRO Thread Bambu: {str(e)}", flush=True)
            self.bambu_connected = False
    
    def _on_bambu_connect(self, client, userdata, flags, rc):
        """Callback quando conectado ao broker Bambu"""
        if rc == 0:
            logger.info("Conectado ao broker MQTT da Bambu")
            self.bambu_connected = True
            # Inscrever-se no tópico de relatórios
            client.subscribe(self.bambu_topic_report)
        else:
            logger.error(f"Falha ao conectar ao broker MQTT da Bambu, código {rc}")
            self.bambu_connected = False
    
    def _on_bambu_disconnect(self, client, userdata, rc):
        """Callback quando desconectado do broker Bambu"""
        self.bambu_connected = False
        logger.warning(f"Desconectado do broker MQTT da Bambu, código {rc}")
    
    def _on_bambu_message(self, client, userdata, msg):
        """
        Callback quando uma mensagem é recebida do broker Bambu
        
        Args:
            client: Cliente MQTT
            userdata: Dados do usuário
            msg: Mensagem MQTT recebida
        """
        try:
            # Log detalhado para debug
            print(f"<<< Recebida mensagem no tópico Bambu: {msg.topic}", flush=True)
            print(f"<<< Tamanho do payload Bambu: {len(msg.payload)} bytes", flush=True)
            
            # Se for o tópico de report, processa os dados
            if msg.topic == self.bambu_topic_report:
                data = json.loads(msg.payload)
                # Processa apenas os dados JSON válidos
                logger.info(f"Recebida mensagem Bambu em: {msg.topic} ({len(msg.payload)} bytes)")
                self._process_bambu_data(data)
        except json.JSONDecodeError:
            logger.warning(f"Recebida mensagem Bambu com JSON inválido: {msg.payload}")
            print(f"<<< ERRO: JSON inválido no payload Bambu", flush=True)
        except Exception as e:
            logger.error(f"Erro ao processar mensagem Bambu: {str(e)}")
            print(f"<<< ERRO ao processar mensagem Bambu: {str(e)}", flush=True)
    
    def _process_bambu_data(self, data):
        """
        Processa dados recebidos da impressora Bambu e atualiza o banco de dados
        
        Args:
            data (dict): Dados recebidos via MQTT
        """
        try:
            # Log do payload completo para debug
            logger.debug(f"Dados recebidos da Bambu: {json.dumps(data, indent=2)}")
            
            # Atualizar o objeto printer_status global via callback
            if self.update_callback:
                try:
                    self.update_callback(data)
                    logger.info(f"Atualizado printer_status via callback com dados da Bambu: {list(data.keys())}")
                    print(f"<<< Atualizado printer_status via callback com: {list(data.keys())}", flush=True)
                except Exception as e:
                    logger.error(f"Erro ao chamar callback de atualização: {str(e)}")
                    print(f"<<< ERRO no callback de atualização: {str(e)}", flush=True)
            else:
                logger.warning("Nenhum callback de atualização definido")
                print("<<< AVISO: Nenhum callback de atualização definido", flush=True)
            
            # Inicializar valores de estatísticas
            power_on_hours = None
            total_prints = None
            print_hours = None
            
            # Verificar se há dados de print na mensagem
            if 'print' in data:
                print_data = data['print']
                logger.debug(f"Encontrado nó 'print' nos dados MQTT")
                
                # Extrair informações relevantes
                if 'mc_remaining_time' in print_data:
                    logger.debug(f"Impressão em andamento, tempo restante: {print_data['mc_remaining_time']}")
                
                # Verificar dados de impressão total
                if 'total_layer_num' in print_data:
                    total_layers = print_data.get('total_layer_num', 0)
                    logger.debug(f"Total de camadas: {total_layers}")
                
                # Verificar se há informações de estatísticas da impressora
                if 'gcode_state' in print_data:
                    gcode_state = print_data.get('gcode_state')
                    logger.debug(f"Estado da impressora: {gcode_state}")
                    
                # Extrair estatísticas se disponíveis
                if 'print_job' in print_data:
                    job_data = print_data.get('print_job', {})
                    logger.debug(f"Encontrados dados do trabalho de impressão: {job_data}")
                    if 'printed_time' in job_data:
                        # Tempo já impresso no trabalho atual (em segundos)
                        printed_time = job_data.get('printed_time', 0)
                        logger.debug(f"Tempo impresso neste trabalho: {printed_time} segundos")
                        
                # Verificar estatísticas históricas
                if 'statistics' in print_data:
                    stats_data = print_data.get('statistics', {})
                    logger.debug(f"Encontradas estatísticas em 'print': {stats_data}")
                    if 'total_time' in stats_data:
                        # Total de tempo de impressão (em horas)
                        print_hours = float(stats_data.get('total_time', 0)) / 3600.0
                        logger.info(f"Total de horas de impressão (print/statistics): {print_hours:.1f} horas")
                    if 'total_prints' in stats_data:
                        # Total de impressões realizadas
                        total_prints = int(stats_data.get('total_prints', 0))
                        logger.info(f"Total de impressões realizadas (print/statistics): {total_prints}")
                
                # Verificar comando específico get_print_stats
                if 'command' in print_data and print_data['command'] == 'get_print_stats':
                    if 'stats' in print_data:
                        stats = print_data.get('stats', {})
                        logger.debug(f"Estatísticas de print/get_print_stats: {stats}")
                        if 'total_hours' in stats:
                            print_hours = float(stats.get('total_hours', 0))
                            logger.info(f"Total de horas de impressão (get_print_stats): {print_hours:.1f} horas")
                        if 'total_jobs' in stats:
                            total_prints = int(stats.get('total_jobs', 0))
                            logger.info(f"Total de trabalhos (get_print_stats): {total_prints}")
            
            # Verificar se há dados de info na mensagem
            if 'info' in data:
                info_data = data['info']
                logger.debug(f"Encontrado nó 'info' nos dados MQTT")
                
                # Extrair informações de versão e outros dados da impressora
                if 'command' in info_data and info_data['command'] == 'get_version':
                    if 'module' in info_data:
                        modules = info_data.get('module', [])
                        for module in modules:
                            if module.get('name') == 'printer':
                                logger.debug(f"Encontrado módulo printer em info/get_version: {module}")
                                # Extrair estatísticas do módulo printer se disponíveis
                                if 'statistics' in module:
                                    stats = module.get('statistics', {})
                                    logger.debug(f"Estatísticas em info/module/printer: {stats}")
                                    if 'print_time' in stats:
                                        # Tempo total de impressão (em horas)
                                        print_hours = float(stats.get('print_time', 0))
                                        logger.info(f"Tempo total de impressão (info/module/printer): {print_hours:.1f} horas")
                                    if 'print_count' in stats:
                                        # Número total de impressões concluídas
                                        total_prints = int(stats.get('print_count', 0))
                                        logger.info(f"Número total de impressões (info/module/printer): {total_prints}")
                                    if 'power_on_time' in stats:
                                        # Tempo total ligada (em horas)
                                        power_on_hours = float(stats.get('power_on_time', 0))
                                        logger.info(f"Tempo total ligada (info/module/printer): {power_on_hours:.1f} horas")
            
            # Verificar se há dados de system na mensagem
            if 'system' in data:
                system_data = data['system']
                logger.debug(f"Encontrado nó 'system' nos dados MQTT")
                
                # Extrair informações do sistema
                if 'command' in system_data and system_data['command'] == 'get_printer_info':
                    if 'printer' in system_data:
                        printer_info = system_data.get('printer', {})
                        logger.debug(f"Encontradas informações da impressora em system/get_printer_info: {printer_info}")
                        if 'total_usage' in printer_info:
                            usage_data = printer_info.get('total_usage', {})
                            logger.debug(f"Dados de uso total em system/printer: {usage_data}")
                            if 'print_hours' in usage_data:
                                # Horas totais de impressão
                                print_hours = float(usage_data.get('print_hours', 0))
                                logger.info(f"Horas totais de impressão (system/printer/total_usage): {print_hours:.1f} horas")
                            if 'job_count' in usage_data:
                                # Contagem total de trabalhos de impressão
                                total_prints = int(usage_data.get('job_count', 0))
                                logger.info(f"Total de trabalhos (system/printer/total_usage): {total_prints}")
                            if 'power_on_hours' in usage_data:
                                # Horas totais ligada
                                power_on_hours = float(usage_data.get('power_on_hours', 0))
                                logger.info(f"Horas totais ligada (system/printer/total_usage): {power_on_hours:.1f} horas")
            
            # Verificar nó pushing
            if 'pushing' in data:
                pushing_data = data['pushing']
                logger.debug(f"Encontrado nó 'pushing' nos dados MQTT")
                # Verificar se há dados de tempo na mensagem pushing
                if 'print_stats' in pushing_data:
                    stats = pushing_data.get('print_stats', {})
                    logger.debug(f"Estatísticas em pushing/print_stats: {stats}")
                    if 'accumulated_time' in stats:
                        print_hours = float(stats.get('accumulated_time', 0)) / 3600.0
                        logger.info(f"Tempo acumulado de impressão (pushing/print_stats): {print_hours:.1f} horas")
                    if 'total_jobs' in stats:
                        total_prints = int(stats.get('total_jobs', 0))
                        logger.info(f"Total de trabalhos (pushing/print_stats): {total_prints}")
            
            # Verificar se há dados para atualizar no banco de dados
            if power_on_hours is not None or total_prints is not None or print_hours is not None:
                logger.info(f"Atualizando estatísticas da impressora: Horas ligada={power_on_hours}, Horas de impressão={print_hours}, Total de impressões={total_prints}")
                
                # Atualizar estatísticas no banco de dados
                from db_manager import StatsManager
                
                # Usamos valores condicionais para atualizar apenas o que foi recebido
                update_data = {}
                if power_on_hours is not None:
                    update_data['power_on_hours'] = float(power_on_hours)
                if total_prints is not None:
                    update_data['prints'] = int(total_prints)
                if print_hours is not None:
                    update_data['hours'] = float(print_hours)
                    
                if update_data:
                    StatsManager.update_printer_stats(**update_data)
                    logger.info(f"Estatísticas atualizadas no banco de dados: {update_data}")
        
        except Exception as e:
            logger.error(f"Erro ao processar dados da Bambu: {str(e)}", exc_info=True)
    
    def _monitoring_loop(self):
        """
        Loop de monitoramento para processar dados da ESP32 e outros eventos
        """
        try:
            while self.running:
                # Verificar dados do ESP32
                self._check_esp32_data()
                
                # Verificar dados da impressora Bambu Lab
                self._check_bambu_data()
                
                # Dormir um pouco para não sobrecarregar o sistema
                time.sleep(5)
        except Exception as e:
            logger.error(f"Erro no loop de monitoramento: {str(e)}")
    
    def _check_esp32_data(self):
        """
        Verifica e processa dados do ESP32
        """
        try:
            # Obter o cliente MQTT
            client = get_mqtt_client()
            if not client or not client.is_connected():
                return
                
            # Processar mensagens recebidas no último intervalo
            # Nada a fazer aqui, pois os callbacks do MQTT já lidam com isso
            # Esta função pode ser expandida conforme necessário
            
            # Verificar se precisa solicitar dados novamente
            # Se não recebemos atualizações recentes, podemos solicitar explicitamente
            now = datetime.now()
            if (now - self.last_data_check).total_seconds() > 300:  # A cada 5 minutos
                logger.info("Solicitando dados do ESP32 (intervalo de 5 minutos)")
                self.last_data_check = now
                
        except Exception as e:
            logger.error(f"Erro ao verificar dados do ESP32: {str(e)}")
    
    def _check_bambu_data(self):
        """
        Verifica e processa dados da impressora Bambu Lab
        """
        # Implementação da obtenção dos dados da impressora Bambu Lab via MQTT
        try:
            if self.bambu_client and self.bambu_connected:
                # Verificar se é hora de solicitar estatísticas da impressora (a cada 30 minutos)
                now = datetime.now()
                if not hasattr(self, 'last_stats_check') or (now - self.last_stats_check).total_seconds() > 1800:
                    logger.info("Solicitando estatísticas da impressora Bambu Lab (intervalo de 30 minutos)")
                    self.last_stats_check = now
                    
                    # Solicitar informações da impressora
                    self._request_printer_stats()
                    
        except Exception as e:
            logger.error(f"Erro ao verificar dados da Bambu Lab: {str(e)}")
    
    def _request_printer_stats(self):
        """
        Solicita estatísticas da impressora via MQTT
        """
        try:
            if not self.bambu_client or not self.bambu_connected:
                logger.warning("Cliente MQTT Bambu não está conectado, não é possível solicitar estatísticas")
                return
            
            # Gerar um ID de sequência único
            sequence_id = str(int(time.time()))
            
            # Solicitar push de todos os dados (contém estatísticas completas)
            request_payload = {
                "pushing": {
                    "sequence_id": sequence_id,
                    "command": "pushall"
                }
            }
            payload_json = json.dumps(request_payload)
            logger.info(f"Enviando solicitação 'pushall' (seq: {sequence_id}) para {self.bambu_topic_request}")
            self.bambu_client.publish(self.bambu_topic_request, payload_json)
            
            # Incrementar sequence_id
            sequence_id = str(int(time.time()) + 1)
            
            # Solicitar informações da versão (que contém estatísticas)
            request_payload = {
                "info": {
                    "sequence_id": sequence_id,
                    "command": "get_version"
                }
            }
            payload_json = json.dumps(request_payload)
            logger.info(f"Enviando solicitação 'get_version' (seq: {sequence_id}) para {self.bambu_topic_request}")
            self.bambu_client.publish(self.bambu_topic_request, payload_json)
            
            # Também solicitar informações detalhadas da impressora
            sequence_id = str(int(time.time()) + 2)
            request_payload = {
                "system": {
                    "sequence_id": sequence_id,
                    "command": "get_printer_info"
                }
            }
            payload_json = json.dumps(request_payload)
            logger.info(f"Enviando solicitação 'get_printer_info' (seq: {sequence_id}) para {self.bambu_topic_request}")
            self.bambu_client.publish(self.bambu_topic_request, payload_json)
            
            # Solicitação adicional mais específica para obter informações de horas de impressão
            sequence_id = str(int(time.time()) + 3)
            request_payload = {
                "print": {
                    "sequence_id": sequence_id,
                    "command": "get_print_stats"
                }
            }
            payload_json = json.dumps(request_payload)
            logger.info(f"Enviando solicitação 'get_print_stats' (seq: {sequence_id}) para {self.bambu_topic_request}")
            self.bambu_client.publish(self.bambu_topic_request, payload_json)
            
        except Exception as e:
            logger.error(f"Erro ao solicitar estatísticas da impressora: {str(e)}")
    
    def start_monitoring(self):
        """
        Inicia o monitoramento MQTT em uma thread separada
        
        Returns:
            bool: True se iniciado com sucesso
        """
        if self.thread and self.thread.is_alive():
            logger.warning("Thread de monitoramento já está em execução")
            return True
        
        self.running = True
        self.thread = threading.Thread(target=self._monitoring_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Thread de monitoramento MQTT iniciada")
        return True

    def force_stats_update(self):
        """
        Força a solicitação imediata de estatísticas da impressora.
        Útil para diagnóstico ou quando precisamos garantir que temos dados atualizados.
        
        Returns:
            bool: True se a solicitação foi enviada
        """
        logger.info("Forçando atualização de estatísticas da impressora")
        try:
            if not self.bambu_client or not self.bambu_connected:
                logger.warning("Cliente MQTT Bambu não está conectado, não é possível solicitar estatísticas")
                return False
                
            # Resetar o timer para permitir uma nova solicitação imediata
            self.last_stats_check = datetime.now() - timedelta(hours=1)
            
            # Solicitar estatísticas
            self._request_printer_stats()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao forçar atualização de estatísticas: {str(e)}")
            return False

    def set_update_callback(self, callback):
        """
        Define o callback a ser usado para atualizar o printer_status
        
        Args:
            callback: Função que recebe os dados a serem atualizados
        """
        self.update_callback = callback
        logger.info("Callback de atualização definido")
        print("<<< Callback de atualização definido", flush=True)