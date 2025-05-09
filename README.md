# SquidBu - Monitor para Impressoras 3D Bambu Lab

SquidBu é um sistema de monitoramento para impressoras 3D Bambu Lab que permite visualizar o status da impressão, controlar funções da impressora e monitorar o ambiente das caixas de filamento através de sensores ESP32.

## Funcionalidades

- **Monitoramento em Tempo Real**: Acompanhe temperatura, progresso da impressão e status do AMS
- **Controle Remoto**: Pause, retome ou interrompa impressões, controle LEDs e ajuste velocidades de ventiladores
- **Monitoramento Ambiental**: Acompanhe temperatura e umidade das caixas de filamento via sensores ESP32
- **Controle de Filamento**: Visualize o peso restante do filamento em cada compartimento
- **Acesso Remoto Seguro**: Utilize Tailscale para acesso remoto seguro
- **Notificações**: Receba alertas sobre término de impressão e outros eventos

## Requisitos

- Raspberry Pi (testado em Pi 3 e Pi 4) ou computador Linux
- Impressora 3D Bambu Lab (X1/X1C, P1P/P1S ou A1/A1 Mini)
- Opcional: ESP32 para monitoramento ambiental dos compartimentos de filamento

## Instalação

### Método Automático (Recomendado)

Use nosso script de instalação automática que configura todo o sistema, incluindo usuário e senha:

```bash
# Baixe o script de instalação
wget https://raw.githubusercontent.com/gabrielgoulart-b/SquidBu/main/install_squidbu.sh

# Dê permissão de execução
chmod +x install_squidbu.sh

# Execute o instalador (requer privilégios de superusuário)
sudo ./install_squidbu.sh
```

O instalador irá:
1. Verificar e instalar todas as dependências necessárias
2. Configurar usuário e senha para acesso seguro
3. Configurar conexão com sua impressora Bambu Lab
4. Instalar e configurar o servidor MQTT para comunicação com ESP32
5. Criar um serviço do sistema para inicialização automática

### Instalação Manual

Se preferir instalar manualmente:

```bash
# Clone o repositório
git clone https://github.com/gabrielgoulart-b/SquidBu.git
cd SquidBu

# Instale as dependências
pip install -r requirements.txt

# Configure seu ambiente
cp config.json.example config.json
# Edite config.json com os dados da sua impressora

# Inicie o servidor
python3 SquidStart.py
```

## Configuração do ESP32

Consulte o arquivo `LEIAME_AMS_DISPLAY.md` para instruções detalhadas sobre como configurar o monitoramento de filamento com ESP32.

## Configuração MQTT 

Para detalhes sobre a configuração MQTT, veja o arquivo `README_MQTT.md`.

## Licença

Este projeto é distribuído sob a licença MIT.

## Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou enviar pull requests. 