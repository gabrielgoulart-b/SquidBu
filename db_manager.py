#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from werkzeug.security import check_password_hash
from sqlalchemy.exc import SQLAlchemyError

from models import User, PrintJob, PrinterStats, MaintenanceLog, SensorData, PushSubscription
from database import get_session

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_manager')

# Classes para gerenciar entidades no banco de dados

class UserManager:
    @staticmethod
    def get_user_by_username(username):
        """
        Busca um usuário pelo nome de usuário
        
        Args:
            username (str): Nome de usuário
            
        Returns:
            User: Objeto User ou None se não encontrado
        """
        session = get_session()
        try:
            return session.query(User).filter_by(username=username).first()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar usuário: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_user_by_id(user_id):
        """
        Busca um usuário pelo ID
        
        Args:
            user_id (int): ID do usuário
            
        Returns:
            User: Objeto User ou None se não encontrado
        """
        session = get_session()
        try:
            return session.query(User).filter_by(id=user_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar usuário por ID: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def validate_login(username, password):
        """
        Valida as credenciais de login
        
        Args:
            username (str): Nome de usuário
            password (str): Senha em texto puro
            
        Returns:
            User: Objeto User se autenticado ou None se não
        """
        user = UserManager.get_user_by_username(username)
        
        if user and check_password_hash(user.password_hash, password):
            return user
        
        return None
    
    @staticmethod
    def get_all_users():
        """
        Retorna todos os usuários
        
        Returns:
            list: Lista de objetos User
        """
        session = get_session()
        try:
            return session.query(User).all()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar usuários: {str(e)}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def create_user(username, password_hash, email=None, is_admin=False):
        """
        Cria um novo usuário
        
        Args:
            username (str): Nome de usuário
            password_hash (str): Hash da senha
            email (str, optional): Email do usuário
            is_admin (bool, optional): Se o usuário é administrador
            
        Returns:
            User: Objeto User criado ou None se falhou
        """
        session = get_session()
        try:
            user = User(
                username=username,
                password_hash=password_hash,
                email=email,
                is_admin=is_admin
            )
            session.add(user)
            session.commit()
            return user
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao criar usuário: {str(e)}")
            return None
        finally:
            session.close()


class PrintJobManager:
    @staticmethod
    def record_print_start(filename, user_id=None):
        """
        Registra o início de uma impressão
        
        Args:
            filename (str): Nome do arquivo sendo impresso
            user_id (int, optional): ID do usuário que iniciou a impressão
            
        Returns:
            PrintJob: Objeto PrintJob criado ou None se falhou
        """
        session = get_session()
        try:
            # Verificar se já existe um trabalho não finalizado para este arquivo
            existing_job = session.query(PrintJob).filter_by(
                filename=filename, 
                end_time=None
            ).first()
            
            if existing_job:
                logger.info(f"Trabalho existente para {filename}, reutilizando")
                return existing_job
            
            # Criar novo trabalho
            job = PrintJob(
                filename=filename,
                start_time=datetime.utcnow(),
                status="PRINTING",
                user_id=user_id
            )
            session.add(job)
            
            # Atualizar estatísticas
            stats = session.query(PrinterStats).first()
            if stats:
                stats.total_prints += 1
                stats.last_updated = datetime.utcnow()
            
            session.commit()
            return job
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao registrar início da impressão: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def record_print_end(filename, status, filament_used=None):
        """
        Registra o fim de uma impressão
        
        Args:
            filename (str): Nome do arquivo sendo impresso
            status (str): Status final da impressão (FINISHED, FAILED, etc)
            filament_used (float, optional): Quantidade de filamento usado em gramas
            
        Returns:
            PrintJob: Objeto PrintJob atualizado ou None se falhou
        """
        session = get_session()
        try:
            # Buscar trabalho em andamento
            job = session.query(PrintJob).filter_by(
                filename=filename,
                end_time=None
            ).first()
            
            if not job:
                logger.warning(f"Nenhum trabalho em andamento encontrado para {filename}")
                return None
            
            # Atualizar trabalho
            now = datetime.utcnow()
            job.end_time = now
            job.status = status
            
            if job.start_time:
                delta = now - job.start_time
                job.duration_minutes = int(delta.total_seconds() / 60)
            
            if filament_used:
                job.filament_used_grams = filament_used
            
            # Atualizar estatísticas
            stats = session.query(PrinterStats).first()
            if stats and job.duration_minutes:
                stats.total_print_hours += (job.duration_minutes / 60)
                stats.last_updated = now
            
            session.commit()
            return job
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao registrar fim da impressão: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_recent_jobs(limit=10):
        """
        Retorna os trabalhos de impressão mais recentes
        
        Args:
            limit (int, optional): Número máximo de trabalhos a retornar
            
        Returns:
            list: Lista de objetos PrintJob
        """
        session = get_session()
        try:
            return session.query(PrintJob).order_by(
                PrintJob.start_time.desc()
            ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar trabalhos recentes: {str(e)}")
            return []
        finally:
            session.close()


class StatsManager:
    @staticmethod
    def get_printer_stats():
        """
        Retorna as estatísticas da impressora
        
        Returns:
            PrinterStats: Objeto PrinterStats ou None se não encontrado
        """
        session = get_session()
        try:
            return session.query(PrinterStats).first()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar estatísticas: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def update_power_on_hours(hours):
        """
        Atualiza as horas de funcionamento da impressora
        
        Args:
            hours (float): Horas de funcionamento
            
        Returns:
            bool: True se atualizado com sucesso, False caso contrário
        """
        session = get_session()
        try:
            stats = session.query(PrinterStats).first()
            
            if not stats:
                logger.warning("Estatísticas não encontradas, criando um novo registro")
                stats = PrinterStats(power_on_hours=hours)
                session.add(stats)
            else:
                stats.power_on_hours = hours
                stats.last_updated = datetime.utcnow()
            
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao atualizar horas de funcionamento: {str(e)}")
            return False
        finally:
            session.close()
            
    @staticmethod
    def update_printer_stats(hours=None, prints=None, print_hours=None, power_on_hours=None):
        """
        Atualiza as estatísticas da impressora
        
        Args:
            hours (float, optional): Total de horas de impressão (alias para print_hours)
            prints (int, optional): Total de impressões realizadas
            print_hours (float, optional): Total de horas de impressão
            power_on_hours (float, optional): Horas ligada (uptime)
            
        Returns:
            bool: True se atualizado com sucesso, False caso contrário
        """
        session = get_session()
        try:
            stats = session.query(PrinterStats).first()
            
            if not stats:
                logger.warning("Estatísticas não encontradas, criando um novo registro")
                stats = PrinterStats()
                session.add(stats)
            
            # Permitir 'hours' como alias para 'print_hours' para compatibilidade
            if hours is not None and print_hours is None:
                print_hours = hours
            
            # Atualizar somente os campos fornecidos
            if print_hours is not None:
                stats.total_print_hours = float(print_hours)
            
            if prints is not None:
                stats.total_prints = int(prints)
                
            if power_on_hours is not None:
                stats.power_on_hours = float(power_on_hours)
                
            stats.last_updated = datetime.utcnow()
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao atualizar estatísticas da impressora: {str(e)}")
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Erro geral ao atualizar estatísticas: {str(e)}")
            return False
        finally:
            session.close()


class MaintenanceManager:
    @staticmethod
    def add_maintenance_log(task, notes=None, user_id=None):
        """
        Adiciona um novo registro de manutenção
        
        Args:
            task (str): Tarefa de manutenção realizada
            notes (str, optional): Notas adicionais
            user_id (int, optional): ID do usuário que realizou a manutenção
            
        Returns:
            MaintenanceLog: Objeto MaintenanceLog criado ou None se falhou
        """
        session = get_session()
        try:
            # Obter estatísticas para registrar horas/impressões
            stats = session.query(PrinterStats).first()
            hours = stats.power_on_hours if stats else 0
            prints = stats.total_prints if stats else 0
            
            log = MaintenanceLog(
                task=task,
                notes=notes,
                performed_at=datetime.utcnow(),
                hours_at_log=hours,
                prints_at_log=prints,
                user_id=user_id
            )
            
            session.add(log)
            session.commit()
            return log
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao adicionar registro de manutenção: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_maintenance_logs(limit=None):
        """
        Retorna os registros de manutenção
        
        Args:
            limit (int, optional): Número máximo de registros a retornar
            
        Returns:
            list: Lista de objetos MaintenanceLog
        """
        session = get_session()
        try:
            query = session.query(MaintenanceLog).order_by(
                MaintenanceLog.performed_at.desc()
            )
            
            if limit:
                query = query.limit(limit)
                
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar registros de manutenção: {str(e)}")
            return []
        finally:
            session.close()


class SensorManager:
    @staticmethod
    def record_sensor_data(source, temperature=None, humidity=None, 
                          ams_slot=None, ams_filament_type=None, 
                          ams_filament_remaining=None):
        """
        Registra dados de sensores
        
        Args:
            source (str): Fonte dos dados (ex: "ESP32", "PRINTER")
            temperature (float, optional): Temperatura
            humidity (float, optional): Umidade
            ams_slot (int, optional): Slot AMS
            ams_filament_type (str, optional): Tipo do filamento
            ams_filament_remaining (float, optional): Porcentagem restante
            
        Returns:
            SensorData: Objeto SensorData criado ou None se falhou
        """
        session = get_session()
        try:
            sensor_data = SensorData(
                source=source,
                timestamp=datetime.utcnow(),
                temperature=temperature,
                humidity=humidity,
                ams_slot=ams_slot,
                ams_filament_type=ams_filament_type,
                ams_filament_remaining=ams_filament_remaining
            )
            
            session.add(sensor_data)
            session.commit()
            return sensor_data
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao registrar dados de sensores: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_recent_sensor_data(source=None, limit=100):
        """
        Retorna dados de sensores recentes
        
        Args:
            source (str, optional): Filtrar por fonte
            limit (int, optional): Número máximo de registros
            
        Returns:
            list: Lista de objetos SensorData
        """
        session = get_session()
        try:
            query = session.query(SensorData).order_by(
                SensorData.timestamp.desc()
            )
            
            if source:
                query = query.filter_by(source=source)
                
            return query.limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar dados de sensores: {str(e)}")
            return []
        finally:
            session.close()


class PushManager:
    @staticmethod
    def save_subscription(subscription_json, user_agent=None, user_id=None):
        """
        Salva uma assinatura push
        
        Args:
            subscription_json (str): JSON da assinatura
            user_agent (str, optional): User agent do navegador
            user_id (int, optional): ID do usuário
            
        Returns:
            PushSubscription: Objeto PushSubscription criado ou None se falhou
        """
        session = get_session()
        try:
            # Verificar se já existe
            if isinstance(subscription_json, dict):
                subscription_json = json.dumps(subscription_json)
                
            existing = session.query(PushSubscription).filter_by(
                subscription_json=subscription_json
            ).first()
            
            if existing:
                existing.last_used = datetime.utcnow()
                existing.user_agent = user_agent or existing.user_agent
                existing.user_id = user_id or existing.user_id
                session.commit()
                return existing
            
            # Criar nova assinatura
            subscription = PushSubscription(
                subscription_json=subscription_json,
                user_agent=user_agent,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow(),
                user_id=user_id
            )
            
            session.add(subscription)
            session.commit()
            return subscription
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao salvar assinatura push: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_all_subscriptions():
        """
        Retorna todas as assinaturas push
        
        Returns:
            list: Lista de objetos PushSubscription
        """
        session = get_session()
        try:
            return session.query(PushSubscription).all()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar assinaturas push: {str(e)}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def delete_subscription(subscription_json):
        """
        Remove uma assinatura push
        
        Args:
            subscription_json (str): JSON da assinatura
            
        Returns:
            bool: True se removido com sucesso, False caso contrário
        """
        session = get_session()
        try:
            if isinstance(subscription_json, dict):
                subscription_json = json.dumps(subscription_json)
                
            subscription = session.query(PushSubscription).filter_by(
                subscription_json=subscription_json
            ).first()
            
            if subscription:
                session.delete(subscription)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao remover assinatura push: {str(e)}")
            return False
        finally:
            session.close() 