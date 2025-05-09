#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import json
from sqlalchemy.exc import SQLAlchemyError

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('gpio_manager')

# Verificar se estamos em um Raspberry Pi e importar a biblioteca RPi.GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    # Configurar GPIO
    GPIO.setmode(GPIO.BCM)  # Usar numeração BCM
    GPIO.setwarnings(False)
    logger.info("GPIO inicializado com sucesso")
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("Biblioteca RPi.GPIO não encontrada. Executando em modo de simulação.")

from models import GpioPin
from database import get_session

class GpioManager:
    """
    Gerenciador para controlar os pinos GPIO do Raspberry Pi
    """
    
    @staticmethod
    def setup_pins():
        """
        Configura os pinos GPIO com base nas definições do banco de dados
        
        Returns:
            bool: True se configurado com sucesso, False caso contrário
        """
        if not GPIO_AVAILABLE:
            logger.warning("GPIO não disponível, ignorando configuração de pinos")
            return False
            
        session = get_session()
        try:
            pins = session.query(GpioPin).all()
            
            for pin in pins:
                pin_num = pin.pin_number
                
                if pin.is_output:
                    GPIO.setup(pin_num, GPIO.OUT)
                    GPIO.output(pin_num, pin.current_state)
                    logger.info(f"Pino {pin_num} configurado como saída, estado: {pin.current_state}")
                else:
                    GPIO.setup(pin_num, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    logger.info(f"Pino {pin_num} configurado como entrada com pull-up")
            
            return True
        except Exception as e:
            logger.error(f"Erro ao configurar pinos GPIO: {str(e)}")
            return False
        finally:
            session.close()
    
    @staticmethod
    def add_pin(pin_number, name, is_output=True, initial_state=False, description=None):
        """
        Adiciona um novo pino GPIO ao banco de dados
        
        Args:
            pin_number (int): Número do pino (BCM)
            name (str): Nome descritivo do pino
            is_output (bool, optional): Se o pino é de saída (True) ou entrada (False)
            initial_state (bool, optional): Estado inicial (para pinos de saída)
            description (str, optional): Descrição do pino
            
        Returns:
            GpioPin: Objeto GpioPin criado ou None se falhou
        """
        # Validar número do pino
        if not isinstance(pin_number, int) or pin_number < 0 or pin_number > 27:
            logger.error(f"Número de pino inválido: {pin_number}")
            return None
            
        session = get_session()
        try:
            # Verificar se o pino já existe
            existing = session.query(GpioPin).filter_by(pin_number=pin_number).first()
            
            if existing:
                logger.warning(f"Pino {pin_number} já existe no banco de dados")
                return existing
                
            pin = GpioPin(
                pin_number=pin_number,
                name=name,
                current_state=initial_state,
                is_output=is_output,
                description=description
            )
            
            session.add(pin)
            session.commit()
            
            # Configurar o pino físico se GPIO disponível
            if GPIO_AVAILABLE:
                if is_output:
                    GPIO.setup(pin_number, GPIO.OUT)
                    GPIO.output(pin_number, initial_state)
                else:
                    GPIO.setup(pin_number, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            logger.info(f"Pino {pin_number} ({name}) adicionado com sucesso")
            return pin
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao adicionar pino ao banco de dados: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def remove_pin(pin_number):
        """
        Remove um pino GPIO do banco de dados
        
        Args:
            pin_number (int): Número do pino (BCM)
            
        Returns:
            bool: True se removido com sucesso, False caso contrário
        """
        session = get_session()
        try:
            pin = session.query(GpioPin).filter_by(pin_number=pin_number).first()
            
            if not pin:
                logger.warning(f"Pino {pin_number} não encontrado")
                return False
                
            session.delete(pin)
            session.commit()
            
            # Limpar o pino físico se GPIO disponível
            if GPIO_AVAILABLE:
                GPIO.cleanup(pin_number)
                
            logger.info(f"Pino {pin_number} removido com sucesso")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao remover pino: {str(e)}")
            return False
        finally:
            session.close()
    
    @staticmethod
    def set_pin_state(pin_number, state):
        """
        Define o estado de um pino GPIO
        
        Args:
            pin_number (int): Número do pino (BCM)
            state (bool): Estado do pino (True para ligado, False para desligado)
            
        Returns:
            bool: True se definido com sucesso, False caso contrário
        """
        session = get_session()
        try:
            pin = session.query(GpioPin).filter_by(pin_number=pin_number).first()
            
            if not pin:
                logger.warning(f"Pino {pin_number} não encontrado")
                return False
                
            if not pin.is_output:
                logger.warning(f"Pino {pin_number} não é configurado como saída")
                return False
                
            # Atualizar no banco de dados
            pin.current_state = bool(state)
            session.commit()
            
            # Atualizar pino físico se GPIO disponível
            if GPIO_AVAILABLE:
                GPIO.output(pin_number, state)
                
            logger.info(f"Pino {pin_number} alterado para estado: {state}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao definir estado do pino: {str(e)}")
            return False
        finally:
            session.close()
    
    @staticmethod
    def toggle_pin(pin_number):
        """
        Inverte o estado de um pino GPIO
        
        Args:
            pin_number (int): Número do pino (BCM)
            
        Returns:
            bool: O novo estado do pino ou None se falhou
        """
        session = get_session()
        try:
            pin = session.query(GpioPin).filter_by(pin_number=pin_number).first()
            
            if not pin:
                logger.warning(f"Pino {pin_number} não encontrado")
                return None
                
            if not pin.is_output:
                logger.warning(f"Pino {pin_number} não é configurado como saída")
                return None
                
            # Inverter estado
            new_state = not pin.current_state
            
            # Atualizar no banco de dados
            pin.current_state = new_state
            session.commit()
            
            # Atualizar pino físico se GPIO disponível
            if GPIO_AVAILABLE:
                GPIO.output(pin_number, new_state)
                
            logger.info(f"Pino {pin_number} alternado para estado: {new_state}")
            return new_state
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao alternar estado do pino: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_pin_state(pin_number):
        """
        Obtém o estado atual de um pino GPIO
        
        Args:
            pin_number (int): Número do pino (BCM)
            
        Returns:
            bool: Estado do pino ou None se falhou
        """
        session = get_session()
        try:
            pin = session.query(GpioPin).filter_by(pin_number=pin_number).first()
            
            if not pin:
                logger.warning(f"Pino {pin_number} não encontrado")
                return None
                
            # Se for pino de entrada e GPIO disponível, ler o estado atual
            if not pin.is_output and GPIO_AVAILABLE:
                state = GPIO.input(pin_number)
                # Atualizar no banco de dados
                pin.current_state = state
                session.commit()
                return state
            
            return pin.current_state
        except SQLAlchemyError as e:
            logger.error(f"Erro ao obter estado do pino: {str(e)}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_all_pins():
        """
        Obtém todos os pinos GPIO configurados
        
        Returns:
            list: Lista de dicionários com informações dos pinos
        """
        session = get_session()
        try:
            pins = session.query(GpioPin).all()
            
            # Converter para lista de dicionários
            result = []
            for pin in pins:
                # Se for pino de entrada e GPIO disponível, ler o estado atual
                current_state = pin.current_state
                if not pin.is_output and GPIO_AVAILABLE:
                    try:
                        current_state = GPIO.input(pin.pin_number)
                        # Atualizar no banco de dados
                        pin.current_state = current_state
                    except Exception:
                        pass  # Ignorar erros ao ler pinos
                
                result.append({
                    'id': pin.id,
                    'pin_number': pin.pin_number,
                    'name': pin.name,
                    'current_state': current_state,
                    'is_output': pin.is_output,
                    'description': pin.description
                })
            
            session.commit()  # Salvar quaisquer atualizações de estado
            return result
        except SQLAlchemyError as e:
            logger.error(f"Erro ao obter pinos: {str(e)}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def cleanup():
        """
        Limpa todos os pinos GPIO
        
        Returns:
            bool: True se limpo com sucesso
        """
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
                logger.info("Pinos GPIO limpos com sucesso")
            except Exception as e:
                logger.error(f"Erro ao limpar pinos GPIO: {str(e)}")
                return False
        return True

# Inicializar os pinos GPIO na importação do módulo
if __name__ != "__main__":
    if GPIO_AVAILABLE:
        GpioManager.setup_pins()

# Teste simples se executado diretamente
if __name__ == "__main__":
    import time
    
    print("Testando módulo GPIO...")
    
    if not GPIO_AVAILABLE:
        print("AVISO: Executando em modo de simulação (sem hardware GPIO)")
    
    # Adicionar alguns pinos de teste
    GpioManager.add_pin(17, "LED Vermelho", True, False, "LED Vermelho de teste")
    GpioManager.add_pin(18, "LED Verde", True, False, "LED Verde de teste")
    GpioManager.add_pin(23, "Botão", False, False, "Botão de teste")
    
    # Listar pinos
    pins = GpioManager.get_all_pins()
    print("\nPinos configurados:")
    for pin in pins:
        print(f"Pino {pin['pin_number']} ({pin['name']}): {'LIGADO' if pin['current_state'] else 'DESLIGADO'}")
    
    if GPIO_AVAILABLE:
        # Piscar LEDs
        print("\nPiscando LEDs...")
        for i in range(5):
            GpioManager.set_pin_state(17, True)
            time.sleep(0.5)
            GpioManager.set_pin_state(17, False)
            GpioManager.set_pin_state(18, True)
            time.sleep(0.5)
            GpioManager.set_pin_state(18, False)
    
    # Limpar
    print("\nLimpando pinos...")
    GpioManager.cleanup() 