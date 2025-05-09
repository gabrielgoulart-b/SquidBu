#!/usr/bin/env python3
import os
import subprocess
import sys
import time
import signal
import psutil

def find_flask_process():
    """Encontra o processo do Flask em execução"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Verifica se o comando contém 'app.py'
            cmdline = proc.cmdline()
            if cmdline and len(cmdline) > 1 and 'app.py' in cmdline[1]:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def restart_flask():
    """Reinicia o aplicativo Flask"""
    # Encontra e encerra o processo Flask atual
    flask_process = find_flask_process()
    if flask_process:
        print(f"Processo Flask encontrado (PID: {flask_process.pid}). Encerrando...")
        try:
            # Envia SIGTERM para encerramento gracioso
            os.kill(flask_process.pid, signal.SIGTERM)
            
            # Espera até 5 segundos pelo encerramento
            for _ in range(5):
                if not psutil.pid_exists(flask_process.pid):
                    break
                time.sleep(1)
                
            # Se ainda estiver em execução, força o encerramento
            if psutil.pid_exists(flask_process.pid):
                print("Forçando encerramento...")
                os.kill(flask_process.pid, signal.SIGKILL)
                
            print("Processo Flask encerrado com sucesso.")
        except Exception as e:
            print(f"Erro ao encerrar o processo Flask: {e}")
    else:
        print("Nenhum processo Flask encontrado em execução.")
    
    # Inicia um novo processo Flask usando o SquidStart.py
    print("Iniciando o SquidStart.py...")
    try:
        # Usar o diretório atual como base
        project_dir = os.getcwd()
        squid_start = os.path.join(project_dir, 'SquidStart.py')
        
        if not os.path.exists(squid_start):
            print(f"ERRO: Script SquidStart.py não encontrado em {squid_start}")
            return False
            
        # Inicia o novo processo
        subprocess.Popen(['python3', squid_start], 
                       stdout=subprocess.DEVNULL, 
                       stderr=subprocess.DEVNULL)
        
        print("SquidStart.py iniciado com sucesso.")
        return True
    except Exception as e:
        print(f"Erro ao iniciar o SquidStart.py: {e}")
        return False

if __name__ == "__main__":
    print("=== Script de Reinicialização do Flask ===")
    success = restart_flask()
    if success:
        print("Reinicialização concluída com sucesso.")
    else:
        print("Houve um problema durante a reinicialização.")
    print("=== Fim do Script ===") 