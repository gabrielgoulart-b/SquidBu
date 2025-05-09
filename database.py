#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from datetime import datetime
from werkzeug.security import generate_password_hash
from models import init_db, User, PrinterStats, MaintenanceLog, PushSubscription

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('database')

# Caminho do banco de dados
DB_PATH = 'squidbu.db'

# Inicialização do banco de dados
engine, Session = init_db(DB_PATH)

def get_session():
    """Retorna uma nova sessão do banco de dados"""
    return Session()

def create_admin_user(username, password, email=None):
    """
    Cria um usuário administrador se não existir
    
    Args:
        username (str): Nome de usuário
        password (str): Senha do usuário
        email (str, optional): Email do usuário
    
    Returns:
        User: O objeto User criado ou encontrado
    """
    session = get_session()
    
    try:
        # Verifica se o usuário já existe
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            # Cria um novo usuário
            password_hash = generate_password_hash(password)
            user = User(
                username=username,
                password_hash=password_hash,
                email=email,
                is_admin=True
            )
            session.add(user)
            session.commit()
            logger.info(f"Usuário administrador '{username}' criado com sucesso")
        else:
            logger.info(f"Usuário '{username}' já existe")
        
        return user
    except Exception as e:
        session.rollback()
        logger.error(f"Erro ao criar usuário: {str(e)}")
        raise
    finally:
        session.close()

def init_printer_stats():
    """
    Inicializa as estatísticas da impressora se não existirem
    
    Returns:
        PrinterStats: O objeto PrinterStats
    """
    session = get_session()
    
    try:
        # Verifica se já existem estatísticas
        stats = session.query(PrinterStats).first()
        
        if not stats:
            # Cria novas estatísticas
            stats = PrinterStats()
            session.add(stats)
            session.commit()
            logger.info("Estatísticas da impressora inicializadas")
        
        return stats
    except Exception as e:
        session.rollback()
        logger.error(f"Erro ao inicializar estatísticas: {str(e)}")
        raise
    finally:
        session.close()

def migrate_user_from_config():
    """
    Migra o usuário do arquivo config.json para o banco de dados
    
    Returns:
        bool: True se a migração foi bem-sucedida, False caso contrário
    """
    if not os.path.exists('config.json'):
        logger.warning("Arquivo config.json não encontrado")
        return False
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        username = config.get('LOGIN_USERNAME')
        password_hash = config.get('LOGIN_PASSWORD_HASH')
        
        if not username or not password_hash:
            logger.warning("Credenciais de login não encontradas em config.json")
            return False
        
        # Criar usuário diretamente com o hash da senha existente
        session = get_session()
        
        # Verifica se o usuário já existe
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            # Cria um novo usuário com o hash existente
            user = User(
                username=username,
                password_hash=password_hash,
                is_admin=True
            )
            session.add(user)
            session.commit()
            logger.info(f"Usuário '{username}' migrado do config.json")
        else:
            logger.info(f"Usuário '{username}' já existe no banco de dados")
        
        session.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao migrar usuário do config.json: {str(e)}")
        return False

def migrate_maintenance_logs():
    """
    Migra registros de manutenção de maintenance_data.json para o banco de dados
    
    Returns:
        int: Número de registros migrados
    """
    if not os.path.exists('maintenance_data.json'):
        logger.warning("Arquivo maintenance_data.json não encontrado")
        return 0
    
    try:
        with open('maintenance_data.json', 'r') as f:
            maintenance_data = json.load(f)
        
        if not maintenance_data or not isinstance(maintenance_data, list):
            logger.warning("Formato inválido ou dados vazios em maintenance_data.json")
            return 0
        
        session = get_session()
        count = 0
        
        # Obter o usuário admin para associar aos registros
        admin = session.query(User).filter_by(is_admin=True).first()
        
        for item in maintenance_data:
            # Verifica se este registro já foi migrado (busca por timestamp)
            if 'timestamp' in item:
                timestamp = datetime.fromisoformat(item['timestamp'])
                existing = session.query(MaintenanceLog).filter_by(performed_at=timestamp).first()
                
                if existing:
                    continue
                
                log = MaintenanceLog(
                    task=item.get('task', 'Manutenção não especificada'),
                    notes=item.get('notes', ''),
                    performed_at=timestamp,
                    hours_at_log=item.get('printer_hours', 0),
                    prints_at_log=item.get('print_count', 0)
                )
                
                if admin:
                    log.user_id = admin.id
                
                session.add(log)
                count += 1
        
        if count > 0:
            session.commit()
            logger.info(f"{count} registros de manutenção migrados para o banco de dados")
        
        session.close()
        return count
    except Exception as e:
        if 'session' in locals():
            session.rollback()
            session.close()
        logger.error(f"Erro ao migrar registros de manutenção: {str(e)}")
        return 0

def migrate_push_subscriptions():
    """
    Migra assinaturas push de subscriptions.json para o banco de dados
    
    Returns:
        int: Número de assinaturas migradas
    """
    if not os.path.exists('subscriptions.json'):
        logger.warning("Arquivo subscriptions.json não encontrado")
        return 0
    
    try:
        with open('subscriptions.json', 'r') as f:
            subscriptions = json.load(f)
        
        if not subscriptions or not isinstance(subscriptions, list):
            logger.warning("Formato inválido ou dados vazios em subscriptions.json")
            return 0
        
        session = get_session()
        count = 0
        
        for sub in subscriptions:
            subscription_json = json.dumps(sub)
            
            # Verifica se esta assinatura já existe
            existing = session.query(PushSubscription).filter_by(
                subscription_json=subscription_json).first()
            
            if not existing:
                subscription = PushSubscription(
                    subscription_json=subscription_json,
                    created_at=datetime.utcnow()
                )
                session.add(subscription)
                count += 1
        
        if count > 0:
            session.commit()
            logger.info(f"{count} assinaturas push migradas para o banco de dados")
        
        session.close()
        return count
    except Exception as e:
        if 'session' in locals():
            session.rollback()
            session.close()
        logger.error(f"Erro ao migrar assinaturas push: {str(e)}")
        return 0

def initialize_database():
    """
    Inicializa o banco de dados e migra dados existentes
    
    Returns:
        bool: True se a inicialização foi bem-sucedida
    """
    try:
        # Inicializa estatísticas da impressora
        init_printer_stats()
        
        # Migra usuário do config.json
        migrate_user_from_config()
        
        # Migra registros de manutenção
        migrate_maintenance_logs()
        
        # Migra assinaturas push
        migrate_push_subscriptions()
        
        logger.info("Inicialização do banco de dados concluída com sucesso")
        return True
    except Exception as e:
        logger.error(f"Erro durante a inicialização do banco de dados: {str(e)}")
        return False

if __name__ == "__main__":
    # Se executado diretamente, inicializa o banco de dados
    initialize_database() 