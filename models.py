#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

# Configuração base do SQLAlchemy
Base = declarative_base()

# Definição dos modelos
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    email = Column(String(100))
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    print_jobs = relationship("PrintJob", back_populates="user")
    maintenance_logs = relationship("MaintenanceLog", back_populates="user")
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}', admin={self.is_admin})>"


class PrintJob(Base):
    __tablename__ = 'print_jobs'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_minutes = Column(Integer)
    status = Column(String(50))
    result_code = Column(Integer)
    filament_used_grams = Column(Float)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    # Relacionamentos
    user = relationship("User", back_populates="print_jobs")
    
    def __repr__(self):
        return f"<PrintJob(filename='{self.filename}', status='{self.status}')>"


class PrinterStats(Base):
    __tablename__ = 'printer_stats'
    
    id = Column(Integer, primary_key=True)
    total_print_hours = Column(Float, default=0)
    total_prints = Column(Integer, default=0)
    power_on_hours = Column(Float, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<PrinterStats(prints={self.total_prints}, hours={self.total_print_hours})>"


class MaintenanceLog(Base):
    __tablename__ = 'maintenance_logs'
    
    id = Column(Integer, primary_key=True)
    task = Column(String(100), nullable=False)
    notes = Column(Text)
    performed_at = Column(DateTime, default=datetime.utcnow)
    hours_at_log = Column(Float)
    prints_at_log = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    # Relacionamentos
    user = relationship("User", back_populates="maintenance_logs")
    
    def __repr__(self):
        return f"<MaintenanceLog(task='{self.task}', performed_at='{self.performed_at}')>"


class SensorData(Base):
    __tablename__ = 'sensor_data'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), nullable=False)
    temperature = Column(Float)
    humidity = Column(Float)
    ams_slot = Column(Integer)
    ams_filament_type = Column(String(50))
    ams_filament_remaining = Column(Float)
    
    def __repr__(self):
        return f"<SensorData(source='{self.source}', temperature={self.temperature}, humidity={self.humidity})>"


class GpioPin(Base):
    __tablename__ = 'gpio_pins'
    
    id = Column(Integer, primary_key=True)
    pin_number = Column(Integer, nullable=False)
    name = Column(String(50), nullable=False)
    current_state = Column(Boolean, default=False)
    is_output = Column(Boolean, default=True)
    description = Column(String(255))
    
    def __repr__(self):
        return f"<GpioPin(pin={self.pin_number}, name='{self.name}', state={self.current_state})>"


class PushSubscription(Base):
    __tablename__ = 'push_subscriptions'
    
    id = Column(Integer, primary_key=True)
    subscription_json = Column(Text, nullable=False)
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    def __repr__(self):
        return f"<PushSubscription(id={self.id}, created_at='{self.created_at}')>"


# Função para inicializar o banco de dados
def init_db(db_path='squidbu.db'):
    """
    Inicializa o banco de dados e retorna o engine e uma sessão
    
    Args:
        db_path (str): Caminho para o arquivo de banco de dados SQLite
        
    Returns:
        tuple: (engine, Session)
    """
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return engine, Session 