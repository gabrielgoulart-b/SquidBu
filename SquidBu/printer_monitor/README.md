# Monitor de Impressora Bambu Lab

Este projeto implementa uma página web simples para monitorar o status de uma impressora 3D Bambu Lab na rede local usando MQTT.

## Estrutura

*   `app.py`: Backend Python (Flask) que conecta à impressora via MQTT e serve uma API de status.
*   `templates/index.html`: Frontend HTML/CSS/JavaScript que exibe os dados.
*   `requirements.txt`: Dependências Python.
*   `static/`: Pasta para arquivos estáticos (CSS, JS, imagens) - não utilizada neste exemplo básico.

## Configuração

1.  **Edite `app.py`:**
    *   Abra o arquivo `app.py`.
    *   Localize as linhas de configuração perto do topo:
        ```python
        PRINTER_IP = "192.168.1.XXX"  # Substitua pelo IP da sua impressora
        ACCESS_CODE = "SUA_SENHA_AQUI" # Substitua pelo seu Código de Acesso LAN
        DEVICE_ID = "SEU_NUMERO_SERIE" # Substitua pelo Número de Série da sua impressora
        ```
    *   Substitua os valores entre aspas pelos dados corretos da sua impressora Bambu Lab.
        *   Você pode encontrar o IP, o Código de Acesso LAN (Access Code) e o Número de Série (Device ID) nas configurações de rede da impressora ou no aplicativo Bambu Handy.

2.  **Instale as dependências:**
    *   Navegue até o diretório `SquidBu/printer_monitor` no seu terminal.
    *   Crie um ambiente virtual (recomendado):
        ```bash
        python3 -m venv venv
        source venv/bin/activate  # No Linux/macOS
        # venv\Scripts\activate    # No Windows
        ```
    *   Instale as bibliotecas necessárias:
        ```bash
        pip install -r requirements.txt
        ```

## Execução

1.  **Inicie o servidor backend:**
    *   Ainda no diretório `SquidBu/printer_monitor` e com o ambiente virtual ativado (se estiver usando um), execute:
        ```bash
        python app.py
        ```
    *   Você deverá ver mensagens indicando que o servidor Flask foi iniciado e que está tentando conectar ao MQTT da impressora.

2.  **Acesse a página web:**
    *   Abra um navegador web em **qualquer dispositivo na mesma rede local** que o Raspberry Pi (ou onde você estiver rodando o `app.py`).
    *   Acesse o endereço: `http://<IP_DO_RASPBERRY_PI>:5000` (substitua `<IP_DO_RASPBERRY_PI>` pelo endereço IP do dispositivo que está rodando o `app.py`).

    *   A página deverá carregar e começar a exibir os dados da impressora após alguns segundos.

## Solução de Problemas

*   **Erro "Falha ao conectar ao backend" na página web:**
    *   Verifique se o script `app.py` está em execução no terminal.
    *   Confirme se você está acessando o IP correto e a porta 5000 no navegador.
    *   Verifique se o firewall no dispositivo que roda o `app.py` permite conexões na porta 5000.
*   **Mensagens de erro no terminal sobre conexão MQTT:**
    *   Confirme se o IP da impressora, o Código de Acesso e o Número de Série em `app.py` estão corretos.
    *   Verifique se a impressora está ligada e conectada à mesma rede local.
    *   Certifique-se de que o modo LAN está habilitado nas configurações da impressora.
*   **Nenhum dado aparece na página:**
    *   Verifique o terminal onde `app.py` está rodando para mensagens de erro MQTT.
    *   Dê alguns segundos para a conexão ser estabelecida e os dados serem recebidos. 