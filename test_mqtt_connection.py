#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paho.mqtt.client as mqtt
import json
import time
import sys

# Configurações
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_USER = ""
MQTT_PASSWORD = ""
MQTT_CLIENT_ID = "test_mqtt_client"

# Lista de tópicos a monitorar
TOPICS = [
    "filament/box/+/temperature",
    "filament/box/+/humidity",
    "filament/box/+/usage_mm",
    "filament/box/+/remaining_g",
    "filament/box/+/remaining_percent",
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

# Contador para mensagens recebidas
messages_received = 0
esp32_messages = 0
messages_by_topic = {}

# Callback quando conectado
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Conectado ao servidor MQTT em {MQTT_HOST}:{MQTT_PORT}")
        # Subscrever a todos os tópicos
        for topic in TOPICS:
            client.subscribe(topic)
            print(f"Subscrito ao tópico: {topic}")
    else:
        print(f"Falha ao conectar ao servidor MQTT, código: {rc}")

# Callback quando mensagem recebida
def on_message(client, userdata, msg):
    global messages_received, esp32_messages
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    
    messages_received += 1
    
    # Contador por tópico
    topic_base = topic.split('/')[0]
    if topic_base == "filament_monitor":
        esp32_messages += 1
    
    if topic_base not in messages_by_topic:
        messages_by_topic[topic_base] = 0
    messages_by_topic[topic_base] += 1
    
    # Exibir detalhes da mensagem
    print(f"Tópico: {topic}")
    print(f"Payload: {payload}")
    print(f"Mensagens totais: {messages_received} (ESP32: {esp32_messages})")
    print("=" * 50)

def main():
    print("=== Teste de Conexão MQTT ===")
    print(f"Servidor: {MQTT_HOST}:{MQTT_PORT}")
    
    client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    
    # Configurar callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Configurar autenticação (se necessário)
    if MQTT_USER and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    
    try:
        # Conectar ao servidor
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        
        # Iniciar loop
        client.loop_start()
        
        # Mostrar estatísticas a cada 5 segundos
        start_time = time.time()
        try:
            while True:
                time.sleep(5)
                elapsed = time.time() - start_time
                print(f"\nEstatísticas após {elapsed:.1f} segundos:")
                print(f"Mensagens totais: {messages_received}")
                print(f"Mensagens do ESP32: {esp32_messages}")
                print("Por tipo de tópico:")
                for topic_base, count in messages_by_topic.items():
                    print(f"  - {topic_base}: {count}")
                
                if elapsed > 30 and messages_received == 0:
                    print("Nenhuma mensagem recebida após 30 segundos. Verifique a conexão.")
                elif esp32_messages == 0 and elapsed > 30:
                    print("Nenhuma mensagem do ESP32 recebida. Verifique a configuração do ESP32.")
                
                print("=" * 50)
                
        except KeyboardInterrupt:
            print("\nMonitoramento interrompido pelo usuário.")
        
        # Parar loop e desconectar
        client.loop_stop()
        client.disconnect()
        
    except Exception as e:
        print(f"Erro durante a execução: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 