document.addEventListener('DOMContentLoaded', () => {
    console.log("[DEBUG] DOMContentLoaded iniciado");

    // =======================================
    // FUNÇÕES AUXILIARES (DEFINIDAS PRIMEIRO)
    // =======================================
    function createStatusItem(label, value, unit = '') {
        console.log(`[DEBUG] createStatusItem chamado com: label=${label}, value=${value}`);
        try {
            console.log("[DEBUG] createStatusItem: Criando div...");
            const itemDiv = document.createElement('div');
            if (!itemDiv) {
                console.error("[DEBUG] ERRO CRÍTICO: document.createElement falhou!");
                return document.createTextNode("Erro interno");
            }
            itemDiv.className = 'status-item';
            console.log("[DEBUG] createStatusItem: Definindo innerHTML...");
            itemDiv.innerHTML = `<strong>${label}</strong><span class="status-value">${value !== undefined && value !== null ? value : '--'}${unit}</span>`;
            console.log("[DEBUG] createStatusItem: innerHTML definido. Verificando se é Node...");
            if (!(itemDiv instanceof Node)) {
                 console.error("[DEBUG] ERRO CRÍTICO: itemDiv não é um Node após innerHTML!");
                 return document.createTextNode("Erro interno");
            }
             console.log("[DEBUG] createStatusItem: Retornando itemDiv:", itemDiv);
            return itemDiv;
        } catch (e) {
            console.error("[DEBUG] Erro DENTRO de createStatusItem:", e);
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
            console.error('[DEBUG] hexToRgb: Input inválido:', hex);
            return 'rgb(128, 128, 128)'; // Cinza como fallback
        }
        // Remove # se presente e pega os 6 primeiros caracteres (ignora Alpha)
        const hexClean = hex.startsWith('#') ? hex.slice(1, 7) : hex.slice(0, 6);

        if (hexClean.length !== 6) {
             console.error('[DEBUG] hexToRgb: Hex inválido após limpar:', hexClean, 'Original:', hex);
             return 'rgb(128, 128, 128)'; // Cinza como fallback
        }

        try {
            const bigint = parseInt(hexClean, 16);
            const r = (bigint >> 16) & 255;
            const g = (bigint >> 8) & 255;
            const b = bigint & 255;
            return `rgb(${r}, ${g}, ${b})`;
        } catch (e) {
            console.error('[DEBUG] hexToRgb: Erro ao converter hex:', hex, e);
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
         console.log("[DEBUG] applyTheme chamada com tema:", theme);
         const isDark = theme === 'dark';
         document.body.classList.toggle('dark-theme', isDark);
         themeToggleButton.textContent = isDark ? '☀️ Tema Claro' : '🌙 Tema Escuro';
         console.log("[DEBUG] applyTheme: Classe/Texto do botão atualizado.");
         console.log("[DEBUG] applyTheme: Atualização do gráfico concluída (se houver gráfico).");
    }
    function initializeChart() {
        console.log("[DEBUG] initializeChart: Iniciando...");
        if (!chartCtx) {
            console.error("[DEBUG] initializeChart: ERRO - Canvas 'temperatureChart' não encontrado!");
            return;
        }
        console.log("[DEBUG] initializeChart: Canvas encontrado.");

        const initialData = {
            labels: [],
            datasets: [
                { label: 'Bico (°C)', data: [], borderColor: 'rgb(255, 99, 132)', tension: 0.1, yAxisID: 'y' },
                { label: 'Mesa (°C)', data: [], borderColor: 'rgb(54, 162, 235)', tension: 0.1, yAxisID: 'y' },
                { label: 'Câmara (°C)', data: [], borderColor: 'rgb(75, 192, 192)', tension: 0.1, yAxisID: 'y', hidden: false }
            ]
        };

        try {
            console.log("[DEBUG] initializeChart: Criando novo Chart...");
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
            console.log("[DEBUG] initializeChart: Gráfico criado com sucesso:", tempChart);
        } catch (e) {
             console.error("[DEBUG] initializeChart: ERRO ao criar Chart:", e);
             tempChart = null; // Garante que não tentaremos usar um gráfico inválido
        }
    }
    function addDataToChart(timestamp, nozzleTemp, bedTemp, chamberTemp) {
        console.log(`[DEBUG] addDataToChart: Recebido T=${timestamp}, Bico=${nozzleTemp}, Mesa=${bedTemp}, Cam=${chamberTemp}`);
        if (!tempChart || !tempChart.data || !tempChart.data.labels || !tempChart.data.datasets) {
            console.warn("[DEBUG] addDataToChart: Gráfico não inicializado ou inválido, abortando.");
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
            console.log("[DEBUG] addDataToChart: Dados adicionados aos arrays.");

            // Remove dados antigos se exceder o limite (vamos ajustar isso depois para 1h)
            if (labels.length > MAX_DATA_POINTS) {
                labels.shift();
                nozzleData.shift();
                bedData.shift();
                chamberData.shift();
                console.log("[DEBUG] addDataToChart: Dados antigos removidos (MAX_DATA_POINTS).");
            }

            // Atualiza o gráfico
            console.log("[DEBUG] addDataToChart: Chamando tempChart.update()...");
            tempChart.update();
            console.log("[DEBUG] addDataToChart: tempChart.update() concluído.");

        } catch (e) {
            console.error("[DEBUG] addDataToChart: ERRO durante atualização do gráfico:", e);
        }
    }
    function updateUI(data) {
         console.log("[DEBUG] updateUI chamada...");
         try {
             if (!errorDiv) { console.error("#error-message não encontrado!"); return; }
             errorDiv.style.display = 'none';
             console.log("[DEBUG] updateUI: Limpando divs...");

             // Limpar divs containers
             const clearIfExists = (el) => { if (el) el.innerHTML = ''; else console.warn(`Elemento para limpar não encontrado:`, el ? el.id : 'ID não encontrado'); };

             // <<< LOG: VERIFICAR ELEMENTOS >>>
             console.log(`[DEBUG] Verificando elementos: overviewDiv=${overviewDiv ? 'OK' : 'NULL'}, progressDiv=${progressDiv ? 'OK' : 'NULL'}, progressBarSection=${progressBarSection ? 'OK' : 'NULL'}, tempsFansDiv=${tempsFansDiv ? 'OK' : 'NULL'}, amsDiv=${amsDiv ? 'OK' : 'NULL'}, taskDiv=${taskDiv ? 'OK' : 'NULL'}, otherDiv=${otherDiv ? 'OK' : 'NULL'}`);

             clearIfExists(overviewDiv);
             clearIfExists(progressDiv);
             clearIfExists(progressBarSection);
             clearIfExists(tempsFansDiv);
             clearIfExists(amsDiv);
             clearIfExists(taskDiv);
             clearIfExists(otherDiv);

             const loadingMsg = '<div class="loading">Aguardando primeira atualização da impressora...</div>';
             const loadingMsgShort = 'Aguardando...';

             // --- Verifica Conexão/Dados --- (Modificado para clareza)
             if (Object.keys(data).length === 0) {
                 // Se NENHUM dado chegou ainda (nem print, nem info, etc.)
                 console.log("[DEBUG] updateUI: Objeto de dados global vazio. Exibindo 'Aguardando dados do backend...'");
                 const backendMsg = '<div class="loading">Aguardando dados do backend...</div>';
                 if(overviewDiv) overviewDiv.innerHTML = backendMsg;
                 if(progressDiv) progressDiv.innerHTML = backendMsg;
                 if(tempsFansDiv) tempsFansDiv.innerHTML = backendMsg;
                 if(amsDiv) amsDiv.innerHTML = backendMsg;
                 if(taskDiv) taskDiv.innerHTML = backendMsg;
                 if(otherDiv) otherDiv.innerHTML = backendMsg;
                 // Limpar toolbar e valores atuais
                 if (toolbarNozzleValue) toolbarNozzleValue.textContent = '-- / --';
                 if (toolbarBedValue) toolbarBedValue.textContent = '-- / --';
                 if (toolbarChamberValue) toolbarChamberValue.textContent = '--';
                 if (toolbarChamberItem) toolbarChamberItem.style.display = 'none';
                 // Removido current temp/fan spans pois os controles foram removidos
                 // if (currentNozzleTempSpan) currentNozzleTempSpan.textContent = '--';
                 // if (currentBedTempSpan) currentBedTempSpan.textContent = '--';
                 if (currentFanSpeedSpan) currentFanSpeedSpan.textContent = '--';
                 return; // Sai da função
             }
             else if (!data.print) {
                // Se temos dados, mas não especificamente data.print (talvez só 'info' ou 'system')
                // Ou se data.print está vazio após uma desconexão
                console.log("[DEBUG] updateUI: Sem dados 'print' válidos. Exibindo 'Aguardando primeira atualização da impressora...'");
                if(overviewDiv) overviewDiv.innerHTML = loadingMsg;
                if(progressDiv) progressDiv.innerHTML = loadingMsg;
                if(tempsFansDiv) tempsFansDiv.innerHTML = loadingMsg;
                if(amsDiv) amsDiv.innerHTML = loadingMsg;
                if(taskDiv) taskDiv.innerHTML = loadingMsg;
                if(otherDiv) otherDiv.innerHTML = loadingMsg;
                 // Limpar toolbar e valores atuais
                 if (toolbarNozzleValue) toolbarNozzleValue.textContent = '-- / --';
                 if (toolbarBedValue) toolbarBedValue.textContent = '-- / --';
                 if (toolbarChamberValue) toolbarChamberValue.textContent = '--';
                 if (toolbarChamberItem) toolbarChamberItem.style.display = 'none';
                 // Removido current temp/fan spans pois os controles foram removidos
                 // if (currentNozzleTempSpan) currentNozzleTempSpan.textContent = '--';
                 // if (currentBedTempSpan) currentBedTempSpan.textContent = '--';
                 if (currentFanSpeedSpan) currentFanSpeedSpan.textContent = '--';
                return; // Sai da função
             }

             // Se chegou aqui, temos data.print válido
             console.log("[DEBUG] updateUI: Processando dados print válidos...");
             const printData = data.print;

             // --- Atualizar Toolbar Temps ---
             console.log("[DEBUG] updateUI: Atualizando toolbar...");
             if (toolbarNozzleValue) toolbarNozzleValue.textContent = `${printData.nozzle_temper?.toFixed(1) ?? '-'} / ${printData.nozzle_target_temper?.toFixed(0) ?? '-'}`;
             if (toolbarBedValue) toolbarBedValue.textContent = `${printData.bed_temper?.toFixed(1) ?? '-'} / ${printData.bed_target_temper?.toFixed(0) ?? '-'}`;
             if (printData.chamber_temper !== undefined && printData.chamber_temper !== null) {
                 if(toolbarChamberItem) toolbarChamberItem.style.display = 'inline';
                 if(toolbarChamberValue) toolbarChamberValue.textContent = `${printData.chamber_temper?.toFixed(1) ?? '-'}`;
             } else {
                 if(toolbarChamberItem) toolbarChamberItem.style.display = 'none';
             }

             // --- Construir HTML diretamente (Abordagem innerHTML) ---
             console.log("[DEBUG] updateUI: Construindo HTML para colunas...");

             // Coluna Esquerda: Progresso e Visão Geral
             if (progressDiv) {
                 const percent = printData.mc_percent !== undefined ? printData.mc_percent : 0;
                 const remainingMinutes = printData.mc_remaining_time;
                 const layerNum = printData.layer_num || 0;
                 const totalLayerNum = printData.total_layer_num || 0;
                 let progressHTML = `<div class="status-item"><strong>Camada</strong><span class="status-value">${layerNum} / ${totalLayerNum}</span></div>`;
                 progressHTML += `<div class="status-item"><strong>Tempo Restante</strong><span class="status-value">${formatTime(remainingMinutes)}</span></div>`;
                 console.log("[DEBUG] progressHTML:", progressHTML);
                 progressDiv.innerHTML = progressHTML;

                 // Barra de Progresso
                 if (progressBarSection) {
                      const barHTML = `<div class="progress-bar-container">
                                      <div class="progress-bar" style="width: ${percent}%;">${percent}%</div>
                                   </div>`;
                      console.log("[DEBUG] progressBarHTML:", barHTML);
                     progressBarSection.innerHTML = barHTML;
                 }
             }
             if (overviewDiv) {
                 const speedMap = ['N/A', 'Silencioso', 'Padrão', 'Sport', 'Ludicrous'];
                 const speedLevelText = speedMap[printData.spd_lvl] || 'N/A';
                 let overviewHTML = `<div class="status-item"><strong>Estado</strong><span class="status-value">${printData.gcode_state ?? '--'}</span></div>`;
                 overviewHTML += `<div class="status-item"><strong>Velocidade</strong><span class="status-value">${speedLevelText} (${printData.spd_mag ?? '--'}%)</span></div>`;
                 console.log("[DEBUG] overviewHTML:", overviewHTML);
                 overviewDiv.innerHTML = overviewHTML;
             }

             // Coluna Direita: Temps/Fans, AMS, Tarefa, Outros
             if (tempsFansDiv) {
                 let tempsHTML = `<div class="status-item"><strong>Temperaturas (°C)</strong>
                                    <p><span class="label">Bico:</span> <span class="value">${printData.nozzle_temper?.toFixed(1) ?? '-'} / ${printData.nozzle_target_temper?.toFixed(1) ?? '-'}</span></p>
                                    <p><span class="label">Mesa:</span> <span class="value">${printData.bed_temper?.toFixed(1) ?? '-'} / ${printData.bed_target_temper?.toFixed(1) ?? '-'}</span></p>
                                    ${printData.chamber_temper !== undefined ? `<p><span class="label">Câmara:</span> <span class="value">${printData.chamber_temper?.toFixed(1) ?? '-'}</span></p>` : ''}
                                </div>`;
                 let fansHTML = `<div class="status-item"><strong>Ventoinhas (%)</strong>
                                   <p><span class="label">Peça:</span> <span class="value">${printData.cooling_fan_speed ?? '-'}</span></p>
                                   <p><span class="label">Auxiliar:</span> <span class="value">${printData.big_fan1_speed ?? '-'}</span></p>
                                   <p><span class="label">Câmara:</span> <span class="value">${printData.big_fan2_speed ?? '-'}</span></p>
                                   <p><span class="label">Heatbreak:</span> <span class="value">${printData.heatbreak_fan_speed ?? '-'}</span></p>
                                </div>`;
                 console.log("[DEBUG] tempsFansHTML:", tempsHTML + fansHTML);
                 tempsFansDiv.innerHTML = tempsHTML + fansHTML;

                 // Atualizar valores atuais na seção Controle
                 if (currentNozzleTempSpan) currentNozzleTempSpan.textContent = printData.nozzle_temper?.toFixed(1) ?? '--';
                 if (currentBedTempSpan) currentBedTempSpan.textContent = printData.bed_temper?.toFixed(1) ?? '--';
                 if (currentFanSpeedSpan) currentFanSpeedSpan.textContent = printData.cooling_fan_speed ?? '--';
             }

             if (amsDiv) {
                 console.log("[DEBUG] updateUI: Processando AMS (HTML)...");
                 let amsHTML = '';
                 if (printData.ams && printData.ams.ams && printData.ams.ams.length > 0) {
                     printData.ams.ams.forEach((amsUnit, amsIndex) => {
                         amsHTML += `<div class="ams-unit">
                                        <h3>AMS ${amsIndex + 1} <span class="label">(T:${amsUnit.temp || '-'}° H:${amsUnit.humidity || '-'}%)</span></h3>`;
                         let traysHTML = '';
                         if (amsUnit.tray && amsUnit.tray.length > 0) {
                             amsUnit.tray.forEach(tray => {
                                 if (!tray.cols && !tray.tray_type) return; // Pular bandejas vazias/inválidas
                                 console.log(`[DEBUG] AMS Tray Loop: Processando Bandeja ID ${tray.id}`, tray); // Log da bandeja inteira
                                 const trayId = tray.id !== undefined ? parseInt(tray.id) : -1;
                                 const colorHex = tray.tray_color || 'FFFFFF00'; // Padrão branco transparente se ausente
                                 console.log(`[DEBUG] AMS Tray Loop: colorHex bruto = ${tray.tray_color}, Usando = ${colorHex}`); // Log do HEX bruto e o que será usado
                                 const colorRgb = hexToRgb(colorHex);
                                 console.log(`[DEBUG] AMS Tray Loop: colorRgb convertido = ${colorRgb}`); // Log do RGB convertido
                                 const type = tray.tray_type || 'N/A';
                                 const profile = tray.tray_info_idx ? `(${tray.tray_info_idx})` : '';
                                 const remaining = tray.remain !== undefined ? `${tray.remain}%` : '--';
                                 const trayHTMLFragment = `<div class="ams-tray">
                                                          <h4>Bandeja ${trayId >= 0 ? trayId + 1 : '?'}</h4>
                                                          <p>
                                                              <span class="filament-color" style="background-color: ${colorRgb};"><!-- COR APLICADA AQUI --></span>
                                                              <span class="value">${type}</span> <span class="label">${profile}</span>
                                                          </p>
                                                          <p><span class="label">Restante:</span> <span class="value">${remaining}</span></p>
                                                      </div>`;
                                 console.log(`[DEBUG] AMS Tray Loop: HTML Gerado = ${trayHTMLFragment}`); // Log do HTML da bandeja
                                 traysHTML += trayHTMLFragment;
                             });
                         }
                         if (traysHTML === '') {
                             traysHTML = '<p class="label">Nenhuma bandeja com filamento.</p>';
                         }
                         amsHTML += traysHTML + '</div>'; // Fecha ams-unit
                     });
                 } else {
                     amsHTML = '<div class="loading">AMS não detectado.</div>';
                 }
                 console.log("[DEBUG] amsHTML:", amsHTML);
                 amsDiv.innerHTML = amsHTML;
             }

             if(taskDiv) {
                 console.log("[DEBUG] updateUI: Atualizando Task (HTML)...");
                 const taskHTML = `<div class="status-item"><strong>Arquivo</strong><span class="status-value">${printData.gcode_file || '--'}</span></div>
                                  <div class="status-item"><strong>Tarefa ID</strong><span class="status-value">${printData.task_id || '--'}</span></div>`;
                 console.log("[DEBUG] taskHTML:", taskHTML);
                 taskDiv.innerHTML = taskHTML;
             }

             if(otherDiv) {
                 console.log("[DEBUG] updateUI: Atualizando Outros (HTML)...");
                 const otherHTML = `<div class="status-item"><strong>Sinal Wifi</strong><span class="status-value">${printData.wifi_signal || '--'}</span></div>`;
                 console.log("[DEBUG] otherHTML:", otherHTML);
                 otherDiv.innerHTML = otherHTML;
             }

             // --- Adicionar dados ao Gráfico ---
             console.log("[DEBUG] updateUI: Chamando addDataToChart...");
             addDataToChart(Date.now(), printData.nozzle_temper, printData.bed_temper, printData.chamber_temper);
             console.log("[DEBUG] updateUI: addDataToChart retornou.");

             console.log("[DEBUG] updateUI: Atualização (parcial) concluída.");

         } catch (error) {
            console.error("[DEBUG] Erro DENTRO de updateUI:", error);
            if (errorDiv) {
                errorDiv.textContent = `Erro ao processar dados recebidos: ${error.message}`;
                errorDiv.style.display = 'block';
            }
         }
     }
    function fetchData() {
        console.log("[DEBUG] fetchData chamada");
        try {
            fetch('/status')
                .then(response => {
                    if (!response.ok) {
                        console.error(`[DEBUG] Erro HTTP ${response.status} ao buscar /status`);
                        throw new Error(`Erro HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("[DEBUG] Dados recebidos de /status:", data);
                    updateUI(data);
                })
                .catch(error => {
                    console.error('[DEBUG] Erro DENTRO do .then/.catch do fetch:', error);
                    if (errorDiv) {
                        errorDiv.textContent = `Falha ao buscar dados (${error.message}).`;
                        errorDiv.style.display = 'block';
                    }
                });
        } catch (error) {
            console.error('[DEBUG] Erro GERAL DENTRO de fetchData (antes do fetch):', error);
             if (errorDiv) {
                errorDiv.textContent = `Erro inesperado ao processar busca de dados: ${error.message}`;
                errorDiv.style.display = 'block';
            }
        }
    }
    function sendCommand(payload) {
        console.log("[DEBUG] sendCommand: Recebido payload:", payload);
        if (!payload || !payload.command) {
            console.error("[DEBUG] sendCommand: Payload inválido.", payload);
            if (commandStatusDiv) commandStatusDiv.textContent = 'Erro: Comando inválido.';
            return;
        }
        if (commandStatusDiv) commandStatusDiv.textContent = 'Enviando...';
        fetch('/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => {
            console.log("[DEBUG] sendCommand: Resposta recebida do fetch.");
            if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            console.log("[DEBUG] sendCommand: Resposta JSON:", data);
            if (commandStatusDiv) {
                commandStatusDiv.textContent = data.message || 'Comando enviado.';
                commandStatusDiv.className = data.success ? 'status-success' : 'status-error';
            }
            // Limpa a mensagem após alguns segundos
            setTimeout(() => { if (commandStatusDiv) commandStatusDiv.textContent = ''; }, 5000);
        })
        .catch(error => {
            console.error('[DEBUG] Erro em sendCommand:', error);
            if (commandStatusDiv) {
                commandStatusDiv.textContent = `Erro ao enviar comando: ${error.message}`;
                commandStatusDiv.className = 'status-error';
            }
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
            console.log("[DEBUG] Clique na Sidebar detectado:", link.getAttribute('href'));
            event.preventDefault();
            const targetId = link.getAttribute('href').substring(1);
            contentSections.forEach(section => section.classList.remove('active'));
            const targetSection = document.getElementById(targetId);
            if (targetSection) targetSection.classList.add('active');
            sidebarLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            console.log("[DEBUG] Sidebar: Classes 'active' atualizadas.");
        });
    });

    // --- Botão de Tema ---
    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            console.log("[DEBUG] Clique no botão de Tema detectado");
            let currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : 'light';
            let newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', newTheme);
            applyTheme(newTheme);
             console.log("[DEBUG] Tema: applyTheme chamada após clique.");
        });
    } else { console.error("[DEBUG] Botão de tema não encontrado!"); }

    // --- Controles Diretos (Pause, etc) ---
    controlButtons.forEach(button => { /* ... (listener) ... */ });
    // --- Velocidade ---
    if (setSpeedButton && speedSelect) { /* ... (listener) ... */ }
    // --- LEDs ---
    ledButtons.forEach(button => {
        button.addEventListener('click', () => {
            console.log("[DEBUG] Botão LED clicado:", button.dataset);
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
                console.log("[DEBUG] Payload para sendCommand (LED):", payload);
                sendCommand(payload);
            } else {
                console.error("[DEBUG] Nó de LED desconhecido:", node);
            }
        });
    });
    // --- Temperatura/Fan ---
    if (setFanSpeedButton && fanSpeedInput) {
        setFanSpeedButton.addEventListener('click', () => {
            console.log("[DEBUG] Botão 'Definir Fan' clicado.");
            const value = parseInt(fanSpeedInput.value, 10);
            console.log(`[DEBUG] Valor lido do input Fan: ${value}`);
            // A UI usa 0-100%, mas o backend agora espera 0-100 também para converter para Gcode
            if (!isNaN(value) && value >= 0 && value <= 100) {
                const payload = { command: 'set_part_fan', value: value };
                console.log("[DEBUG] Payload para sendCommand (Fan):", payload);
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

    // =======================================
    // INICIALIZAÇÃO FINAL
    // =======================================
    console.log("[DEBUG] Iniciando inicialização final...");

    console.log("[DEBUG] Aplicando tema salvo...");
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
    console.log("[DEBUG] Tema salvo aplicado.");

    console.log("[DEBUG] Inicializando câmera (se houver)...");
    if (cameraFeed) { /* ... (inicialização câmera - manter sem log interno por ora) ... */ }
    console.log("[DEBUG] Inicialização da câmera concluída (ou ignorada).");

    console.log("[DEBUG] Chamando initializeChart...");
    initializeChart();
    console.log("[DEBUG] initializeChart retornou.");

    console.log("[DEBUG] Chamando fetchData inicial...");
    fetchData();
    fetchMaintenanceData();
    console.log("[DEBUG] fetchData inicial retornou (ou erro capturado).");

    console.log("[DEBUG] Configurando setInterval...");
    setInterval(fetchData, 3000);
    console.log("[DEBUG] setInterval configurado.");

    console.log("[DEBUG] Inicialização final concluída, fetchData agendado.");
});
