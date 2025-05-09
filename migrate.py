#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import argparse
from database import initialize_database, create_admin_user

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('migrate')

def parse_args():
    parser = argparse.ArgumentParser(description='Migração de dados para o banco de dados SQLite')
    parser.add_argument('--create-admin', action='store_true', 
                        help='Criar um novo usuário administrador')
    parser.add_argument('--username', type=str, help='Nome de usuário do admin')
    parser.add_argument('--password', type=str, help='Senha do admin')
    parser.add_argument('--email', type=str, help='Email do admin')
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    logger.info("Iniciando migração para o banco de dados SQLite...")
    
    # Inicializa o banco de dados e migra dados existentes
    success = initialize_database()
    
    if not success:
        logger.error("Falha na inicialização do banco de dados")
        sys.exit(1)
    
    # Criar novo usuário administrador se solicitado
    if args.create_admin:
        if not args.username or not args.password:
            logger.error("Nome de usuário e senha são obrigatórios para criar um admin")
            sys.exit(1)
        
        try:
            create_admin_user(args.username, args.password, args.email)
        except Exception as e:
            logger.error(f"Erro ao criar usuário admin: {str(e)}")
            sys.exit(1)
    
    logger.info("Migração concluída com sucesso!")

if __name__ == "__main__":
    main() 