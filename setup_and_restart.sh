#!/bin/bash

# Script para configurar e reiniciar o SquidBu

echo "=== Configuração e Reinicialização do SquidBu ==="
echo "NOTA: Se este script falhar, execute os comandos manualmente."

# Caminho para o ambiente virtual
VENV_PATH="./venv"
echo "Verificando ambiente virtual em: $VENV_PATH"

if [ ! -d "$VENV_PATH" ]; then
  echo "AVISO: Ambiente virtual não encontrado. Criando..."
  echo "Execute manualmente: python3 -m venv venv"
  python3 -m venv venv
fi

# Ativa o ambiente virtual
echo "Ativando ambiente virtual..."
echo "Execute manualmente: source venv/bin/activate"
source venv/bin/activate || { echo "Falha ao ativar o ambiente virtual. Continue manualmente."; }

# Instala o psutil se necessário
echo "Instalando dependências..."
echo "Execute manualmente: pip install psutil"
pip install psutil || { echo "Falha ao instalar psutil. Continue manualmente."; }

# Encerra os processos Flask atuais
echo "Encerrando processos Flask..."
echo "Execute manualmente: pkill -f 'app.py'"
pkill -f "app.py" || echo "Nenhum processo Flask encontrado ou falha ao encerrar."

# Aguarda 5 segundos
echo "Aguardando processos encerrarem..."
sleep 5

# Reinicia o aplicativo
echo "Reiniciando o aplicativo..."
echo "Execute manualmente: python3 SquidStart.py"

# Inicia o aplicativo em background
nohup python3 SquidStart.py > squid_start.log 2>&1 &
PID=$!
echo "Aplicativo iniciado com PID: $PID"

# Verifica se o servidor MQTT está em execução
echo "Verificando o servidor MQTT..."
pgrep mosquitto > /dev/null
if [ $? -eq 0 ]; then
  echo "Servidor MQTT (mosquitto) está em execução."
else
  echo "AVISO: Servidor MQTT (mosquitto) parece não estar em execução."
  echo "Execute manualmente: sudo service mosquitto start"
fi

echo "=== Configuração e Reinicialização Concluídas ==="
echo "Monitore os logs com: tail -f squid_start.log" 