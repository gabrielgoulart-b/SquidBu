document.addEventListener('DOMContentLoaded', () => {
    // console.log("[DEBUG] DOMContentLoaded iniciado");

    // =======================================
    // FUNÇÕES AUXILIARES (DEFINIDAS PRIMEIRO)
    // =======================================
    function createStatusItem(label, value, unit = '') {
        // console.log(`[DEBUG] createStatusItem chamado com: label=${label}, value=${value}`);
        try {
            // console.log("[DEBUG] createStatusItem: Criando div...");
            const itemDiv = document.createElement('div');
            if (!itemDiv) {
                console.error("ERRO CRÍTICO: document.createElement falhou!");
                return document.createTextNode("Erro interno");
            }
            itemDiv.className = 'status-item';
            // console.log("[DEBUG] createStatusItem: Definindo innerHTML...");
            itemDiv.innerHTML = `<strong>${label}</strong><span class="status-value">${value !== undefined && value !== null ? value : '--'}${unit}</span>`;
            // console.log("[DEBUG] createStatusItem: innerHTML definido. Verificando se é Node...");
            if (!(itemDiv instanceof Node)) {
                 console.error("ERRO CRÍTICO: itemDiv não é um Node após innerHTML!");
                 return document.createTextNode("Erro interno");
            }
             // console.log("[DEBUG] createStatusItem: Retornando itemDiv:", itemDiv);
            return itemDiv;
        } catch (e) {
            console.error("Erro DENTRO de createStatusItem:", e);
            return document.createTextNode("Erro interno");
        }
    }

    function formatTime(minutes) {
        if (minutes === undefined || minutes === null || minutes < 0) {
            return '--';
        }
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;
        if (hours > 0) {
            return `${hours}h ${remainingMinutes}m`;
        }
        return `${remainingMinutes}m`;
    }

    function hexToRgb(hex) {
        if (!hex || typeof hex !== 'string') {
            // console.error('[DEBUG] hexToRgb: Input inválido:', hex);
            return 'rgb(128, 128, 128)'; // Cinza como fallback
        }
        // Remove # se presente e pega os 6 primeiros caracteres (ignora Alpha)
        const hexClean = hex.startsWith('#') ? hex.slice(1, 7) : hex.slice(0, 6);

        if (hexClean.length !== 6) {
             // console.error('[DEBUG] hexToRgb: Hex inválido após limpar:', hexClean, 'Original:', hex);
             return 'rgb(128, 128, 128)'; // Cinza como fallback
        }

        try {
            const bigint = parseInt(hexClean, 16);
            const r = (bigint >> 16) & 255;
            const g = (bigint >> 8) & 255;
            const b = bigint & 255;
            return `rgb(${r}, ${g}, ${b})`;
        } catch (e) {
            console.error('hexToRgb: Erro ao converter hex:', hex, e);
            return 'rgb(128, 128, 128)'; // Cinza como fallback
        }
    }

    // =======================================
    // VARIÁVEIS GLOBAIS DO SCRIPT
    // =======================================
    let tempChart = null;
    const MAX_DATA_POINTS = 60;
    const chartData = { /* ... (definição do chartData) ... */ };

    // =======================================
    // ELEMENTOS DO DOM (APÓS FUNÇÕES AUXILIARES)
    // =======================================
    // --- Sidebar e Seções ---
    const sidebarLinks = document.querySelectorAll('#sidebar ul li a');
    const contentSections = document.querySelectorAll('.content-section');
    // --- Toolbar ---
    const themeToggleButton = document.getElementById('theme-toggle');
    const toolbarNozzleValue = document.getElementById('toolbar-nozzle-value');
    const toolbarBedValue = document.getElementById('toolbar-bed-value');
    const toolbarChamberItem = document.getElementById('toolbar-chamber-item');
    const toolbarChamberValue = document.getElementById('toolbar-chamber-value');

    // --- Elementos do Dashboard ---
    const overviewDiv = document.getElementById('status-overview');
    const progressDiv = document.getElementById('status-progress');
    const progressBarSection = document.getElementById('progress-bar-section');
    const tempsFansDiv = document.getElementById('status-temps-fans');
    const amsDiv = document.getElementById('ams-data');
    const taskDiv = document.getElementById('status-task');
    const otherDiv = document.getElementById('status-other');
    const errorDiv = document.getElementById('error-message');
    const cameraFeed = document.getElementById('camera-feed');
    const chartCtx = document.getElementById('temperatureChart')?.getContext('2d');

    // --- Elementos de Controle ---
    const controlButtons = document.querySelectorAll('.control-button[data-command]'); // Pause, Resume, Stop
    const setSpeedButton = document.getElementById('set-speed-button');
    const speedSelect = document.getElementById('speed-select');
    const ledButtons = document.querySelectorAll('.led-button');
    const commandStatusDiv = document.getElementById('command-status');
    const currentNozzleTempSpan = document.getElementById('current-nozzle-temp');
    const currentBedTempSpan = document.getElementById('current-bed-temp');
    const currentFanSpeedSpan = document.getElementById('current-fan-speed');
    const nozzleTempInput = document.getElementById('nozzle-temp-input');
    const bedTempInput = document.getElementById('bed-temp-input');
    const fanSpeedInput = document.getElementById('fan-speed-input');
    const setNozzleTempButton = document.getElementById('set-nozzle-temp-button');
    const setBedTempButton = document.getElementById('set-bed-temp-button');
    const setFanSpeedButton = document.getElementById('set-fan-speed-button');

    // --- Elementos de Manutenção ---
    const totalHoursSpan = document.getElementById('total-hours');
    const totalPrintsSpan = document.getElementById('total-prints');
    const totalsLastUpdatedSpan = document.getElementById('totals-last-updated');
    const updateHoursInput = document.getElementById('update-hours-input');
    const updatePrintsInput = document.getElementById('update-prints-input');
    const updateTotalsButton = document.getElementById('update-totals-button');
    const totalsStatusDiv = document.getElementById('totals-status');
    const maintenanceTaskSelect = document.getElementById('maintenance-task');
    const maintenanceNotesTextarea = document.getElementById('maintenance-notes');
    const logMaintenanceButton = document.getElementById('log-maintenance-button');
    const logStatusDiv = document.getElementById('log-status');
    const historyTableBody = document.getElementById('maintenance-history-table')?.querySelector('tbody');

    // =======================================
    // FUNÇÕES PRINCIPAIS (APÓS VARIÁVEIS E ELEMENTOS)
    // =======================================
    function applyTheme(theme) {
         // console.log("[DEBUG] applyTheme chamada com tema:", theme);
         const isDark = theme === 'dark';
         document.body.classList.toggle('dark-theme', isDark);
         themeToggleButton.textContent = isDark ? '☀️ Tema Claro' : '🌙 Tema Escuro';
         // console.log("[DEBUG] applyTheme: Classe/Texto do botão atualizado.");
         // Atualiza cores do gráfico se ele existir
         if (tempChart) {
            const textColor = isDark ? '#dee2e6' : '#333';
            const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
            tempChart.options.scales.x.ticks.color = textColor;
            tempChart.options.scales.x.title.color = textColor;
            tempChart.options.scales.x.grid.color = gridColor;
            tempChart.options.scales.y.ticks.color = textColor;
            tempChart.options.scales.y.title.color = textColor;
            tempChart.options.scales.y.grid.color = gridColor;
            tempChart.options.plugins.legend.labels.color = textColor;
            tempChart.update('none'); // Atualiza sem animação
            // console.log("[DEBUG] applyTheme: Atualização do gráfico concluída.");
         }
    }
    function initializeChart() {
        // console.log("[DEBUG] initializeChart: Iniciando...");
        if (!chartCtx) {
            // console.error("[DEBUG] initializeChart: ERRO - Canvas 'temperatureChart' não encontrado!");
            return;
        }
        // console.log("[DEBUG] initializeChart: Canvas encontrado.");

        const initialData = {
            labels: [],
            datasets: [
                { label: 'Bico (°C)', data: [], borderColor: 'rgb(255, 99, 132)', tension: 0.1, yAxisID: 'y' },
                { label: 'Mesa (°C)', data: [], borderColor: 'rgb(54, 162, 235)', tension: 0.1, yAxisID: 'y' },
                { label: 'Câmara (°C)', data: [], borderColor: 'rgb(75, 192, 192)', tension: 0.1, yAxisID: 'y', hidden: false }
            ]
        };

        try {
            // console.log("[DEBUG] initializeChart: Criando novo Chart...");
            tempChart = new Chart(chartCtx, {
                type: 'line',
                data: initialData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'minute',
                                displayFormats: { minute: 'HH:mm:ss' }, // Formato do tooltip
                                tooltipFormat: 'HH:mm:ss' // Formato no eixo
                            },
                            title: { display: true, text: 'Tempo' }
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Temperatura (°C)' }
                        }
                    },
                    plugins: {
                        legend: { position: 'top' },
                        tooltip: { mode: 'index', intersect: false }
                    }
                }
            });
            // console.log("[DEBUG] initializeChart: Gráfico criado com sucesso:", tempChart);
            // Aplica tema inicial ao gráfico
            applyTheme(localStorage.getItem('theme') || 'light');
        } catch (e) {
             console.error("initializeChart: ERRO ao criar Chart:", e);
             tempChart = null;
        }
    }
    function addDataToChart(timestamp, nozzleTemp, bedTemp, chamberTemp) {
        // console.log(`[DEBUG] addDataToChart: Recebido T=${timestamp}, Bico=${nozzleTemp}, Mesa=${bedTemp}, Cam=${chamberTemp}`);
        if (!tempChart || !tempChart.data || !tempChart.data.labels || !tempChart.data.datasets) {
            // console.warn("[DEBUG] addDataToChart: Gráfico não inicializado ou inválido, abortando.");
            return;
        }
        try {
            const now = timestamp || Date.now(); // Usa timestamp recebido ou o atual
            const labels = tempChart.data.labels;
            const nozzleData = tempChart.data.datasets[0].data;
            const bedData = tempChart.data.datasets[1].data;
            const chamberData = tempChart.data.datasets[2].data;

            // Adiciona novos dados
            labels.push(now);
            nozzleData.push(nozzleTemp !== null && nozzleTemp !== undefined ? nozzleTemp : NaN); // Usa NaN para gaps
            bedData.push(bedTemp !== null && bedTemp !== undefined ? bedTemp : NaN);
            chamberData.push(chamberTemp !== null && chamberTemp !== undefined ? chamberTemp : NaN);
            // console.log("[DEBUG] addDataToChart: Dados adicionados aos arrays.");

            // Remove dados antigos se exceder o limite (vamos ajustar isso depois para 1h)
            if (labels.length > MAX_DATA_POINTS) {
                labels.shift();
                nozzleData.shift();
                bedData.shift();
                chamberData.shift();
                // console.log("[DEBUG] addDataToChart: Dados antigos removidos (MAX_DATA_POINTS).");
            }

            // Atualiza o gráfico
            // console.log("[DEBUG] addDataToChart: Chamando tempChart.update()...");
            tempChart.update();
            // console.log("[DEBUG] addDataToChart: tempChart.update() concluído.");
        } catch (e) {
            console.error("addDataToChart: ERRO durante atualização do gráfico:", e);
        }
    }
    function updateUI(data) {
        // console.log("[DEBUG] updateUI chamada...");
        try {
            if (!errorDiv) { console.error("#error-message não encontrado!"); return; }
            errorDiv.style.display = 'none';
            // console.log("[DEBUG] updateUI: Limpando divs...");
            const clearIfExists = (el) => { if (el) el.innerHTML = ''; };
            // console.log(`[DEBUG] Verificando elementos...`); // Removido log detalhado
            clearIfExists(overviewDiv);
            clearIfExists(progressDiv);
            clearIfExists(progressBarSection);
            clearIfExists(tempsFansDiv);
            clearIfExists(amsDiv);
            clearIfExists(taskDiv);
            clearIfExists(otherDiv);

            const printStatus = data.print || {};
            const systemStatus = data.system || {}; // Adicionado para status wifi
            const amsStatus = data.ams || {}; // Para AMS

            // Atualizar Toolbar
            // console.log("[DEBUG] updateUI: Atualizando toolbar...");
            if (toolbarNozzleValue) toolbarNozzleValue.textContent = `${printStatus.nozzle_temper?.toFixed(1) ?? '--'} / ${printStatus.nozzle_target_temper?.toFixed(1) ?? '--'}`;
            if (toolbarBedValue) toolbarBedValue.textContent = `${printStatus.bed_temper?.toFixed(1) ?? '--'} / ${printStatus.bed_target_temper?.toFixed(1) ?? '--'}`;
            if (toolbarChamberItem && printStatus.chamber_temper !== undefined) {
                toolbarChamberItem.style.display = 'inline';
                if (toolbarChamberValue) toolbarChamberValue.textContent = printStatus.chamber_temper?.toFixed(1) ?? '--';
            } else if (toolbarChamberItem) {
                toolbarChamberItem.style.display = 'none';
            }

            // Atualizar Gráfico
            addDataToChart(data.system?.timestamp, printStatus.nozzle_temper, printStatus.bed_temper, printStatus.chamber_temper);

            // Construir HTML para as Colunas
            // console.log("[DEBUG] updateUI: Construindo HTML para colunas...");
            let progressHTML = '';
            let progressBarHTML = '';
            let overviewHTML = '';
            let tempsFansHTML = '';
            let amsHTML = '';
            let taskHTML = '';
            let otherHTML = '';

            // Bloco Progresso
            if (progressDiv && progressBarSection) {
                 const mcPercent = printStatus.mc_percent;
                 const mcRemaining = formatTime(printStatus.mc_remaining_time);
                 progressHTML += `<div class="status-item"><strong>Camada</strong><span class="status-value">${printStatus.layer_num ?? '--'} / ${printStatus.total_layer_num ?? '--'}</span></div>`;
                 progressHTML += `<div class="status-item"><strong>Tempo Restante</strong><span class="status-value">${mcRemaining}</span></div>`;
                 // console.log("[DEBUG] progressHTML:", progressHTML);
                 progressDiv.innerHTML = progressHTML;

                 if (mcPercent !== undefined && mcPercent !== null) {
                     progressBarHTML = `<div class="progress-bar-container">
                                      <div class="progress-bar" style="width: ${mcPercent}%;">${mcPercent}%</div>
                                   </div>`;
                     // console.log("[DEBUG] progressBarHTML:", progressBarHTML);
                     progressBarSection.innerHTML = progressBarHTML;
                 }
            }

            // Bloco Visão Geral
            if (overviewDiv) {
                let printStage = printStatus.mc_print_stage || 'UNKNOWN';
                // Traduzir estágios se necessário (opcional)
                // const stageTranslations = { 'IDLE': 'Ocioso', 'PRINTING': 'Imprimindo', ... };
                // printStage = stageTranslations[printStage] || printStage;
                const printSpeedMap = { 1: 'Silencioso (50%)', 2: 'Padrão (100%)', 3: 'Sport (124%)', 4: 'Ludicrous (168%)' };
                const printSpeed = printSpeedMap[printStatus.spd_lvl] || 'Desconhecido';
                overviewHTML += `<div class="status-item"><strong>Estado</strong><span class="status-value">${printStage}</span></div>`;
                overviewHTML += `<div class="status-item"><strong>Velocidade</strong><span class="status-value">${printSpeed}</span></div>`;
                // console.log("[DEBUG] overviewHTML:", overviewHTML);
                overviewDiv.innerHTML = overviewHTML;
            }

            // Bloco Temperaturas & Ventoinhas
            if (tempsFansDiv) {
                 tempsFansHTML += `<div class="status-item"><strong>Temperaturas (°C)</strong>
                                    <p><span class="label">Bico:</span> <span class="value">${printStatus.nozzle_temper?.toFixed(1) ?? '--'} / ${printStatus.nozzle_target_temper?.toFixed(1) ?? '--'}</span></p>
                                    <p><span class="label">Mesa:</span> <span class="value">${printStatus.bed_temper?.toFixed(1) ?? '--'} / ${printStatus.bed_target_temper?.toFixed(1) ?? '--'}</span></p>
                                    ${printStatus.chamber_temper !== undefined ? `<p><span class="label">Câmara:</span> <span class="value">${printStatus.chamber_temper?.toFixed(1) ?? '--'}</span></p>` : ''}
                                </div>`;
                 tempsFansHTML += `<div class="status-item"><strong>Ventoinhas (%)</strong>
                                   <p><span class="label">Peça:</span> <span class="value">${printStatus.cooling_fan_speed ?? '--'}</span></p>
                                   <p><span class="label">Auxiliar:</span> <span class="value">${printStatus.heatbreak_fan_speed ?? '--'}</span></p>
                                   <p><span class="label">Câmara:</span> <span class="value">${printStatus.big_fan1_speed ?? '--'}</span></p>
                                   <p><span class="label">Heatbreak:</span> <span class="value">${printStatus.cooling_fan_speed ?? '--'}</span></p>
                                </div>`;
                 // console.log("[DEBUG] tempsFansHTML:", tempsFansHTML);
                 tempsFansDiv.innerHTML = tempsFansHTML;
            }

            // Bloco AMS - Lógica Atualizada
            if (amsDiv) {
                let processedAMS = false;
                let amsHTML = ''; // Initialize amsHTML here

                try { // Added try block
                    // 1. Tentar usar data.print.stg (provável para A1 Mini/AMS Lite)
                    if (printStatus.stg && printStatus.stg.length > 0) {
                        console.log("[DEBUG] Processando AMS via print.stg...");
                        const trays = printStatus.stg;
                        let traysHTML = trays.map((tray, trayIndex) => {
                            const trayNum = parseInt(tray.id) + 1;
                            const stgFilamentType = tray.tray_type || 'N/A';
                            const stgFilamentSubType = tray.tray_sub_brands || '';
                            const colorHexRaw = tray.cols?.[0] ?? '808080FF';
                            const colorHex = colorHexRaw.length >= 6 ? colorHexRaw : '808080FF';
                            const colorRgb = hexToRgb(colorHex);
                            const remainingPercent = tray.remain !== undefined ? `${tray.remain}%` : '--';
                            const stgSubTypeDisplay = stgFilamentSubType ? ` (${stgFilamentSubType})` : '';

                            // Ler dados do DHT (assumindo que virão do backend)
                            const dhtTemp = tray.dht_temp !== undefined && tray.dht_temp !== null ? `${tray.dht_temp.toFixed(1)}°C` : '--';
                            const dhtHumidity = tray.dht_humidity !== undefined && tray.dht_humidity !== null ? `${tray.dht_humidity.toFixed(0)}%` : '--';

                            if (tray.id >= 0 && tray.id <= 3) {
                                return `<div class="ams-tray">
                                            <h4>Slot ${trayNum}</h4>
                                            <p>
                                                <span class="filament-color" style="background-color: ${colorRgb};"></span>
                                                <span class="value">${stgFilamentType}</span><span class="label">${stgSubTypeDisplay}</span>
                                            </p>
                                            <p><span class="label">Restante:</span> <span class="value">${remainingPercent}</span></p>
                                            <p>
                                                <span class="label">🌡️</span> <span class="value">${dhtTemp}</span>&nbsp;&nbsp;
                                                <span class="label">💧</span> <span class="value">${dhtHumidity}</span>
                                            </p>
                                        </div>`;
                            } else {
                                console.log("[DEBUG] print.stg: Ignorando tray com ID inválido:", tray.id);
                                return '';
                            }
                        }).join('');

                        amsHTML = `<div class="ams-unit">
                                       <h3>AMS Lite Status</h3>
                                       ${traysHTML}
                                   </div>`;
                        processedAMS = true;
                    }
                    // 2. Fallback para a estrutura aninhada (X1/P1?)
                    else if (printStatus.ams && printStatus.ams.ams && printStatus.ams.ams.length > 0) {
                        console.log("[DEBUG] Processando AMS via print.ams.ams[]...");
                        amsHTML = printStatus.ams.ams.map((unit, index) => {
                            const unitTemp = unit.temp !== undefined ? `${unit.temp}°C` : '--';
                            const unitHumidity = unit.humidity !== undefined ? `${unit.humidity}%` : '--';
                            let traysHTML = '';
                            if (unit.tray && unit.tray.length > 0) {
                                traysHTML = unit.tray.map((tray, trayIndex) => {
                                    const trayNum = parseInt(tray.id) + 1;
                                    const filamentType = tray.tray_type || 'N/A';
                                    const filamentSubType = tray.tray_sub_brands || '';
                                    const colorHexRaw = tray.cols?.[0] ?? '808080FF';
                                    const colorHex = colorHexRaw.length >= 6 ? colorHexRaw : '808080FF';
                                    const colorRgb = hexToRgb(colorHex);
                                    const remainingPercent = tray.remain !== undefined ? `${tray.remain}%` : '--';
                                    const subTypeDisplay = filamentSubType ? ` (${filamentSubType})` : '';

                                    // Ler dados do DHT (assumindo que virão do backend)
                                    const dhtTemp = tray.dht_temp !== undefined && tray.dht_temp !== null ? `${tray.dht_temp.toFixed(1)}°C` : '--';
                                    const dhtHumidity = tray.dht_humidity !== undefined && tray.dht_humidity !== null ? `${tray.dht_humidity.toFixed(0)}%` : '--';

                                    return `<div class="ams-tray">
                                                <h4>Bandeja ${trayNum}</h4>
                                                <p>
                                                    <span class="filament-color" style="background-color: ${colorRgb};"></span>
                                                    <span class="value">${filamentType}</span><span class="label">${subTypeDisplay}</span>
                                                </p>
                                                <p><span class="label">Restante:</span> <span class="value">${remainingPercent}</span></p>
                                                <p>
                                                    <span class="label">🌡️</span> <span class="value">${dhtTemp}</span>&nbsp;&nbsp;
                                                    <span class="label">💧</span> <span class="value">${dhtHumidity}</span>
                                                </p>
                                            </div>`;
                                }).join('');
                            }
                            return `<div class="ams-unit">
                                        <h3>AMS ${index + 1} <span class="label">(T:${unitTemp} H:${unitHumidity})</span></h3>${traysHTML}</div>`;
                        }).join('');
                        processedAMS = true;
                    }
                } catch (e) {
                    console.error("Erro ao processar dados AMS:", e);
                    processedAMS = false; // Marcar como não processado em caso de erro
                }

                // 3. Atualizar o HTML final
                if (processedAMS && amsHTML) { // Se processou com sucesso e tem HTML
                    amsDiv.innerHTML = amsHTML;
                } else {
                    amsDiv.innerHTML = '<div class="loading">Nenhum AMS detectado ou sem dados válidos.</div>';
                }
            } // Fim do if (amsDiv)

            // Bloco Informações da Tarefa
            if (taskDiv) {
                 // console.log("[DEBUG] updateUI: Atualizando Task (HTML)...");
                 const gcodeFile = printStatus.gcode_file || 'N/A';
                 const taskId = printStatus.task_id || '--';
                 taskHTML += `<div class="status-item"><strong>Arquivo</strong><span class="status-value">${gcodeFile.split('/').pop()}</span></div>`; // Mostra só nome do arquivo
                 taskHTML += `<div class="status-item"><strong>Tarefa ID</strong><span class="status-value">${taskId}</span></div>`;
                 // console.log("[DEBUG] taskHTML:", taskHTML);
                 taskDiv.innerHTML = taskHTML;
            }

            // Bloco Outros Status
            if (otherDiv) {
                // console.log("[DEBUG] updateUI: Atualizando Outros (HTML)...");
                const wifiSignal = printStatus.wifi_signal ? `${printStatus.wifi_signal}dBm` : '--';
                otherHTML += `<div class="status-item"><strong>Sinal Wifi</strong><span class="status-value">${wifiSignal}</span></div>`;
                // Adicionar mais itens aqui se necessário
                // console.log("[DEBUG] otherHTML:", otherHTML);
                otherDiv.innerHTML = otherHTML;
            }
             // console.log("[DEBUG] updateUI: Atualização (parcial) concluída.");

        } catch (e) {
            console.error("Erro GRANDE dentro de updateUI:", e);
            if (errorDiv) {
                errorDiv.textContent = `Erro ao atualizar interface: ${e.message}`;
                errorDiv.style.display = 'block';
            } else {
                 alert(`Erro fatal ao atualizar UI: ${e.message}`);
            }
        }
    }
    function fetchData() {
        // console.log("[DEBUG] fetchData chamada");
        fetch("/status")
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                 // console.log("[DEBUG] Dados recebidos de /status:", data);
                if (Object.keys(data).length > 0) {
                    updateUI(data);
                } else {
                     // console.log("[DEBUG] fetchData: Dados vazios recebidos, talvez inicializando...");
                    // Poderia mostrar um estado de "Aguardando dados" se necessário
                }
            })
            .catch(error => {
                console.error('Erro ao buscar dados:', error);
                 if (errorDiv) {
                    errorDiv.textContent = `Falha ao conectar ao backend. (${error.message})`;
                    errorDiv.style.display = 'block';
                 } else {
                     alert(`Falha ao conectar ao backend: ${error.message}`);
                 }
                // Limpar divs para indicar erro?
                // updateUI({}); // Chama com objeto vazio para limpar os campos
            });
    }
    function sendCommand(payload) {
        // console.log("[DEBUG] sendCommand chamado com payload:", payload);
        if (!commandStatusDiv) { console.error("Div #command-status não encontrada!"); return; }

        commandStatusDiv.textContent = `Enviando comando ${payload.command}...`;
        commandStatusDiv.style.color = 'var(--label-color)'; // Reset color

        fetch("/command", {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                // Tenta obter detalhes do erro do corpo da resposta JSON
                 return response.json().then(errData => {
                     throw new Error(errData.error || `Erro ${response.status}`);
                 }).catch(() => {
                      // Se o corpo não for JSON ou não tiver 'error', lança erro genérico
                      throw new Error(`Erro HTTP ${response.status}`);
                 });
            }
            return response.json();
        })
        .then(data => {
            // console.log("[DEBUG] Resposta do comando:", data);
            if (data.success) {
                commandStatusDiv.textContent = `Comando ${payload.command} enviado com sucesso.`;
                commandStatusDiv.style.color = 'var(--success-color)';
            } else {
                commandStatusDiv.textContent = `Falha ao enviar ${payload.command}: ${data.error || 'Erro desconhecido'}`;
                commandStatusDiv.style.color = 'var(--error-text)';
            }
            // Limpa a mensagem após alguns segundos
            setTimeout(() => {
                if (commandStatusDiv.textContent.startsWith(`Comando ${payload.command}`) || commandStatusDiv.textContent.startsWith(`Falha ao enviar ${payload.command}`)) {
                    commandStatusDiv.textContent = '';
                }
             }, 5000);
        })
        .catch(error => {
            console.error('Erro ao enviar comando:', error);
            commandStatusDiv.textContent = `Erro ao enviar comando: ${error.message}`;
            commandStatusDiv.style.color = 'var(--error-text)';
        });
    }

    // =======================================
    // FUNÇÕES DE MANUTENÇÃO
    // =======================================

    function updateTotalsDisplay(totals) {
        console.log("[DEBUG] updateTotalsDisplay chamada com:", totals);
        if (totalHoursSpan) totalHoursSpan.textContent = totals.hours?.toFixed(1) ?? 'N/A';
        if (totalPrintsSpan) totalPrintsSpan.textContent = totals.prints ?? 'N/A';
        if (totalsLastUpdatedSpan) totalsLastUpdatedSpan.textContent = totals.last_updated ?? 'Nunca';
        // Preenche os inputs com os valores atuais para facilitar a atualização
        if (updateHoursInput) updateHoursInput.value = totals.hours ?? '';
        if (updatePrintsInput) updatePrintsInput.value = totals.prints ?? '';
    }

    function populateHistoryTable(logs) {
        console.log("[DEBUG] populateHistoryTable chamada com", logs.length, "logs.");
        if (!historyTableBody) {
            console.error("[DEBUG] Tabela de histórico não encontrada!");
            return;
        }
        historyTableBody.innerHTML = ''; // Limpa a tabela

        if (logs.length === 0) {
            historyTableBody.innerHTML = '<tr><td colspan="5">Nenhum registro de manutenção encontrado.</td></tr>';
            return;
        }

        logs.forEach(log => {
            const row = historyTableBody.insertRow();
            row.insertCell().textContent = log.timestamp ?? '-';
            row.insertCell().textContent = log.task ?? '-';
            row.insertCell().textContent = log.hours_at_log?.toFixed(1) ?? '-';
            row.insertCell().textContent = log.prints_at_log ?? '-';
            row.insertCell().textContent = log.notes ?? '-';
        });
    }

    function fetchMaintenanceData() {
        console.log("[DEBUG] fetchMaintenanceData: Buscando dados de manutenção...");
        fetch('/maintenance_data')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erro HTTP ${response.status} ao buscar /maintenance_data`);
                }
                return response.json();
            })
            .then(data => {
                console.log("[DEBUG] fetchMaintenanceData: Dados recebidos:", data);
                if (data && data.totals) {
                    updateTotalsDisplay(data.totals);
                }
                if (data && data.logs) {
                    populateHistoryTable(data.logs);
                }
            })
            .catch(error => {
                console.error("[DEBUG] fetchMaintenanceData: Erro -", error);
                if (totalsStatusDiv) {
                    totalsStatusDiv.textContent = `Erro ao buscar dados: ${error.message}`;
                    totalsStatusDiv.className = 'status-error';
                }
                 if (historyTableBody) {
                    historyTableBody.innerHTML = `<tr><td colspan="5">Erro ao carregar histórico: ${error.message}</td></tr>`;
                 }
            });
    }

    function sendMaintenancePost(url, body, statusDiv) {
        console.log(`[DEBUG] sendMaintenancePost: Enviando para ${url} com body:`, body);
        statusDiv.textContent = 'Enviando...';
        statusDiv.className = 'status-pending';

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        })
        .then(response => {
            // Ler o corpo JSON mesmo se a resposta não for ok, pode conter detalhes do erro
            return response.json().then(data => ({ ok: response.ok, status: response.status, data }));
        })
        .then(({ ok, status, data }) => {
            if (ok) {
                console.log(`[DEBUG] sendMaintenancePost: Sucesso para ${url}:`, data);
                statusDiv.textContent = data.message || 'Operação concluída com sucesso!';
                statusDiv.className = 'status-success';
                // Atualiza os dados na tela após sucesso
                fetchMaintenanceData(); 
                 // Limpar campos do formulário de log se for o caso
                if (url === '/log_maintenance' && maintenanceNotesTextarea) {
                    maintenanceNotesTextarea.value = '';
                 }
            } else {
                console.error(`[DEBUG] sendMaintenancePost: Erro ${status} para ${url}:`, data);
                statusDiv.textContent = `Erro: ${data.error || 'Falha na operação.'} (Status: ${status})`;
                statusDiv.className = 'status-error';
            }
        })
        .catch(error => {
            console.error(`[DEBUG] sendMaintenancePost: Erro de rede/fetch para ${url}:`, error);
            statusDiv.textContent = `Erro de Rede: ${error.message}`;
            statusDiv.className = 'status-error';
        });
    }

    // =======================================
    // EVENT LISTENERS (APÓS TODAS AS DEFINIÇÕES)
    // =======================================
    // --- Navegação da Sidebar ---
    sidebarLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            // console.log("[DEBUG] Clique na Sidebar detectado:", link.getAttribute('href'));
            event.preventDefault();
            const targetId = link.getAttribute('href').substring(1);
            contentSections.forEach(section => section.classList.remove('active'));
            const targetSection = document.getElementById(targetId);
            if (targetSection) targetSection.classList.add('active');
            sidebarLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            // console.log("[DEBUG] Sidebar: Classes 'active' atualizadas.");
        });
    });

    // --- Botão de Tema ---
    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            // console.log("[DEBUG] Clique no botão de Tema detectado");
            let currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : 'light';
            let newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', newTheme);
            applyTheme(newTheme);
             // console.log("[DEBUG] Tema: applyTheme chamada após clique.");
        });
    } else { console.error("[DEBUG] Botão de tema não encontrado!"); }

    // --- Controles Diretos (Pause, etc) ---
    controlButtons.forEach(button => { /* ... (listener) ... */ });
    // --- Velocidade ---
    if (setSpeedButton && speedSelect) { /* ... (listener) ... */ }
    // --- LEDs ---
    ledButtons.forEach(button => {
        button.addEventListener('click', () => {
            // console.log("[DEBUG] Botão LED clicado:", button.dataset);
            const node = button.dataset.node; // Deve ser 'chamber_light' ou 'work_light'
            const mode = button.dataset.mode; // Deve ser 'on', 'off', ou 'flashing' (apenas work_light)
            let commandName = null;
            if (node === 'chamber_light') {
                commandName = 'set_chamber_light';
            } else if (node === 'work_light') {
                commandName = 'set_work_light';
            }

            if (commandName) {
                const payload = { command: commandName, mode: mode };
                // console.log("[DEBUG] Payload para sendCommand (LED):", payload);
                sendCommand(payload);
            } else {
                console.error("[DEBUG] Nó de LED desconhecido:", node);
            }
        });
    });
    // --- Temperatura/Fan ---
    if (setFanSpeedButton && fanSpeedInput) {
        setFanSpeedButton.addEventListener('click', () => {
            // console.log("[DEBUG] Botão 'Definir Fan' clicado.");
            const value = parseInt(fanSpeedInput.value, 10);
            // console.log(`[DEBUG] Valor lido do input Fan: ${value}`);
            // A UI usa 0-100%, mas o backend agora espera 0-100 também para converter para Gcode
            if (!isNaN(value) && value >= 0 && value <= 100) {
                const payload = { command: 'set_part_fan', value: value };
                // console.log("[DEBUG] Payload para sendCommand (Fan):", payload);
                sendCommand(payload);
            } else {
                console.error("[DEBUG] Valor inválido para velocidade do fan:", fanSpeedInput.value);
                if (commandStatusDiv) {
                    commandStatusDiv.textContent = 'Erro: Velocidade do fan inválida (0-100%).'; // Corrigido para 0-100
                    commandStatusDiv.className = 'status-error';
                }
            }
        });
    } else { console.warn("[DEBUG] Elementos de controle de Fan não encontrados."); }

    // --- Listeners de Manutenção ---
    if (updateTotalsButton && updateHoursInput && updatePrintsInput && totalsStatusDiv) {
        updateTotalsButton.addEventListener('click', () => {
            const hours = parseFloat(updateHoursInput.value);
            const prints = parseInt(updatePrintsInput.value, 10);
            console.log(`[DEBUG] Botão 'Salvar Totais' clicado. Horas: ${hours}, Impressões: ${prints}`);

            if (isNaN(hours) || hours < 0 || isNaN(prints) || prints < 0) {
                totalsStatusDiv.textContent = 'Erro: Insira valores numéricos válidos para horas (>=0) e impressões (inteiro >=0).';
                totalsStatusDiv.className = 'status-error';
                return;
            }

            const payload = { hours: hours, prints: prints };
            sendMaintenancePost('/update_totals', payload, totalsStatusDiv);
        });
    } else { console.warn("[DEBUG] Elementos de atualização de totais não encontrados."); }

    if (logMaintenanceButton && maintenanceTaskSelect && maintenanceNotesTextarea && logStatusDiv) {
        logMaintenanceButton.addEventListener('click', () => {
            const task = maintenanceTaskSelect.value;
            const notes = maintenanceNotesTextarea.value.trim();
            console.log(`[DEBUG] Botão 'Registrar Manutenção' clicado. Tarefa: ${task}, Notas: ${notes}`);

            if (!task) { // Deve sempre ter um valor selecionado
                 logStatusDiv.textContent = 'Erro: Selecione uma tarefa de manutenção.';
                 logStatusDiv.className = 'status-error';
                 return;
            }

             const payload = { task: task, notes: notes };
             sendMaintenancePost('/log_maintenance', payload, logStatusDiv);
        });
    } else { console.warn("[DEBUG] Elementos de log de manutenção não encontrados."); }

    const shareButton = document.getElementById('share-link-button');
    const shareToken = document.body.dataset.shareToken;

    if (shareButton && shareToken) {
        shareButton.addEventListener('click', async () => {
            const liveLink = `${window.location.origin}/live/${shareToken}`;
            const shareData = {
                title: 'SquidBu Live Print',
                text: 'Acompanhe minha impressão 3D ao vivo!',
                url: liveLink
            };

            try {
                if (navigator.share) {
                    await navigator.share(shareData);
                    console.log('Link compartilhado com sucesso!');
                    // Poderia adicionar um feedback visual aqui
                } else {
                    // Fallback para copiar para a área de transferência
                    await navigator.clipboard.writeText(liveLink);
                    alert('Link copiado para a área de transferência! (Compartilhamento nativo não suportado)'); 
                    console.log('Link copiado para a área de transferência.');
                }
            } catch (err) {
                console.error('Erro ao compartilhar/copiar link: ', err);
                alert('Erro ao tentar compartilhar o link.');
            }
        });
    } else if (shareButton && !shareToken) {
        console.warn('Botão de compartilhamento encontrado, mas token não definido no config.json ou não passado para o template.');
        shareButton.disabled = true;
        shareButton.title = "Token de compartilhamento não configurado";
    }

    // =======================================
    // INICIALIZAÇÃO FINAL
    // =======================================
    // console.log("[DEBUG] Iniciando inicialização final...");

    // console.log("[DEBUG] Aplicando tema salvo...");
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
    // console.log("[DEBUG] Tema salvo aplicado.");

    // console.log("[DEBUG] Inicializando câmera (se houver)...");
    if (cameraFeed) {
         setInterval(() => {
             cameraFeed.src = "/camera_proxy" + "?t=" + new Date().getTime();
         }, 30000);
     }
    // console.log("[DEBUG] Inicialização da câmera concluída (ou ignorada).");

    // console.log("[DEBUG] Chamando initializeChart...");
    initializeChart();
    // console.log("[DEBUG] initializeChart retornou.");

    // console.log("[DEBUG] Chamando fetchData inicial...");
    fetchData();
    fetchMaintenanceData();
    // console.log("[DEBUG] fetchData inicial retornou (ou erro capturado).");

    // console.log("[DEBUG] Configurando setInterval...");
    setInterval(fetchData, 3000);
    // console.log("[DEBUG] setInterval configurado.");

    // console.log("[DEBUG] Inicialização final concluída, fetchData agendado.");
});
