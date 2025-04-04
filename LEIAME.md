# Monitor de Impressora Bambu Lab

Este projeto implementa uma página web para monitorar o status de uma impressora 3D Bambu Lab na rede local usando MQTT, com funcionalidades adicionais, incluindo autenticação e compartilhamento.

## Funcionalidades

*   **Monitoramento em Tempo Real:** Busca dados da impressora via MQTT.
*   **Interface Web:** Exibe informações organizadas:
    *   **Visão Geral:** Estado atual da impressora, sinal Wi-Fi.
    *   **Progresso:** Arquivo G-code, camada atual/total, tempo restante, barra de progresso.
    *   **Temperaturas & Ventoinhas:** Temperatura atual e alvo do bico e mesa, temperatura da câmara (se disponível), velocidade das ventoinhas.
    *   **AMS:** Detalhes de cada unidade AMS e bandeja (tipo de filamento, cor, porcentagem restante estimada). *(Nota: A interface agora tenta ler dados do array `stg` para melhor compatibilidade com AMS Lite).*
    *   **Câmera:** Exibe o stream de vídeo da câmera. Requer uma câmera USB conectada ao dispositivo que roda o app e a configuração do MJPG-Streamer (veja abaixo) ou outra fonte MJPEG acessível via URL.
    *   **Gráfico de Temperaturas:** Histórico das temperaturas do bico, mesa e câmara.
*   **Autenticação de Usuário:** Sistema de login com nome de usuário e senha para proteger o acesso à interface principal. Inclui opção "Lembrar-me".
*   **Visualização Ao Vivo Compartilhável:** Uma URL especial (`/live/<token>`) permite compartilhar uma visualização simplificada (progresso e câmera) sem login, protegida por um token secreto. Agora inclui um botão "🔗 Compartilhar" na barra superior para facilitar a cópia/envio do link.
*   **Notificações Push:** Receba notificações no seu navegador ou celular sobre eventos importantes da impressão (início, fim, erro/pausa) usando Web Push. Requer configuração (veja abaixo).
*   **Tema Claro/Escuro:** Botão na barra de ferramentas para alternar o tema visual, com preferência salva no navegador.
*   **Layout Responsivo:** A interface se adapta automaticamente para melhor visualização em telas de desktop e mobile (com barra lateral retrátil em mobile).
*   **Acesso Remoto (Opcional):** Pode ser configurado via Tailscale Funnel para acesso seguro de fora da rede local.

## Estrutura

*   `app.py`: Backend Python (Flask) que:
    *   Conecta à impressora via MQTT.
    *   Implementa autenticação de usuário (login/logout) usando Flask-Login.
    *   Serve a interface principal (`/`), a página de login (`/login`) e a visualização ao vivo (`/live/<token>`).
    *   Serve a API `/status`.
    *   Atua como proxy para a câmera (`/camera_proxy`).
*   `templates/index.html`: Frontend principal (requer login).
*   `templates/login.html`: Página de login.
*   `templates/live_view.html`: Página simplificada para visualização ao vivo compartilhada.
*   `static/css/style.css`: Folha de estilos principal.
*   `static/js/script.js`: JavaScript para a interface principal (atualização de dados, temas, compartilhamento, etc.).
*   `static/js/notifications.js`: JavaScript para gerenciar notificações push.
*   `static/js/service-worker.js`: Service Worker para receber notificações push.
*   `config.json`: Arquivo de configuração local (NÃO versionado).
*   `config.json.example`: Exemplo do arquivo de configuração.
*   `requirements.txt`: Dependências Python (Flask, paho-mqtt, requests, Flask-Login, Flask-WTF, pywebpush).
*   `SquidStart.py`: Script (opcional) para iniciar e monitorar `app.py` e `tailscale funnel` no boot via systemd.
*   `.gitignore`: Arquivo para evitar o envio de arquivos desnecessários (como `venv`, `config.json`, logs) para o Git.

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
        *   `CAMERA_URL`: A URL para o stream MJPEG. 
            *   Se usar MJPG-Streamer rodando localmente (veja passo 5), use algo como `http://127.0.0.1:8080/?action=stream` (ajuste a porta se necessário).
            *   Se usar outra fonte (câmera IP, stream da própria Bambu se acessível), coloque a URL direta.
            *   Se não for usar, pode deixar o valor de exemplo.
        *   `SECRET_KEY`: Uma chave secreta longa e aleatória para segurança da sessão Flask. **Importante:** Gere uma chave segura! Você pode usar Python:
            ```bash
            # No terminal, execute:
            python3 -c 'import secrets; print(secrets.token_hex(24))'
            # Copie a saída e cole como valor da chave no JSON.
            ```
        *   `LOGIN_USERNAME`: O nome de usuário que você usará para fazer login na interface.
        *   `LOGIN_PASSWORD_HASH`: O hash da senha correspondente ao `LOGIN_USERNAME`. **NÃO COLOQUE A SENHA EM TEXTO PURO AQUI.** Para gerar o hash:
            1.  Certifique-se de ter o ambiente virtual ativo (`source venv/bin/activate`).
            2.  Execute o shell interativo do Flask: `flask shell`
            3.  Dentro do shell, importe a função e gere o hash (substitua `'sua_senha_aqui'`):
                ```python
                from werkzeug.security import generate_password_hash
                print(generate_password_hash('sua_senha_aqui'))
                exit() # Sai do shell
                ```
            4.  Copie a saída completa (começando com `scrypt:...` ou `pbkdf2:...`) e cole como valor da chave no JSON.
        *   `LIVE_SHARE_TOKEN` (Opcional): Uma string secreta e difícil de adivinhar para usar na URL da visualização ao vivo. Se não for usar o compartilhamento, pode deixar vazio ou remover a chave. Para gerar um token:
             ```bash
             # No terminal, execute:
             python3 -c 'import secrets; print(secrets.token_hex(16))'
             # Copie a saída e cole como valor da chave no JSON.
             ```
        *   **Configurações VAPID (para Notificações Push - Opcional):**
            *   `VAPID_ENABLED`: Defina como `true` para habilitar as notificações push, ou `false` para desabilitar.
            *   `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_MAILTO`: Chaves necessárias para o Web Push. Para gerá-las:
                1.  Certifique-se de ter o ambiente virtual ativo (`source venv/bin/activate`).
                2.  Certifique-se de que `pywebpush` está instalado (`pip install pywebpush`).
                3.  Execute o comando Python para gerar e exibir as chaves (ajuste o comando se a biblioteca mudar):
                    ```bash
                    python -c "import base64; from cryptography.hazmat.primitives import serialization; from pywebpush import Vapid; v = Vapid(); v.generate_keys(); pk_raw = v.public_key.public_bytes(encoding=serialization.Encoding.X962, format=serialization.PublicFormat.UncompressedPoint); sk_der = v.private_key.private_bytes(encoding=serialization.Encoding.DER, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()); print(f\"Private Key: {base64.urlsafe_b64encode(sk_der).rstrip(b'=').decode('utf-8')}\"); print(f\"Public Key (Raw): {base64.urlsafe_b64encode(pk_raw).rstrip(b'=').decode('utf-8')}\")"
                    ```
                4.  Copie a "Public Key (Raw)" gerada e cole no valor de `VAPID_PUBLIC_KEY` no `config.json`.
                5.  Copie a "Private Key" gerada e cole no valor de `VAPID_PRIVATE_KEY` no `config.json`.
                6.  Defina `VAPID_MAILTO` como seu endereço de e-mail no formato `mailto:seuemail@exemplo.com`. Isso é usado por alguns serviços de push.
    *   **Importante:** O arquivo `config.json` contém informações sensíveis e **não será enviado** ao GitHub (está no `.gitignore`).

3.  **Crie e Ative o Ambiente Virtual:**
    *   Navegue até o diretório do projeto.
    *   Crie o ambiente virtual (recomendado nomeá-lo `venv`):
        ```bash
        python3 -m venv venv
        # Ative o ambiente virtual:
        source venv/bin/activate  # No Linux/macOS
        # venv\Scripts\activate    # No Windows
        ```
        *Nota: O script `SquidStart.py` agora assume que o venv está em `./venv`. Se você usar um nome/local diferente, precisará ajustar a variável `VENV_PYTHON` no início de `SquidStart.py`.* 

4.  **Instale as dependências:**
    *   Com o ambiente virtual ativo, execute:
        ```bash
        pip install -r requirements.txt
        ```

5.  **Configure a Câmera (Opcional - via MJPG-Streamer para Webcam USB):**
    *   Esta etapa é necessária apenas se você quiser usar uma webcam USB conectada ao dispositivo que roda o SquidBu (Raspberry Pi ou PC Linux) como fonte de vídeo.
    *   **a) Instale o MJPG-Streamer:**
        *   Tente instalar via gerenciador de pacotes (pode não estar disponível em todas as distribuições):
            ```bash
            sudo apt update && sudo apt install mjpg-streamer -y
            ```
        *   Se o comando acima falhar (pacote não encontrado), compile a partir do código-fonte:
            1.  Instale as dependências de compilação:
                ```bash
                sudo apt update && sudo apt install cmake libjpeg-dev build-essential git -y
                ```
            2.  Clone o repositório (um fork comum):
                ```bash
                cd ~ # Ou outro diretório adequado fora do projeto SquidBu
                git clone https://github.com/jacksonliam/mjpg-streamer.git
                ```
            3.  Compile:
                ```bash
                cd mjpg-streamer/mjpg-streamer-experimental
                make
                ```
                *(Opcional: `sudo make install` pode copiar os arquivos para locais do sistema, mas rodaremos do diretório de compilação por enquanto)*
    *   **b) Identifique sua Webcam:**
        *   Conecte a webcam USB.
        *   Liste os dispositivos de vídeo:
            ```bash
            ls /dev/video*
            ```
        *   Anote o dispositivo correto (geralmente `/dev/video0`, mas pode ser `/dev/video1`, etc.).
    *   **c) Teste o MJPG-Streamer:**
        *   Navegue até o diretório onde o `mjpg_streamer` foi compilado ou instalado. Exemplo se compilado manualmente:
            ```bash
            cd ~/mjpg-streamer/mjpg-streamer-experimental
            ```
        *   Execute o comando, ajustando o dispositivo (`-d`), resolução (`-r`), FPS (`-f`) e porta (`-p`) conforme necessário:
            ```bash
            ./mjpg_streamer -i './input_uvc.so -d /dev/video0 -r 1280x720 -f 15' -o './output_http.so -w ./www -p 8080'
            ```
        *   Acesse `http://<IP_DO_SEU_DISPOSITIVO>:8080` no navegador para verificar se o stream está funcionando. Pare o comando com `Ctrl+C` após o teste.
    *   **d) Atualize `config.json`:**
        *   Certifique-se de que a chave `CAMERA_URL` no seu `config.json` principal (do SquidBu) esteja definida para acessar o MJPG-Streamer localmente. Use a porta definida no passo anterior (ex: 8080):
            ```json
            "CAMERA_URL": "http://127.0.0.1:8080/?action=stream"
            ```
    *   **e) (Recomendado) Crie um Serviço Systemd para MJPG-Streamer:**
        *   Para que o MJPG-Streamer inicie automaticamente com o sistema:
            1.  Crie o arquivo de serviço:
                ```bash
                sudo nano /etc/systemd/system/mjpg-streamer.service
                ```
            2.  Cole o seguinte conteúdo, **ajustando `User`, `Group`, `WorkingDirectory` e o comando em `ExecStart`** para corresponder à sua configuração (usuário, caminho da compilação, dispositivo de vídeo, resolução, porta):
                ```ini
                [Unit]
                Description=MJPG-Streamer - Webcam Streamer
                After=network-online.target
                Wants=network-online.target

                [Service]
                Type=simple
                User=<SEU_USUARIO>
                Group=video
                WorkingDirectory=<CAMINHO_PARA_mjpg-streamer-experimental>
                ExecStart=<CAMINHO_PARA_mjpg-streamer-experimental>/mjpg_streamer -i './input_uvc.so -d /dev/videoX -r <RESOLUCAO> -f <FPS>' -o './output_http.so -w ./www -p <PORTA>'
                Restart=on-failure
                RestartSec=5

                [Install]
                WantedBy=multi-user.target
                ```
            3.  Salve e feche (`Ctrl+X`, `Y`, `Enter`).
            4.  Recarregue, habilite e inicie o serviço:
                ```bash
                sudo systemctl daemon-reload
                sudo systemctl enable mjpg-streamer.service
                sudo systemctl start mjpg-streamer.service
                ```
            5.  Verifique o status:
                ```bash
                sudo systemctl status mjpg-streamer.service
                ```

## Execução Local

1.  **Certifique-se de que `config.json` existe e está preenchido corretamente (incluindo as chaves de login).**

2.  **Inicie o servidor backend:**
    *   Com o ambiente virtual ativo, execute:
        ```bash
        python app.py
        ```
    *   Se houver erros ao carregar `config.json` ou dependências faltando, mensagens aparecerão no terminal.

3.  **Inicie o serviço `mjpg-streamer.service` (se configurado):**
    *   Se você configurou o MJPG-Streamer, inicie o serviço:
        ```bash
        sudo systemctl start mjpg-streamer.service
        ```

4.  **Acesse a página web:**
    *   Abra um navegador na **mesma rede local**.
    *   Acesse: `http://<IP_DO_DISPOSITIVO_RODANDO_APP>:5000` (substitua pelo IP do dispositivo que roda o app).
    *   Você será redirecionado para a página de login. Use o `LOGIN_USERNAME` e a senha correspondente ao `LOGIN_PASSWORD_HASH` configurados.

5.  **Ative as Notificações (Opcional):** Se configurado no `config.json`, clique no botão 🔔 na barra superior e permita as notificações no seu navegador.

## Visualização Ao Vivo Compartilhável (Opcional)

Se você configurou um `LIVE_SHARE_TOKEN` no `config.json`, pode clicar no botão "🔗 Compartilhar" na barra superior para copiar ou enviar o link especial:

`http://<IP_DO_DISPOSITIVO_RODANDO_APP>:5000/live/<SEU_LIVE_SHARE_TOKEN>`

Ou, se estiver usando Tailscale Funnel:

`https://<nome-do-host>.<seu-tailnet>.ts.net/live/<SEU_LIVE_SHARE_TOKEN>`

*   Substitua `<SEU_LIVE_SHARE_TOKEN>` pelo valor exato que você definiu no `config.json`.
*   Qualquer pessoa com este link poderá ver a página simplificada sem precisar fazer login.
*   Se o token estiver incorreto ou não configurado, o acesso será negado.

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