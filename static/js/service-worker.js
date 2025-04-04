console.log('Service Worker Loaded');

self.addEventListener('push', event => {
    console.log('[Service Worker] Push Received.');
    // Tenta obter os dados como JSON, caso contrário usa como texto
    let notificationData = {};
    try {
        notificationData = event.data.json();
    } catch (e) {
        console.log('[Service Worker] Push event data is not JSON, treating as text.');
        notificationData = { title: 'SquidBu Notificação', body: event.data.text() };
    }

    const title = notificationData.title || 'SquidBu Notificação';
    const options = {
        body: notificationData.body || 'Você recebeu uma notificação.',
        icon: notificationData.icon || '/static/icons/android-chrome-192x192.png', // Ícone padrão
        badge: notificationData.badge || '/static/icons/favicon-96x96.png', // Ícone menor (Android)
        // tag: 'squidbu-notification', // Usar tag pode agrupar/substituir notificações
        // renotify: true,
        data: notificationData.data || {} // Dados extras para usar no click (ex: URL)
    };

    console.log('[Service Worker] Showing notification:', title, options);

    // Garante que o SW não termine antes da notificação ser exibida
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
    console.log('[Service Worker] Notification click Received.');

    event.notification.close();

    // Abre a janela/aba do aplicativo se não estiver aberta
    // Ou foca se já estiver aberta
    // Pode personalizar a URL para abrir baseado nos dados da notificação (event.notification.data.url)
    const targetUrl = event.notification.data.url || '/'; // Abre a raiz por padrão

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(clientList => {
            // Verifica se alguma janela/aba com a URL de destino já está aberta
            for (let i = 0; i < clientList.length; i++) {
                let client = clientList[i];
                // Remove query string/hash para comparação mais flexível da URL base
                let clientBaseUrl = client.url.split('?')[0].split('#')[0];
                let targetBaseUrl = targetUrl.split('?')[0].split('#')[0];
                if (clientBaseUrl === targetBaseUrl && 'focus' in client) {
                    return client.focus();
                }
            }
            // Se nenhuma janela/aba correspondente foi encontrada, abre uma nova
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
}); 