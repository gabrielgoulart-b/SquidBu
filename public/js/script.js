initializeWebcam();

// Polling function to fetch data and update UI
async function fetchAndUpdate() {
  log("Polling for data...");
  const telemetryObject = await retrieveData();
  if (telemetryObject && telemetryObject !== "Incomplete") { // Check for null and "Incomplete"
    // Call UI update functions only if data is valid
    await updateUI(telemetryObject);
    await updateFans(telemetryObject);
    await updateWifi(telemetryObject);
    await updateAMS(telemetryObject);
    log("UI updated with polled data.");
  } else if (telemetryObject === "Incomplete") {
    log("Polled data is incomplete, UI not updated.");
  } else {
    log("Failed to retrieve valid data during polling, UI not updated.");
    // Optionally call disableUI() here if desired after multiple failures
    // disableUI();
  }
}

// Function to initialize the connection and start polling
async function initializeConnection() {
  // ... (existing code inside initializeConnection) ...
  try {
    // ... (existing code: fetch /reconnect-printer, initial retrieveData, updateUI etc.) ...
    console.log(`Status da conexão: ${result.status}`);
    
    // Aguardar um momento para dar tempo de receber os dados atualizados
    await sleep(1000); 
    
    // Então tentar buscar dados iniciais
    var telemetryObject = await retrieveData();
    if (telemetryObject != null && telemetryObject != "Incomplete") {
      await updateUI(telemetryObject);
      await updateFans(telemetryObject);
      await updateWifi(telemetryObject);
      await updateAMS(telemetryObject);
      console.log("Dados iniciais carregados com sucesso");
    } else {
      console.log("Não foi possível obter dados iniciais, aguardando atualização...");
      disableUI(); 
    }

    // Start polling AFTER initial load attempt
    setInterval(fetchAndUpdate, 3000); // Poll every 3 seconds
    log("Started periodic polling for data.");

  } catch (error) {
    console.error("Erro ao inicializar conexão:", error);
    // Consider starting polling even if initial connection has issues?
    // setInterval(fetchAndUpdate, 3000);
  }
}

// REMOVE or comment out the focus listener
// window.addEventListener('focus', function() {
//   console.log("Página recebeu foco, atualizando dados...");
//   initializeConnection(); 
// });

async function retrieveData() {
// ... existing code ...
} 

// Example - Search for Bed Temperature update:
const bedTempElement = document.getElementById('bedTemp'); // Assuming ID
if (bedTempElement) {
  const bedTempC = telemetryObject.bed_temper;
  // SIMPLIFIED: Always display Celsius only
  bedTempElement.textContent = Math.round(bedTempC) + '°C';
  // REMOVED: Logic checking tempSetting and adding Fahrenheit
}

// Example - Search for Nozzle Temperature update:
const nozzleTempElement = document.getElementById('nozzleTemp'); // Assuming ID
if (nozzleTempElement) {
  const nozzleTempC = telemetryObject.nozzle_temper;
  // SIMPLIFIED: Always display Celsius only
  nozzleTempElement.textContent = Math.round(nozzleTempC) + '°C';
  // REMOVED: Logic checking tempSetting and adding Fahrenheit
}

// Example - Search for Chamber Temperature update (if exists):
const chamberTempElement = document.getElementById('chamberTemp'); // Assuming ID
if (chamberTempElement && telemetryObject.chamber_temper !== undefined) {
  const chamberTempC = telemetryObject.chamber_temper;
  // SIMPLIFIED: Always display Celsius only
  chamberTempElement.textContent = Math.round(chamberTempC) + '°C';
  // REMOVED: Logic checking tempSetting and adding Fahrenheit
}

// Remove the celsiusToFahrenheit function if it exists
// function celsiusToFahrenheit(celsius) { ... } // REMOVED 