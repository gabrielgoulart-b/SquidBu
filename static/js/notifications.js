console.log('notifications.js Loaded');

// Ler a chave do atributo data-* no body
const vapidKeyElement = document.body;
const applicationServerPublicKey = vapidKeyElement.dataset.vapidKey;

if (!applicationServerPublicKey) {
    console.error("ERRO: Chave pública VAPID não encontrada no DOM!");
}

const pushButton = document.getElementById('notifications-toggle');
const statusDiv = document.getElementById('notification-status');

let isSubscribed = false;
let swRegistration = null;

// --- Nova função: Decodificador Base64 Puro JS ---
const base64Chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";

function decodeBase64Url(base64String) {
    // 1. Converter Base64 URL Safe para Base64 Standard (+ padding)
    let base64 = base64String.replace(/\-/g, '+').replace(/_/g, '/');
    const padding = '='.repeat((4 - base64.length % 4) % 4);
    base64 += padding;

    let bytes = [];
    let i = 0;
    const len = base64.length;

    while (i < len) {
        // Ler 4 caracteres Base64
        const enc1 = base64Chars.indexOf(base64[i++]);
        const enc2 = base64Chars.indexOf(base64[i++]);
        const enc3 = base64Chars.indexOf(base64[i++]);
        const enc4 = base64Chars.indexOf(base64[i++]);

        // Ignorar caracteres inválidos (embora não devessem ocorrer aqui)
        if (enc1 === -1 || enc2 === -1) break; // Erro básico

        // Calcular 3 bytes a partir de 4 caracteres Base64
        const b1 = (enc1 << 2) | (enc2 >> 4);
        bytes.push(b1);

        // Verificar padding no terceiro caractere
        if (enc3 === 64) break; // Padding '='
        const b2 = ((enc2 & 15) << 4) | (enc3 >> 2);
        bytes.push(b2);

        // Verificar padding no quarto caractere
        if (enc4 === 64) break; // Padding '='
        const b3 = ((enc3 & 3) << 6) | enc4;
        bytes.push(b3);
    }
    return new Uint8Array(bytes);
}
// ---------------------------------------------

// Função para converter Base64 URL para Uint8Array usando o decodificador manual
function urlB64ToUint8Array(base64String) {
    try {
        const uint8Array = decodeBase64Url(base64String);
        if (!uint8Array) {
            throw new Error("Decodificador manual retornou null");
        }
        return uint8Array;
    } catch (e) {
        console.error("Erro durante decodificação manual de Base64:", e);
        return null;
    }
}

function updateBtn() {
    if (Notification.permission === 'denied') {
        statusDiv.textContent = 'Permissão para notificações foi negada.';
        pushButton.disabled = true;
        updateSubscriptionOnServer(null); // Informa ao servidor que não há assinatura
        return;
    }

    if (isSubscribed) {
        pushButton.textContent = '🔕 Desativar Notificações';
        statusDiv.textContent = 'Notificações ativadas.';
    } else {
        pushButton.textContent = '🔔 Ativar Notificações';
        statusDiv.textContent = 'Notificações desativadas.';
    }

    pushButton.disabled = false;
}

function initializeUI() {
    pushButton.addEventListener('click', () => {
        pushButton.disabled = true;
        if (isSubscribed) {
            unsubscribeUser();
        } else {
            subscribeUser();
        }
    });

    // Verifica o estado atual da assinatura
    swRegistration.pushManager.getSubscription()
    .then(subscription => {
        isSubscribed = !(subscription === null);
        updateSubscriptionOnServer(subscription);
        if (isSubscribed) {
            console.log('Usuário JÁ está inscrito.');
        } else {
            console.log('Usuário NÃO está inscrito.');
        }
        updateBtn();
    });
}

// Função subscribeUser usando a chave lida do DOM
function subscribeUser() {
    if (!applicationServerPublicKey) {
        console.error("Impossível inscrever: Chave pública VAPID ausente.");
        statusDiv.textContent = 'Erro de configuração: Chave VAPID ausente.';
        pushButton.disabled = false;
        return;
    }

    const applicationServerKey = urlB64ToUint8Array(applicationServerPublicKey);

    if (!applicationServerKey) {
        console.error("Falha ao converter a chave VAPID lida do DOM (Decoder Manual).");
        statusDiv.textContent = 'Erro interno ao preparar notificações (Decoder Manual).';
        pushButton.disabled = false;
        return;
    }

    swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
    })
    .then(subscription => {
        console.log('Usuário inscrito com sucesso:', subscription);
        updateSubscriptionOnServer(subscription);
        isSubscribed = true;
        updateBtn();
    })
    .catch(err => {
        console.error('Falha ao inscrever usuário: ', err);
        if (Notification.permission === 'denied') {
             statusDiv.textContent = 'Permissão negada. Habilite nas configurações do navegador.';
        } else {
            statusDiv.textContent = 'Falha ao ativar notificações.';
        }
        updateBtn();
    });
}

function unsubscribeUser() {
    swRegistration.pushManager.getSubscription()
    .then(subscription => {
        if (subscription) {
            return subscription.unsubscribe();
        }
    })
    .catch(error => {
        console.error('Erro ao cancelar inscrição: ', error);
    })
    .then(() => {
        updateSubscriptionOnServer(null); // Informa ao servidor para remover a assinatura
        console.log('Inscrição cancelada pelo usuário.');
        isSubscribed = false;
        updateBtn();
    });
}

function updateSubscriptionOnServer(subscription) {
    // Envia a assinatura (ou null para cancelar) para o backend
    // TODO: Implementar a rota /save_subscription no backend
    fetch('/save_subscription', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(subscription) // Envia o objeto de assinatura (ou null)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Falha ao salvar assinatura no servidor.');
        }
        return response.json();
    })
    .then(responseData => {
        if (responseData.success) {
             console.log('Assinatura atualizada no servidor.');
        } else {
            console.warn('Servidor reportou falha ao atualizar assinatura:', responseData.error);
        }
    })
    .catch(error => {
        console.error('Erro ao enviar assinatura para o servidor: ', error);
        // Não mostrar erro crítico para o usuário aqui, talvez logar
    });
}

// Verifica suporte e registra o Service Worker
if ('serviceWorker' in navigator && 'PushManager' in window) {
    console.log('Service Worker e Push são suportados');

    navigator.serviceWorker.register('/static/js/service-worker.js')
    .then(swReg => {
        console.log('Service Worker registrado: ', swReg);
        swRegistration = swReg;
        initializeUI(); // Inicializa a UI após registro do SW
    })
    .catch(error => {
        console.error('Falha ao registrar Service Worker: ', error);
        statusDiv.textContent = 'Erro: Service Worker não pôde ser registrado.';
        pushButton.disabled = true;
    });
} else {
    console.warn('Push Messaging não é suportado');
    statusDiv.textContent = 'Notificações Push não são suportadas neste navegador.';
    pushButton.disabled = true;
} 