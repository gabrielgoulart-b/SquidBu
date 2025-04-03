# Monitor de Impressora Bambu Lab

Este projeto implementa uma página web para monitorar o status de uma impressora 3D Bambu Lab na rede local usando MQTT, com funcionalidades adicionais.

## Funcionalidades

*   **Monitoramento em Tempo Real:** Busca dados da impressora via MQTT.
*   **Interface Web:** Exibe informações organizadas:
    *   **Visão Geral:** Estado atual da impressora, sinal Wi-Fi.
    *   **Progresso:** Arquivo G-code, camada atual/total, tempo restante, barra de progresso.
    *   **Temperaturas & Ventoinhas:** Temperatura atual e alvo do bico e mesa, temperatura da câmara (se disponível), velocidade das ventoinhas.
    *   **AMS:** Detalhes de cada unidade AMS e bandeja (tipo de filamento, cor, porcentagem restante estimada).
    *   **Câmera:** Exibe o stream de vídeo da câmera da impressora (requer configuração correta do URL em `app.py` e acessibilidade da câmera).
    *   **Gráfico de Temperaturas:** Histórico das temperaturas do bico, mesa e câmara.
*   **Tema Claro/Escuro:** Botão na barra de ferramentas para alternar o tema visual, com preferência salva no navegador.
*   **Layout Responsivo:** A interface se adapta automaticamente para melhor visualização em telas de desktop e mobile.
*   **Acesso Remoto (Opcional):** Pode ser configurado via Tailscale Funnel para acesso seguro de fora da rede local.

## Estrutura

*   `app.py`: Backend Python (Flask) que conecta à impressora via MQTT, serve a API `/status` e atua como proxy para a câmera (`/camera_proxy`).
*   `templates/index.html`: Frontend HTML/CSS/JavaScript que exibe os dados, o gráfico e a câmera.
*   `requirements.txt`: Dependências Python (Flask, paho-mqtt, requests).
*   `.gitignore`: Arquivo para evitar o envio de arquivos desnecessários (como `venv`) para o Git.

## Configuração

1.  **Clone o Repositório (se obtendo do GitHub):**
    ```bash
    git clone <URL_DO_REPOSITORIO>
    cd <PASTA_DO_REPOSITORIO>
    ```

2.  **Crie o Arquivo de Configuração Local:**
    *   No diretório do projeto, copie o arquivo de exemplo:
        ```bash
        cp config.json.example config.json
        ```
    *   Edite o novo arquivo `config.json` com um editor de texto (ex: `nano config.json`).
    *   Preencha os valores corretos para as seguintes chaves, substituindo os placeholders:
        *   `PRINTER_IP`: O endereço IP da sua impressora Bambu Lab na rede local.
        *   `ACCESS_CODE`: O Código de Acesso LAN da sua impressora (encontrado nas configurações de rede dela ou no app Bambu Handy).
        *   `DEVICE_ID`: O Número de Série da sua impressora.
        *   `CAMERA_URL`: O URL completo para o stream MJPEG da sua câmera (ex: `http://192.168.X.Y:ZZZZ/?action=stream`).
    *   **Importante:** O arquivo `config.json` contém informações sensíveis e **não será enviado** ao GitHub (está no `.gitignore`).

3.  **Crie e Ative o Ambiente Virtual:**
    *   Navegue até o diretório do projeto (onde você clonou ou onde os arquivos estão).
    *   Crie o ambiente virtual (recomendado dentro de uma subpasta para ser ignorado pelo `.gitignore`, ex: `venv`):
        ```bash
        # Substitua <NOME_PASTA_VENV> pelo nome desejado (ex: venv ou printer_monitor/venv)
        python3 -m venv <NOME_PASTA_VENV>
        # Ative o ambiente virtual:
        source <NOME_PASTA_VENV>/bin/activate  # No Linux/macOS
        # <NOME_PASTA_VENV>\Scripts\activate    # No Windows
        ```
        *Nota: O script `SquidStart.py` assume que o venv está em `printer_monitor/venv`. Se você usar um nome diferente, precisará ajustar a variável `VENV_PYTHON` no início de `SquidStart.py`.* 

4.  **Instale as dependências:**
    *   Com o ambiente virtual ativo, execute:
        ```bash
        pip install -r requirements.txt
        ```

## Execução Local

1.  **Certifique-se de que `config.json` existe e está preenchido.**

2.  **Inicie o servidor backend:**
    *   Com o ambiente virtual ativo, execute:
        ```bash
        python app.py
        ```
    *   Se houver erros ao carregar `config.json`, mensagens aparecerão no terminal.

3.  **Acesse a página web:**
    *   Abra um navegador na **mesma rede local**.
    *   Acesse: `http://<IP_DO_DISPOSITIVO_RODANDO_APP>:5000` (substitua `<IP_DO_DISPOSITIVO_RODANDO_APP>` pelo IP do dispositivo que roda o app).

## Acesso Remoto (Opcional - Via Tailscale Funnel)

Para acessar o monitor de fora da sua rede local de forma segura e gratuita (sem precisar de domínio próprio), você pode usar o Tailscale Funnel.

1.  **Instale o Tailscale no dispositivo que roda o `app.py`:**
    ```bash
    curl -fsSL https://tailscale.com/install.sh | sh
    ```

2.  **Inicie o Tailscale e faça login:**
    ```bash
    sudo tailscale up
    ```
    *   Siga o link exibido para autenticar o dispositivo na sua conta Tailscale.

3.  **Habilite HTTPS para o Tailscale (necessário para Funnel):**
    ```bash
    sudo tailscale set --auto-cert
    ```

4.  **Inicie o Funnel para a porta 5000:**
    *   Certifique-se de que `python app.py` esteja rodando em outro terminal.
    *   Execute o comando Funnel (ele precisa continuar rodando):
        ```bash
        tailscale funnel 5000
        ```
    *   **Na primeira vez**, você pode precisar abrir um link no navegador para aprovar a ativação do Funnel para sua rede.
    *   O comando exibirá o URL público fixo, algo como: `https://<nome-do-host>.<seu-tailnet>.ts.net/`

5.  **Acesse Remotamente:** Use o URL `https://...ts.net` exibido em qualquer navegador, em qualquer rede.

    **Nota:** O comando `tailscale funnel 5000` precisa ficar rodando. Para rodar em segundo plano permanentemente, use a configuração de inicialização no boot descrita abaixo.

## Start on Boot (Opcional - Linux com systemd)

Para fazer o monitor e o túnel Tailscale Funnel iniciarem automaticamente quando o Raspberry Pi (ou outro sistema Linux com systemd) ligar, você pode usar o script `SquidStart.py` e um serviço systemd.

1.  **Script `SquidStart.py`:**
    *   Este script (localizado no diretório principal do projeto) é responsável por iniciar `app.py` (com o ambiente virtual correto) e `tailscale funnel 5000`.
    *   Ele também monitora os processos e tenta reiniciá-los se falharem, além de redirecionar a saída para arquivos `.log`.

2.  **Torne o Script Executável:**
    ```bash
    chmod +x SquidStart.py
    ```

3.  **Configure as Permissões do Tailscale (Recomendado):**
    *   Para permitir que o script (rodando como seu usuário) controle o `tailscale funnel` sem `sudo`, execute uma vez:
        ```bash
        # Substitua <SEU_USUARIO> pelo seu nome de usuário real
        sudo tailscale up --operator=<SEU_USUARIO>
        ```

4.  **Crie o Arquivo de Serviço Systemd:**
    *   Crie e edite o arquivo de serviço:
        ```bash
        sudo nano /etc/systemd/system/squidstart.service
        ```
    *   Cole o seguinte conteúdo no arquivo. **Importante:** Substitua os placeholders `<SEU_USUARIO>`, `<SEU_GRUPO>` e `<CAMINHO_PARA_O_PROJETO>` pelos valores corretos para o seu sistema.

        ```ini
        [Unit]
        Description=SquidBu Monitor and Tailscale Funnel Starter
        After=network.target tailscaled.service

        [Service]
        Type=simple
        User=<SEU_USUARIO>
        Group=<SEU_GRUPO>
        WorkingDirectory=<CAMINHO_PARA_O_PROJETO>
        ExecStart=<CAMINHO_PARA_O_PROJETO>/SquidStart.py
        Restart=on-failure
        RestartSec=10
        StandardOutput=journal
        StandardError=journal

        [Install]
        WantedBy=multi-user.target
        ```
    *   Salve e feche o editor (`Ctrl+X`, `Y`, `Enter`).

5.  **Habilite e Inicie o Serviço:**
    *   Recarregue a configuração do systemd:
        ```bash
        sudo systemctl daemon-reload
        ```
    *   Habilite o serviço para iniciar no boot:
        ```bash
        sudo systemctl enable squidstart.service
        ```
    *   Inicie o serviço imediatamente:
        ```bash
        sudo systemctl start squidstart.service
        ```

6.  **Verifique o Status e Logs:**
    *   Verifique se o serviço está rodando:
        ```bash
        sudo systemctl status squidstart.service
        ```
    *   Veja os logs do serviço (inclui a saída do `SquidStart.py`):
        ```bash
        journalctl -u squidstart.service -f
        ```
    *   Veja os logs específicos do Flask e Tailscale Funnel (localizados em `<CAMINHO_PARA_O_PROJETO>`):
        ```bash
        tail -f <CAMINHO_PARA_O_PROJETO>/flask_app.log
        tail -f <CAMINHO_PARA_O_PROJETO>/tailscale_funnel.log
        ```

Com estes passos, o monitor deverá iniciar automaticamente após cada reinicialização do sistema.

## Solução de Problemas

*   **Erro "Falha ao conectar ao backend" na página web:**
    *   Verifique se `app.py` está rodando e se você está acessando o IP/URL correto.
    *   Verifique o firewall local.
*   **Erro de Conexão MQTT:**
    *   Confirme os dados no arquivo `config.json`.
*   **Página exibe "Carregando..." indefinidamente:**
    *   Verifique o console do desenvolvedor do navegador (F12) por erros JavaScript.
    *   Verifique o terminal onde `app.py` roda por erros.
*   **Câmera não carrega:**
    *   Confirme se o `CAMERA_URL` em `config.json` está correto.
    *   Verifique se o servidor Flask (`app.py`) consegue acessar o URL da câmera (use `curl <CAMERA_URL>` no terminal do servidor Flask).
    *   Verifique se há erros relacionados a `/camera_proxy` no terminal do Flask ou no console do navegador.
*   **Acesso remoto (Funnel) não funciona:**
    *   Confirme se o comando `tailscale funnel 5000` está rodando sem erros.
    *   Verifique se você consegue acessar o URL `.ts.net` fornecido.
    *   Certifique-se de que `python app.py` está rodando. 