#!/bin/bash

# SquidBu - Script de Instalação
# Este script instala o SquidBu e configura o usuário e senha para acesso

# Cores para melhor visualização
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # Sem cor

# Função para exibir mensagens com cores
print_message() {
    echo -e "${BLUE}[SquidBu]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[Sucesso]${NC} $1"
}

print_error() {
    echo -e "${RED}[Erro]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[Aviso]${NC} $1"
}

# Verificar se está rodando como root (sudo)
if [ "$(id -u)" -ne 0 ]; then
    print_error "Este script precisa ser executado com privilégios de superusuário (sudo)."
    echo "Por favor, execute: sudo $0"
    exit 1
fi

# Verificar a versão do Python
print_message "Verificando versão do Python..."
if ! command -v python3 >/dev/null 2>&1; then
    print_error "Python 3 não está instalado. Por favor, instale o Python 3 e tente novamente."
    exit 1
fi

# Verificar a versão específica do Python
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "SquidBu requer Python 3.8 ou superior. Versão detectada: $PYTHON_VERSION"
    print_message "Por favor, atualize o Python e tente novamente."
    exit 1
fi

print_success "Versão do Python compatível detectada: $PYTHON_VERSION"

# Cabeçalho 
echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}               INSTALAÇÃO DO SQUIDBU                           ${NC}"
echo -e "${BLUE}     Monitor para Impressoras 3D Bambu Lab com ESP32           ${NC}"
echo -e "${BLUE}================================================================${NC}"
echo

# Verificar dependências do sistema
print_message "Verificando dependências do sistema..."
REQUIRED_PKGS="python3 python3-pip python3-venv mosquitto git"

# Determinar o gerenciador de pacotes
if command -v dpkg >/dev/null 2>&1; then
    # Debian, Ubuntu, etc
    CHECK_PKG_CMD="dpkg -s"
    UPDATE_CMD="apt-get update"
    INSTALL_CMD="apt-get install -y"
    
    # Verificar se é Ubuntu e adaptar comandos conforme necessário
    if grep -q "Ubuntu" /etc/os-release 2>/dev/null; then
        print_message "Detectado sistema Ubuntu."
        # Em algumas versões do Ubuntu, pode ser necessário instalar python3-venv via python3.x-venv
        # onde x é a versão específica do Python
        if ! dpkg -s python3-venv >/dev/null 2>&1; then
            PYTHON_VERSION_MAJOR_MINOR=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            print_message "Tentando instalar python${PYTHON_VERSION_MAJOR_MINOR}-venv como alternativa..."
            apt-get install -y "python${PYTHON_VERSION_MAJOR_MINOR}-venv" || true
        fi
    fi
elif command -v apt-get >/dev/null 2>&1; then
    # Outros sistemas baseados em Debian sem dpkg
    CHECK_PKG_CMD="apt-cache policy"
    UPDATE_CMD="apt-get update"
    INSTALL_CMD="apt-get install -y"
elif command -v pacman >/dev/null 2>&1; then
    # Arch Linux
    CHECK_PKG_CMD="pacman -Qi"
    UPDATE_CMD="pacman -Sy"
    INSTALL_CMD="pacman -S --noconfirm"
elif command -v dnf >/dev/null 2>&1; then
    # Fedora, CentOS, RHEL
    CHECK_PKG_CMD="rpm -q"
    UPDATE_CMD="dnf check-update || true"
    INSTALL_CMD="dnf install -y"
elif command -v yum >/dev/null 2>&1; then
    # Sistemas mais antigos Red Hat/CentOS
    CHECK_PKG_CMD="rpm -q"
    UPDATE_CMD="yum check-update || true"
    INSTALL_CMD="yum install -y"
else
    print_error "Sistema operacional não suportado ou gerenciador de pacotes não identificado."
    print_warning "Por favor, instale manualmente: $REQUIRED_PKGS"
    read -p "Deseja continuar mesmo assim? (s/n): " continue_anyway
    if [[ ! $continue_anyway =~ ^[Ss]$ ]]; then
        print_message "Instalação cancelada pelo usuário."
        exit 0
    fi
    # Vamos prosseguir mesmo sem verificar/instalar pacotes
    CHECK_PKG_CMD="echo"
    UPDATE_CMD="echo Ignorando atualização de repositórios"
    INSTALL_CMD="echo Ignorando instalação de"
fi

# Atualizar os repositórios uma única vez antes de iniciar as instalações
print_message "Atualizando repositórios de pacotes..."
$UPDATE_CMD
if [ $? -ne 0 ]; then
    print_warning "Houve um erro ao atualizar os repositórios, mas tentaremos prosseguir mesmo assim."
fi

# Instalar cada pacote individualmente para melhor tratamento de erros
for pkg in $REQUIRED_PKGS; do
    if ! $CHECK_PKG_CMD "$pkg" >/dev/null 2>&1; then
        print_warning "Pacote $pkg não encontrado. Tentando instalar..."
        $INSTALL_CMD "$pkg"
        if [ $? -ne 0 ]; then
            if [ "$pkg" = "python3-venv" ]; then
                print_warning "Falha ao instalar python3-venv. Tentando soluções alternativas..."
                
                # Para Ubuntu/Debian, tentar instalar a versão específica do Python
                if command -v apt-get >/dev/null 2>&1; then
                    PYTHON_VERSION_MAJOR_MINOR=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
                    print_message "Tentando instalar python${PYTHON_VERSION_MAJOR_MINOR}-venv..."
                    apt-get install -y "python${PYTHON_VERSION_MAJOR_MINOR}-venv"
                    if [ $? -eq 0 ]; then
                        print_success "Instalou python${PYTHON_VERSION_MAJOR_MINOR}-venv como alternativa."
                        continue
                    fi
                fi
                
                # Se ainda não conseguiu, tentar usar virtualenv como alternativa
                print_message "Tentando usar virtualenv como alternativa..."
                if ! command -v virtualenv >/dev/null 2>&1; then
                    $INSTALL_CMD python3-virtualenv || $INSTALL_CMD virtualenv || pip3 install virtualenv
                fi
                
                if command -v virtualenv >/dev/null 2>&1; then
                    print_success "Virtualenv encontrado, será usado como alternativa ao venv."
                    USE_VIRTUALENV=true
                    continue
                else
                    print_error "Não foi possível instalar nenhuma alternativa para criar ambiente virtual Python."
                    print_error "Por favor, instale python3-venv manualmente e tente novamente."
                    exit 1
                fi
            else
                print_error "Falha ao instalar $pkg. Por favor, instale manualmente e tente novamente."
                exit 1
            fi
        fi
    fi
done

print_success "Todas as dependências do sistema estão instaladas!"

# Definir o diretório de instalação
INSTALL_DIR="/opt/squidbu"
print_message "O SquidBu será instalado em: $INSTALL_DIR"

# Verificar se o diretório já existe
if [ -d "$INSTALL_DIR" ]; then
    print_warning "O diretório $INSTALL_DIR já existe."
    read -p "Deseja prosseguir e sobrescrever a instalação existente? (s/n): " overwrite
    if [[ ! $overwrite =~ ^[Ss]$ ]]; then
        print_message "Instalação cancelada pelo usuário."
        exit 0
    fi
    # Fazer backup da configuração existente se houver
    if [ -f "$INSTALL_DIR/config.json" ]; then
        backup_file="$INSTALL_DIR/config.json.backup.$(date +%Y%m%d%H%M%S)"
        cp "$INSTALL_DIR/config.json" "$backup_file"
        print_warning "Backup da configuração anterior salvo em: $backup_file"
    fi
else
    # Criar diretório de instalação
    mkdir -p "$INSTALL_DIR"
fi

# Clonar o repositório
print_message "Clonando o repositório SquidBu do GitHub..."
cd /tmp
rm -rf SquidBu  # Remover se existir
git clone https://github.com/gabrielgoulart-b/SquidBu.git
if [ $? -ne 0 ]; then
    print_error "Falha ao clonar o repositório. Verifique sua conexão com a internet."
    exit 1
fi

# Copiar arquivos para o diretório de instalação
print_message "Copiando arquivos para $INSTALL_DIR..."
cp -r /tmp/SquidBu/* "$INSTALL_DIR/"
if [ $? -ne 0 ]; then
    print_error "Falha ao copiar arquivos para o diretório de instalação."
    exit 1
fi

# Criar ambiente virtual Python
print_message "Criando ambiente virtual Python..."
cd "$INSTALL_DIR"

if [ "${USE_VIRTUALENV:-false}" = true ]; then
    # Usar virtualenv se venv não estiver disponível
    virtualenv venv
else
    # Método padrão com venv
    python3 -m venv venv
fi

if [ $? -ne 0 ]; then
    print_error "Falha ao criar ambiente virtual Python."
    print_message "Tentando método alternativo..."
    
    # Tentar método alternativo
    python3 -m pip install --user virtualenv
    if command -v virtualenv >/dev/null 2>&1; then
        virtualenv venv
    else
        print_error "Todos os métodos para criar um ambiente virtual falharam."
        exit 1
    fi
fi

# Instalar dependências Python
print_message "Instalando dependências Python..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r requirements.txt
if [ $? -ne 0 ]; then
    print_error "Falha ao instalar dependências Python."
    exit 1
fi

# Configurar usuário e senha para acesso ao SquidBu
print_message "Agora vamos configurar seu acesso ao SquidBu"
echo

# Gerar uma chave secreta aleatória
SECRET_KEY=$(openssl rand -hex 16)
print_success "Chave secreta gerada automaticamente."

# Solicitar dados de usuário e senha
read -p "Digite o nome de usuário para acesso ao SquidBu: " USERNAME
while [ -z "$USERNAME" ]; do
    print_error "O nome de usuário não pode estar vazio."
    read -p "Digite o nome de usuário para acesso ao SquidBu: " USERNAME
done

# Solicitar e confirmar senha
while true; do
    read -s -p "Digite a senha para o usuário $USERNAME: " PASSWORD
    echo
    if [ -z "$PASSWORD" ]; then
        print_error "A senha não pode estar vazia."
        continue
    fi
    
    read -s -p "Confirme a senha: " PASSWORD2
    echo
    
    if [ "$PASSWORD" = "$PASSWORD2" ]; then
        break
    else
        print_error "As senhas não coincidem. Tente novamente."
    fi
done

# Gerar hash da senha
PASSWORD_HASH=$("$INSTALL_DIR/venv/bin/python3" -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('$PASSWORD'))")
if [ $? -ne 0 ] || [ -z "$PASSWORD_HASH" ]; then
    print_error "Falha ao gerar o hash da senha."
    exit 1
fi

print_success "Credenciais configuradas com sucesso!"

# Solicitar informações da impressora Bambu Lab
echo
print_message "Agora vamos configurar sua impressora Bambu Lab"

read -p "Digite o endereço IP da impressora (ex: 192.168.1.100): " PRINTER_IP
while [ -z "$PRINTER_IP" ]; do
    print_error "O endereço IP não pode estar vazio."
    read -p "Digite o endereço IP da impressora: " PRINTER_IP
done

read -p "Digite o código de acesso da impressora (encontrado nas configurações de rede): " ACCESS_CODE
while [ -z "$ACCESS_CODE" ]; do
    print_error "O código de acesso não pode estar vazio."
    read -p "Digite o código de acesso da impressora: " ACCESS_CODE
done

read -p "Digite o ID do dispositivo da impressora (ex: 0123456789ABCDEF): " DEVICE_ID
while [ -z "$DEVICE_ID" ]; do
    print_error "O ID do dispositivo não pode estar vazio."
    read -p "Digite o ID do dispositivo da impressora: " DEVICE_ID
done

# Solicitar URL da câmera (opcional)
read -p "Digite a URL da câmera (opcional, deixe em branco para usar a câmera da impressora): " CAMERA_URL
if [ -z "$CAMERA_URL" ]; then
    # Usando o IP da impressora para a URL da câmera padrão
    CAMERA_URL="http://$PRINTER_IP:8080/?action=stream"
    print_message "Usando URL de câmera padrão: $CAMERA_URL"
fi

# Criar arquivo de configuração
print_message "Criando arquivo de configuração..."
cat > "$INSTALL_DIR/config.json" << EOF
{
    "PRINTER_IP": "$PRINTER_IP",
    "ACCESS_CODE": "$ACCESS_CODE",
    "DEVICE_ID": "$DEVICE_ID",
    "CAMERA_URL": "$CAMERA_URL",
    "SECRET_KEY": "$SECRET_KEY",
    "LOGIN_USERNAME": "$USERNAME",
    "LOGIN_PASSWORD_HASH": "$PASSWORD_HASH",
    "MQTT_HOST": "localhost",
    "MQTT_PORT": 1883
}
EOF

# Verificar se o serviço Mosquitto está ativo
print_message "Verificando serviço MQTT (Mosquitto)..."

# Verificar se o sistema usa systemd
if command -v systemctl >/dev/null 2>&1; then
    # Sistema usa systemd
    USING_SYSTEMD=true
    if ! systemctl is-active --quiet mosquitto; then
        print_warning "O serviço Mosquitto não está rodando. Tentando iniciar..."
        systemctl enable mosquitto
        systemctl start mosquitto
        if ! systemctl is-active --quiet mosquitto; then
            print_error "Não foi possível iniciar o Mosquitto. Por favor, verifique a instalação manualmente."
        else
            print_success "Serviço Mosquitto iniciado com sucesso!"
        fi
    else
        print_success "Serviço Mosquitto já está rodando."
    fi
else
    # Sistema não usa systemd, tentar outros métodos
    USING_SYSTEMD=false
    if command -v service >/dev/null 2>&1; then
        print_warning "Sistema não usa systemd. Tentando iniciar com o comando service..."
        service mosquitto start
        if [ $? -ne 0 ]; then
            print_error "Não foi possível iniciar o Mosquitto. Tentando outra abordagem..."
            if pgrep mosquitto >/dev/null 2>&1; then
                print_success "Mosquitto já está em execução!"
            else
                print_warning "Tentando iniciar o Mosquitto diretamente..."
                mosquitto -d
                if [ $? -ne 0 ]; then
                    print_error "Falha ao iniciar o Mosquitto. Por favor, inicie-o manualmente."
                else
                    print_success "Mosquitto iniciado em segundo plano."
                fi
            fi
        else
            print_success "Serviço Mosquitto iniciado com sucesso!"
        fi
    else
        print_warning "Sistema não usa systemd nem possui o comando service."
        if pgrep mosquitto >/dev/null 2>&1; then
            print_success "Mosquitto já está em execução!"
        else
            print_warning "Tentando iniciar o Mosquitto diretamente..."
            mosquitto -d
            if [ $? -ne 0 ]; then
                print_error "Falha ao iniciar o Mosquitto. Por favor, inicie-o manualmente."
            else
                print_success "Mosquitto iniciado em segundo plano."
            fi
        fi
    fi
fi

# Criar serviço do sistema para o SquidBu
print_message "Configurando serviço do sistema..."

if [ "$USING_SYSTEMD" = true ]; then
    # Criar unidade systemd
    cat > /etc/systemd/system/squidbu.service << EOF
[Unit]
Description=SquidBu - Monitor para Impressoras 3D Bambu Lab
After=network.target mosquitto.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/SquidStart.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    # Habilitar e iniciar o serviço
    print_message "Ativando e iniciando serviço SquidBu..."
    systemctl daemon-reload
    systemctl enable squidbu.service
    systemctl start squidbu.service

    if ! systemctl is-active --quiet squidbu.service; then
        print_error "Não foi possível iniciar o serviço SquidBu. Por favor, verifique os logs com: journalctl -u squidbu.service"
    else
        print_success "Serviço SquidBu iniciado com sucesso!"
    fi
    
    # Instruções para controle do serviço
    SERVICE_CONTROL="
  sudo systemctl start squidbu   # Iniciar
  sudo systemctl stop squidbu    # Parar
  sudo systemctl restart squidbu # Reiniciar
  sudo systemctl status squidbu  # Verificar status"
    
    LOG_COMMAND="sudo journalctl -u squidbu -f"
else
    # Criar script de inicialização para sistemas sem systemd
    print_message "Sistema não usa systemd, criando script de inicialização alternativo..."
    
    cat > "$INSTALL_DIR/start_squidbu.sh" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
"$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/SquidStart.py" >> "$INSTALL_DIR/squidbu.log" 2>&1 &
echo \$! > "$INSTALL_DIR/squidbu.pid"
echo "SquidBu iniciado com PID: \$(cat "$INSTALL_DIR/squidbu.pid")"
EOF

    cat > "$INSTALL_DIR/stop_squidbu.sh" << EOF
#!/bin/bash
if [ -f "$INSTALL_DIR/squidbu.pid" ]; then
    PID=\$(cat "$INSTALL_DIR/squidbu.pid")
    if ps -p \$PID > /dev/null; then
        echo "Parando SquidBu (PID: \$PID)..."
        kill \$PID
        rm "$INSTALL_DIR/squidbu.pid"
        echo "SquidBu parado."
    else
        echo "SquidBu não está rodando com PID \$PID."
        rm "$INSTALL_DIR/squidbu.pid"
    fi
else
    echo "Arquivo PID não encontrado. SquidBu não está rodando."
fi
EOF

    chmod +x "$INSTALL_DIR/start_squidbu.sh"
    chmod +x "$INSTALL_DIR/stop_squidbu.sh"
    
    # Iniciar o serviço
    print_message "Iniciando SquidBu..."
    "$INSTALL_DIR/start_squidbu.sh"
    
    # Adicionar ao rc.local para iniciar no boot
    if [ -f "/etc/rc.local" ]; then
        # Verificar se o script já está no rc.local
        if ! grep -q "start_squidbu.sh" /etc/rc.local; then
            # Adicionar antes da linha "exit 0" se existir
            if grep -q "^exit 0" /etc/rc.local; then
                sed -i "/^exit 0/i $INSTALL_DIR/start_squidbu.sh" /etc/rc.local
            else
                # Adicionar ao final do arquivo
                echo "$INSTALL_DIR/start_squidbu.sh" >> /etc/rc.local
            fi
            print_success "SquidBu configurado para iniciar automaticamente no boot."
        fi
    else
        # Criar um novo rc.local
        cat > /etc/rc.local << EOF
#!/bin/sh -e
#
# rc.local
#
# Este script é executado no final de cada nível multiusuário.
# Certifique-se de que o script retornará 0 no sucesso ou outro valor no erro.

$INSTALL_DIR/start_squidbu.sh

exit 0
EOF
        chmod +x /etc/rc.local
        print_success "Arquivo rc.local criado e SquidBu configurado para iniciar automaticamente no boot."
    fi
    
    # Instruções para controle do serviço
    SERVICE_CONTROL="
  sudo $INSTALL_DIR/start_squidbu.sh  # Iniciar
  sudo $INSTALL_DIR/stop_squidbu.sh   # Parar
  sudo $INSTALL_DIR/stop_squidbu.sh && sudo $INSTALL_DIR/start_squidbu.sh  # Reiniciar
  cat $INSTALL_DIR/squidbu.pid &>/dev/null && echo 'SquidBu está rodando' || echo 'SquidBu não está rodando'  # Verificar status"
    
    LOG_COMMAND="tail -f $INSTALL_DIR/squidbu.log"
fi

# Configurar permissões corretas
chown -R root:root "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# Instalação concluída
echo
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}           INSTALAÇÃO DO SQUIDBU CONCLUÍDA                     ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo
print_message "O SquidBu está agora instalado e rodando como um serviço."
# Obter o endereço IP de forma mais compatível
IP_ADDRESS=""
if command -v hostname >/dev/null 2>&1 && hostname -I >/dev/null 2>&1; then
    IP_ADDRESS=$(hostname -I | awk '{print $1}')
elif command -v ip >/dev/null 2>&1; then
    IP_ADDRESS=$(ip -4 addr show scope global | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
elif command -v ifconfig >/dev/null 2>&1; then
    IP_ADDRESS=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1)
fi

if [ -z "$IP_ADDRESS" ]; then
    IP_ADDRESS="seu_endereco_ip"
    print_warning "Não foi possível determinar o endereço IP automaticamente."
fi

print_message "Acesse o painel de controle em: http://$IP_ADDRESS:5000"
print_message "Use as credenciais que você configurou:"
echo -e "  Usuário: ${YELLOW}$USERNAME${NC}"
echo -e "  Senha: ${YELLOW}********${NC}"
echo
print_message "Para controlar o serviço SquidBu, use os comandos:"
echo -e "$SERVICE_CONTROL"
echo
print_message "Os logs podem ser visualizados com:"
echo "  $LOG_COMMAND"
echo
print_message "Arquivos de configuração:"
echo "  $INSTALL_DIR/config.json"
echo

exit 0 