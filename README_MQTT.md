# Configuração MQTT para o SquidBu

Este documento contém instruções para reiniciar o servidor MQTT e testar a conexão com o ESP32.

## Reiniciando o servidor

O servidor foi configurado para aceitar mensagens no formato que o ESP32 está enviando (`filament_monitor/...`). Para aplicar as alterações, é necessário reiniciar o servidor.

### Método 1: Usando o script de reinicialização

Execute o script de reinicialização:

```bash
# Tornar o script executável
chmod +x setup_and_restart.sh

# Executar o script
./setup_and_restart.sh
```

### Método 2: Reiniciando manualmente

Se o método automático falhar, siga estes passos:

1. Ative o ambiente virtual:
   ```bash
   source venv/bin/activate
   ```

2. Instale o pacote `psutil` necessário:
   ```bash
   pip install psutil
   ```

3. Encerre os processos Flask em execução:
   ```bash
   pkill -f "app.py"
   ```

4. Inicie o aplicativo Flask:
   ```bash
   python3 SquidStart.py
   ```

## Testando a conexão MQTT

Para verificar se o servidor está recebendo as mensagens do ESP32, use o script de teste MQTT:

```bash
# Tornar o script executável
chmod +x test_mqtt_connection.py

# Executar o script
python3 test_mqtt_connection.py
```

Este script:
- Conecta-se ao servidor MQTT
- Monitora os tópicos `filament/box/...` e `filament_monitor/...`
- Exibe as mensagens recebidas em tempo real
- Fornece estatísticas sobre as mensagens recebidas a cada 5 segundos

## Tópicos MQTT do ESP32

O ESP32 utiliza os seguintes tópicos MQTT:

- `filament_monitor/temperature/N` - temperatura da caixa N
- `filament_monitor/humidity/N` - umidade da caixa N
- `filament_monitor/usage/N` - uso de filamento da caixa N
- `filament_monitor/remaining_weight/N` - peso restante na caixa N
- `filament_monitor/remaining_percentage/N` - percentual restante na caixa N
- `filament_monitor/density/N` - densidade do filamento na caixa N
- `filament_monitor/weight/N` - peso inicial configurado para a caixa N
- `filament_monitor/status` - status do ESP32
- `filament_monitor/system/...` - informações do sistema do ESP32

## Verificação de Logs

Para monitorar os logs do aplicativo Flask, use:

```bash
tail -f flask_app.log
```

Procure por mensagens contendo "ESP32" ou "MQTT" para verificar a comunicação. 