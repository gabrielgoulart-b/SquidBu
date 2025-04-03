#!/usr/bin/env python3
import subprocess
import os
import time
import sys
import signal

# --- Configuração ---
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__)) # Diretório onde SquidStart.py está
VENV_PYTHON = os.path.join(PROJECT_DIR, 'printer_monitor', 'venv', 'bin', 'python')
APP_SCRIPT = os.path.join(PROJECT_DIR, 'app.py')
TAILSCALE_CMD = ['tailscale', 'funnel', '5000'] # Comando para iniciar o Funnel
FLASK_LOG = os.path.join(PROJECT_DIR, 'flask_app.log')
TAILSCALE_LOG = os.path.join(PROJECT_DIR, 'tailscale_funnel.log')
# ------------------

flask_process = None
tailscale_process = None

def start_flask():
    """Inicia o aplicativo Flask usando o interpretador Python do venv."""
    global flask_process
    if not os.path.exists(VENV_PYTHON):
        print(f"ERRO: Interpretador Python do Venv não encontrado em {VENV_PYTHON}", file=sys.stderr)
        print("Certifique-se de que o ambiente virtual foi criado em 'printer_monitor/venv'", file=sys.stderr)
        return None
    if not os.path.exists(APP_SCRIPT):
        print(f"ERRO: Script app.py não encontrado em {APP_SCRIPT}", file=sys.stderr)
        return None

    print(f"Iniciando Flask App ({APP_SCRIPT}) com {VENV_PYTHON}...")
    try:
        # Abre arquivos de log para stdout e stderr do Flask
        flask_log_out = open(FLASK_LOG, 'a')
        flask_process = subprocess.Popen(
            [VENV_PYTHON, APP_SCRIPT],
            cwd=PROJECT_DIR, # Define o diretório de trabalho para o Flask
            stdout=flask_log_out,
            stderr=subprocess.STDOUT # Redireciona stderr para o mesmo log de stdout
        )
        print(f"Flask App iniciado. PID: {flask_process.pid}. Logs em: {FLASK_LOG}")
        return flask_process
    except Exception as e:
        print(f"ERRO ao iniciar Flask App: {e}", file=sys.stderr)
        return None

def start_tailscale_funnel():
    """Inicia o Tailscale Funnel."""
    global tailscale_process
    print(f"Iniciando Tailscale Funnel ({' '.join(TAILSCALE_CMD)})...")
    try:
        # Verifica se o comando tailscale existe
        if subprocess.call(['which', TAILSCALE_CMD[0]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
             print(f"ERRO: Comando '{TAILSCALE_CMD[0]}' não encontrado. Tailscale está instalado e no PATH?", file=sys.stderr)
             return None

        # Abre arquivos de log para stdout e stderr do Tailscale
        # Nota: Tailscale funnel pode precisar de permissões elevadas na primeira vez
        # ou se o usuário não tiver permissão. Rodar via systemd como usuário 'gabriel'
        # deve funcionar se 'sudo tailscale up --operator=gabriel' foi rodado antes,
        # ou se o serviço tailscaled está corretamente configurado.
        tailscale_log_out = open(TAILSCALE_LOG, 'a')
        tailscale_process = subprocess.Popen(
            TAILSCALE_CMD,
            stdout=tailscale_log_out,
            stderr=subprocess.STDOUT # Redireciona stderr para o mesmo log de stdout
        )
        print(f"Tailscale Funnel iniciado. PID: {tailscale_process.pid}. Logs em: {TAILSCALE_LOG}")
        return tailscale_process
    except Exception as e:
        print(f"ERRO ao iniciar Tailscale Funnel: {e}", file=sys.stderr)
        return None

def shutdown(signum, frame):
    """Função para lidar com sinais de encerramento (Ctrl+C)."""
    print("\nRecebido sinal de encerramento. Parando processos...")
    if tailscale_process and tailscale_process.poll() is None:
        print("Parando Tailscale Funnel...")
        tailscale_process.terminate() # Tenta terminar graciosamente
        try:
            tailscale_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Tailscale Funnel não terminou, forçando...")
            tailscale_process.kill()
    if flask_process and flask_process.poll() is None:
        print("Parando Flask App...")
        flask_process.terminate()
        try:
            flask_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Flask App não terminou, forçando...")
            flask_process.kill()
    print("Processos parados. Saindo.")
    sys.exit(0)

if __name__ == "__main__":
    # Configura handlers para SIGINT (Ctrl+C) e SIGTERM
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("--- Iniciando SquidStart --- S")
    flask_process = start_flask()
    time.sleep(2) # Pequena pausa antes de iniciar o próximo
    tailscale_process = start_tailscale_funnel()

    if not flask_process or not tailscale_process:
        print("ERRO: Falha ao iniciar um ou ambos os serviços. Verifique os logs.", file=sys.stderr)
        shutdown(None, None) # Tenta parar o que iniciou e sai
        sys.exit(1)

    print("--- SquidStart rodando. Pressione Ctrl+C para parar. ---")

    # Mantém o script principal rodando e monitora os processos
    try:
        while True:
            if flask_process and flask_process.poll() is not None:
                print("ALERTA: Processo Flask terminou inesperadamente. Tentando reiniciar...", file=sys.stderr)
                time.sleep(5)
                flask_process = start_flask()

            if tailscale_process and tailscale_process.poll() is not None:
                print("ALERTA: Processo Tailscale Funnel terminou inesperadamente. Tentando reiniciar...", file=sys.stderr)
                time.sleep(5)
                tailscale_process = start_tailscale_funnel()

            if not flask_process or not tailscale_process:
                 print("ERRO: Falha ao reiniciar um serviço. Encerrando.", file=sys.stderr)
                 shutdown(None, None)
                 sys.exit(1)

            time.sleep(10) # Verifica a cada 10 segundos
    except KeyboardInterrupt:
        shutdown(None, None) 