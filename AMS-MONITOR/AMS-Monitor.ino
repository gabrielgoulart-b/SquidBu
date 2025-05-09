#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <EEPROM.h>

// --- Configurações ---
// WiFi
const char* ssid = "O Dragao Caolho";     // <<< COLOQUE SEU SSID REAL AQUI
const char* password = "99850508"; // <<< COLOQUE SUA SENHA REAL AQUI

// MQTT (Descomentado e configurado para ESP32)
const char* mqtt_server = "192.168.1.103"; // <<< IP do seu Servidor MQTT
const int mqtt_port = 1883;
const char* mqtt_user = "";        // <<< Username do MQTT (se necessário)
const char* mqtt_password = "";     // <<< Senha do MQTT (se necessário)
const char* mqtt_client_id = "esp32_filament_monitor"; // ID único para este dispositivo no MQTT

// Outras Configs
const float INITIAL_FILAMENT_WEIGHT_G = 1000.0; // Peso inicial padrão do filamento em gramas (modificável pelo usuário)

// --- Definições de Pinos para ESP32 ---
// Sensores DHT
#define DHTPIN1 16 // GPIO16
#define DHTPIN2 17 // GPIO17
#define DHTPIN3 18 // GPIO18
#define DHTPIN4 19 // GPIO19
#define DHTTYPE DHT11

// Encoders - Usando pinos com capacidade de interrupção externa no ESP32
#define ENCODER1_PIN 32 // GPIO32
#define ENCODER2_PIN 33 // GPIO33
#define ENCODER3_PIN 25 // GPIO25
#define ENCODER4_PIN 26 // GPIO26

// Botões Digitais - Substituido o antigo sistema analógico
#define BUTTON_MENU_PIN 13    // GPIO13
#define BUTTON_SELECT_PIN 14  // GPIO14
#define BUTTON_BACK_PIN  15   // GPIO15
#define BUTTON_NEXT_PIN 27    // GPIO27

// Adicionar configuração para simular botões via serial para debug
#define ENABLE_SERIAL_BUTTONS true // Habilita controle dos botões via serial

// --- Configuração OLED ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

// --- Instâncias ---
TaskHandle_t MQTTTask;  // Handle para tarefa MQTT
TaskHandle_t UITask;    // Handle para tarefa da interface do usuário
DHT dht1(DHTPIN1, DHTTYPE);
DHT dht2(DHTPIN2, DHTTYPE);
DHT dht3(DHTPIN3, DHTTYPE);
DHT dht4(DHTPIN4, DHTTYPE);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
WiFiClient espClient;
PubSubClient client(espClient);

// --- Variáveis Globais ---
// Variáveis compartilhadas - protegidas por semáforo
SemaphoreHandle_t dataMutex;
float temperatures[4] = {0.0};
float humidities[4] = {0.0};
volatile unsigned long filamentUsage[4] = {0};
unsigned long lastEncoderTime[4] = {0};
float filamentDensity[4] = {1.24}; // g/cm³
float spoolWeight[4] = {0.0};     // Peso inicial do carretel configurável - alterado de emptySpoolWeight

// Variáveis para simulação de encoders
bool simulateEncoder[4] = {false, false, false, false}; // Controla se a simulação está ativa para cada caixa
unsigned long lastSimulatedPulse[4] = {0}; // Último pulso simulado para cada caixa
unsigned long simulatePulseInterval[4] = {1000, 1000, 1000, 1000}; // Intervalo entre pulsos simulados (ms) para cada caixa
#define MIN_PULSE_INTERVAL 100  // Intervalo mínimo (100ms)
#define MAX_PULSE_INTERVAL 1000 // Intervalo máximo (1000ms)

// Adicionando flag para controlar o MQTT
bool mqttEnabled = true; // Flag para habilitar/desativar MQTT
#define MUTEX_TIMEOUT_MS 50 // Timeout para semáforos para evitar bloqueios

// Variáveis da interface do usuário
int currentPage = 0;
const int TOTAL_PAGES = 5;
bool lastButtonMenuState = HIGH;    // Invertido para botões digitais (PULLUP)
bool lastButtonSelectState = HIGH;  // Invertido para botões digitais (PULLUP)
bool lastButtonBackState = HIGH;    // Invertido para botões digitais (PULLUP)
bool lastButtonNextState = HIGH;    // Invertido para botões digitais (PULLUP)
unsigned long lastDebounceTime = 0;
#define DEBOUNCE_DELAY 50
enum MenuState { MAIN_SCREEN, MENU_MAIN, MENU_SET_DENSITY, MENU_SET_SPOOL_WEIGHT };
MenuState currentMenu = MAIN_SCREEN;
int currentBoxForMenu = 0;
int menuSelection = 0;
float editValue = 0.0;

// Variável para controle da tela inicial
bool splashScreenShown = false;
unsigned long splashScreenStartTime = 0;
#define SPLASH_SCREEN_TIMEOUT 5000 // 5 segundos até avançar automaticamente

// Variáveis MQTT
unsigned long lastMqttPublish = 0;
unsigned long lastMqttAttempt = 0;
#define MQTT_PUBLISH_INTERVAL 5000
#define MQTT_RECONNECT_INTERVAL 5000

// --- Endereços EEPROM ---
#define EEPROM_SIZE 512
#define EEPROM_INITIALIZED_ADDR 0
#define EEPROM_DENSITY_ADDR (EEPROM_INITIALIZED_ADDR + sizeof(uint32_t))
#define EEPROM_SPOOL_WEIGHT_ADDR (EEPROM_DENSITY_ADDR + 4 * sizeof(float))
#define EEPROM_USAGE_ADDR (EEPROM_SPOOL_WEIGHT_ADDR + 4 * sizeof(float))
#define EEPROM_INIT_FLAG 0xABCD1235  // Alterado para nova versão

// --- Protótipos ---
void setupWifi();
void readSensors();
void updateDisplay();
void handleButtons();
void resetFilamentUsage(int boxNumber);
void IRAM_ATTR handleEncoder1();
void IRAM_ATTR handleEncoder2();
void IRAM_ATTR handleEncoder3();
void IRAM_ATTR handleEncoder4();
void loadFromEEPROM();
void saveToEEPROM();
void updateMainScreen(int boxIndex);
void updateMenuScreen();
void updateMqttStatusScreen();
float calculateRemainingWeight(int boxNumber);
float calculateRemainingLength(int boxNumber);
float calculateRemainingPercentage(int boxNumber);
void reconnectMqtt();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void publishData();
bool checkMqttConnection();
void checkSerialCommands();
void checkEncoderSimulation();

// --- Tarefas para MultiCore ---
void MQTTTaskCode(void *pvParameters) {
  Serial.print("MQTT Task rodando no núcleo: ");
  Serial.println(xPortGetCoreID());
  
  for(;;) {
    // Verifica se MQTT está habilitado
    if (mqttEnabled) {
      // Verifica e reconecta MQTT se necessário
      if (WiFi.status() == WL_CONNECTED) {
        if (!client.connected()) {
          reconnectMqtt();
        }
        
        if (client.connected()) {
          client.loop();
          
          // Publica dados a cada intervalo
          unsigned long currentMillis = millis();
          if (currentMillis - lastMqttPublish >= MQTT_PUBLISH_INTERVAL) {
            publishData();
            lastMqttPublish = currentMillis;
          }
        }
      }
    }
    
    // Pequeno delay para não sobrecarregar o processador
    vTaskDelay(250 / portTICK_PERIOD_MS); // Aumentado para dar mais tempo para UI
  }
}

void UITaskCode(void *pvParameters) {
  Serial.print("UI Task rodando no núcleo: ");
  Serial.println(xPortGetCoreID());
  
  for(;;) {
    // Leitura dos sensores
    readSensors();
    
    // Interface do usuário
    handleButtons();
    
    // Verificar comandos via Serial
    if (ENABLE_SERIAL_BUTTONS) {
      checkSerialCommands();
    }
    
    // Processar simulação de encoders
    checkEncoderSimulation();
    
    // Atualizar display com status atual
    updateDisplay();
    
    // Pequeno delay para não sobrecarregar o processador
    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

// --- SETUP ---
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 5000);
    delay(100);
    
    // Inicializar gerador de números aleatórios
    randomSeed(analogRead(0));
    
    Serial.println("\n\n--- Iniciando Monitor de Filamento (ESP32) ---");
    Serial.println("INFO: Botoes configurados para pinos digitais:");
    Serial.println("      MENU: GPIO13, SELECT: GPIO15, BACK: GPIO14, NEXT: GPIO27");
    Serial.println("INFO: Envie 'n'=next, 'b'=back, 'm'=menu, 's'=select, 'q'=toggle MQTT via Serial.");
    Serial.println("INFO: Para simular encoders, use:");
    Serial.println("      - Teclas '1', '2', '3', '4' no Serial para um pulso único");
    Serial.println("      - Envie '1on', '2on' para iniciar com intervalo padrão (1000ms)");
    Serial.println("      - Envie '1on500', '2on100' para definir intervalo (100-1000ms)");
    Serial.println("      - Envie '1off', '2off' para parar a simulação");
    Serial.println("INFO: Sistema configurado com encoders nos pinos: 32, 33, 25, 26");

    // Criar semáforo para proteção das variáveis compartilhadas
    dataMutex = xSemaphoreCreateMutex();
    
    // Inicializar EEPROM
    EEPROM.begin(EEPROM_SIZE);
    loadFromEEPROM();

    // Inicializar I2C
    Wire.begin(); // Usa padrão SDA=21, SCL=22 no ESP32
    Serial.println("INFO: I2C iniciado com pinos padrao (SDA=21, SCL=22).");

    // Verificar se o OLED está respondendo
    Serial.print("Verificando comunicação com OLED no endereço 0x");
    Serial.print(SCREEN_ADDRESS, HEX);
    Serial.print("... ");
    
    Wire.beginTransmission(SCREEN_ADDRESS);
    byte error = Wire.endTransmission();
    
    if (error == 0) {
        Serial.println("OK!");
    } else {
        Serial.print("FALHA! Código de erro: ");
        Serial.println(error);
        Serial.println("DICA: Verifique as conexões:");
        Serial.println("- SDA no pino GPIO21");
        Serial.println("- SCL no pino GPIO22");
        Serial.println("- Alimentação do display (3.3V e GND)");
        Serial.println("- Endereço I2C correto (padrão 0x3C)");
    }

    // Inicializar Sensores DHT
    dht1.begin(); dht2.begin(); dht3.begin(); dht4.begin();
    Serial.println("Sensores DHT inicializados.");

    // Inicializar Display OLED
    Serial.println("Tentando inicializar o display OLED...");
    if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        Serial.println(F("Falha ao iniciar SSD1306. Verifique conexao I2C."));
        // Não travar o programa, apenas marcar o erro
        Serial.println("AVISO: Continuando sem inicializar o display!");
    }
    else {
        Serial.println("Display OLED inicializado com sucesso!");
        display.clearDisplay(); display.setTextSize(1); display.setTextColor(SSD1306_WHITE);
        display.setCursor(0, 0); display.println(F("Iniciando...")); display.display();
        delay(100);
    }

    // Configuração dos pinos digitais para botões com pull-up interno
    pinMode(BUTTON_MENU_PIN, INPUT_PULLUP);
    pinMode(BUTTON_SELECT_PIN, INPUT_PULLUP);
    pinMode(BUTTON_BACK_PIN, INPUT_PULLUP);
    pinMode(BUTTON_NEXT_PIN, INPUT_PULLUP);
    Serial.println("Pinos de botão configurados com pull-up interno");
    
    // Configuração dos pinos de entrada para encoders
    pinMode(ENCODER1_PIN, INPUT_PULLUP);
    pinMode(ENCODER2_PIN, INPUT_PULLUP);
    pinMode(ENCODER3_PIN, INPUT_PULLUP);
    pinMode(ENCODER4_PIN, INPUT_PULLUP);

    // Configurar interrupções para ESP32
    attachInterrupt(digitalPinToInterrupt(ENCODER1_PIN), handleEncoder1, FALLING);
    attachInterrupt(digitalPinToInterrupt(ENCODER2_PIN), handleEncoder2, FALLING);
    attachInterrupt(digitalPinToInterrupt(ENCODER3_PIN), handleEncoder3, FALLING);
    attachInterrupt(digitalPinToInterrupt(ENCODER4_PIN), handleEncoder4, FALLING);

    Serial.println("Pinos de encoder configurados.");

    // Conectar ao WiFi
    display.clearDisplay(); display.setCursor(0, 10);
    display.println(F("Conectando WiFi...")); display.display();
    setupWifi();

    // Configuração do cliente MQTT
    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(mqttCallback);

    // Mostrar splash screen
    display.clearDisplay(); display.setCursor(0, 0);
    display.println(F("Monitor Filamento"));
    display.println(F("ESP32 DevKit"));
    if (WiFi.status() == WL_CONNECTED) {
        display.print(F("IP: ")); display.println(WiFi.localIP());
    } else {
        display.println(F("Falha no WiFi!"));
    }
    display.println(F("MQTT: Ativo")); 
    display.println(F("\nIniciando..."));
    display.println(F("Pressione qualquer botao"));
    display.display(); 
    
    // Inicializa o controle da tela de splash
    splashScreenShown = false;
    splashScreenStartTime = millis();
    
    // Configuração para inicialização
    currentPage = 0;
    currentMenu = MAIN_SCREEN;

    // Criar tarefas para multitarefa
    // MQTT Task no núcleo 0
    xTaskCreatePinnedToCore(
      MQTTTaskCode,   /* Função da tarefa */
      "MQTTTask",     /* Nome da tarefa */
      8192,           /* Tamanho da pilha */
      NULL,           /* Parâmetro da tarefa */
      1,              /* Prioridade da tarefa - REDUZIDA */
      &MQTTTask,      /* Handle da tarefa */
      0);             /* Núcleo onde executará (0) */
      
    // UI Task no núcleo 1 (núcleo do Arduino)
    xTaskCreatePinnedToCore(
      UITaskCode,     /* Função da tarefa */
      "UITask",       /* Nome da tarefa */
      8192,           /* Tamanho da pilha */
      NULL,           /* Parâmetro da tarefa */
      3,              /* Prioridade da tarefa - AUMENTADA */
      &UITask,        /* Handle da tarefa */
      1);             /* Núcleo onde executará (1) */

    Serial.println("Setup Concluido. Tarefas iniciadas nos dois núcleos.");
}

// --- LOOP ---
void loop() {
    // O loop principal está vazio, pois as tarefas foram delegadas às funções MQTTTaskCode e UITaskCode
    delay(1000);
}

// --- FUNÇÕES ---
void setupWifi() {
    delay(10); Serial.println(); Serial.print("Conectando a "); Serial.println(ssid);
    WiFi.mode(WIFI_STA); WiFi.begin(ssid, password);
    int wifi_retries = 0;
    while (WiFi.status() != WL_CONNECTED && wifi_retries < 30) {
        delay(500); Serial.print("."); wifi_retries++;
        if (display.height() > 0) { display.print("."); display.display(); }
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi conectado!"); Serial.print("Endereco IP: "); Serial.println(WiFi.localIP());
    } else {
        Serial.println("\nFalha ao conectar no WiFi!");
    }
}

void readSensors() {
    static int sensorIndexToRead = 0;
    float t = NAN; float h = NAN;
    
    switch(sensorIndexToRead) {
      case 0: t = dht1.readTemperature(); h = dht1.readHumidity(); break;
      case 1: t = dht2.readTemperature(); h = dht2.readHumidity(); break;
      case 2: t = dht3.readTemperature(); h = dht3.readHumidity(); break;
      case 3: t = dht4.readTemperature(); h = dht4.readHumidity(); break;
    }
    
    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
        if (!isnan(t) && t > -20 && t < 80) temperatures[sensorIndexToRead] = t;
        if (!isnan(h) && h >= 0 && h <= 100) humidities[sensorIndexToRead] = h;
        xSemaphoreGive(dataMutex);
    }
    
    sensorIndexToRead = (sensorIndexToRead + 1) % 4;
}

void updateDisplay() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    // Verificar se ainda está na tela de splash
    if (!splashScreenShown) {
        unsigned long currentMillis = millis();
        if (currentMillis - splashScreenStartTime > SPLASH_SCREEN_TIMEOUT) {
            splashScreenShown = true;
            currentPage = 0;
            Serial.println("Splash screen timeout - avançando para primeira página");
        } else {
            // Continuar mostrando a tela de splash
            display.setCursor(0, 0);
            display.println(F("Monitor Filamento"));
            display.println(F("ESP32 DevKit"));
            if (WiFi.status() == WL_CONNECTED) {
                display.print(F("IP: ")); display.println(WiFi.localIP());
            } else {
                display.println(F("Falha no WiFi!"));
            }
            display.println(F("MQTT: Ativo")); 
            display.println(F("\nIniciando..."));
            display.println(F("Pressione qualquer botao"));
            display.display();
            return; // Não avança para as telas de menu ainda
        }
    }
    
    // Continua com a exibição normal após a tela de splash
    if (currentMenu == MAIN_SCREEN) {
        if (currentPage >= 0 && currentPage < 4) {
            updateMainScreen(currentPage);
        } else if (currentPage == 4) {
            updateMqttStatusScreen();
        }
    } else {
        updateMenuScreen();
    }
    display.display();
}

void updateMainScreen(int boxIndex) {
    float remainingPercentage = 0.0;
    float remainingWeight = 0.0;
    float temp = 0.0;
    float humid = 0.0;
    unsigned long usage = 0;
    float density = 0.0;
    float spool = 0.0;
    
    // Obter valores protegidos pelo semáforo
    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
        temp = temperatures[boxIndex];
        humid = humidities[boxIndex];
        usage = filamentUsage[boxIndex];
        density = filamentDensity[boxIndex];
        spool = spoolWeight[boxIndex];
        xSemaphoreGive(dataMutex);
    }
    
    // Calcular valores derivados
    remainingPercentage = calculateRemainingPercentage(boxIndex);
    remainingWeight = calculateRemainingWeight(boxIndex);
    
    // Atualizar display
    display.setCursor(0, 0); 
    display.print("Caixa #"); display.print(boxIndex + 1); 
    display.print("/"); display.print(4);
    
    display.setCursor(0, 10); 
    display.print("Temp: "); display.print(temp, 1); 
    display.print((char)247); display.print("C");
    
    display.setCursor(0, 19); 
    display.print("Umid: "); display.print(humid, 0); 
    display.print("%");
    
    display.setCursor(0, 28);
    display.print("Usado:");

    // Valor centralizado
    char usedStr[10];
    float usedLengthMeters = 0.0;
    if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
        usedLengthMeters = filamentUsage[boxIndex] / 1000.0; // converter mm para m
        xSemaphoreGive(dataMutex);
    }
    sprintf(usedStr, "%.1fm", usedLengthMeters);
    int16_t x1, y1;
    uint16_t w1, h1;
    display.getTextBounds(usedStr, 0, 0, &x1, &y1, &w1, &h1);
    display.setCursor((SCREEN_WIDTH - w1) / 2, 28);
    display.print(usedStr);

    display.setCursor(0, 37);
    display.print("Peso:");

    // Valor centralizado
    char weightStr[10];
    if (remainingWeight >= 0) {
        sprintf(weightStr, "%.0fg", remainingWeight);
    } else {
        strcpy(weightStr, "--- g");
    }
    int16_t x2, y2;
    uint16_t w2, h2;
    display.getTextBounds(weightStr, 0, 0, &x2, &y2, &w2, &h2);
    display.setCursor((SCREEN_WIDTH - w2) / 2, 37);
    display.print(weightStr);
    
    // Barra de progresso para o peso restante
    int barX = 0;
    int barY = 47;
    int barWidth = 128;
    int barHeight = 5;
    
    // Calcular a porcentagem do peso restante em relação ao peso máximo (1000g)
    float fillPercentage = 0.0;
    if (spoolWeight[boxIndex] > 0) {
        fillPercentage = (remainingWeight / spoolWeight[boxIndex]) * 100.0;
        if (fillPercentage < 0) fillPercentage = 0;
        if (fillPercentage > 100) fillPercentage = 100;
    }
    
    int fillWidth = (int)((fillPercentage / 100.0) * barWidth);
    
    // Desenhar contorno da barra
    display.drawRect(barX, barY, barWidth, barHeight, SSD1306_WHITE);
    
    // Preencher a barra baseado na porcentagem
    if (fillWidth > 0) {
        display.fillRect(barX + 1, barY + 1, fillWidth - 2, barHeight - 2, SSD1306_WHITE);
    }
    
    // Linha da navegação
    display.setCursor(0, 56);
    display.print("Menu");
    display.setCursor(SCREEN_WIDTH - 30, 56);
    display.print("<   >");
}

void updateMqttStatusScreen() {
    display.setCursor(0, 0); 
    display.println("Status Conexoes");
    display.drawLine(0, 9, SCREEN_WIDTH-1, 9, SSD1306_WHITE);

    display.setCursor(0, 10); 
    display.print("WiFi: ");
    if (WiFi.status() == WL_CONNECTED) {
        display.print("OK ("); 
        display.print(WiFi.RSSI()); 
        display.print("dBm)");
    } else { 
        display.print("Desconectado"); 
    }

    display.setCursor(0, 19); 
    display.print("IP: "); 
    display.println(WiFi.localIP().toString());

    display.setCursor(0, 28); 
    display.print("MQTT: ");
    if (client.connected()) { 
        display.println("CONECTADO"); 
    } else { 
        display.print("DESCONECTADO ("); 
        display.print(client.state()); 
        display.print(")"); 
    }

    display.setCursor(0, 37); 
    display.print("Server: "); 
    display.println(mqtt_server);

    // Linha de navegação
    display.setCursor(0, 56);
    display.print("Menu");
    display.setCursor(SCREEN_WIDTH - 30, 56);
    display.print("<   >");
}

void updateMenuScreen() {
    int boxIndex = currentBoxForMenu; // Caixa relevante para este menu
    display.setTextSize(1);
    display.setCursor(0, 0);
    int startY = 12;
    int lineHeight = 10;

    // Título varia conforme o menu
    if (currentMenu == MENU_MAIN) {
        display.print("Menu - Caixa #"); 
        display.println(boxIndex + 1);
        display.drawLine(0, 9, SCREEN_WIDTH-1, 9, SSD1306_WHITE);
        const char* options[] = {"1. Densidade", "2. Peso Carretel"};
        for (int i = 0; i < 2; i++) {
            display.setCursor(0, startY + i * lineHeight);
            display.print((i == menuSelection) ? "> " : "  ");
            display.println(options[i]);
        }
        display.setCursor(0, 56); 
        display.print("Selec: OK | Menu: Voltar");
    } 
    else if (currentMenu == MENU_SET_DENSITY) {
        display.println("Definir Densidade");
        display.drawLine(0, 9, SCREEN_WIDTH-1, 9, SSD1306_WHITE);
        display.setCursor(0, startY); 
        display.print("(g/cm3) Caixa "); 
        display.println(boxIndex + 1);
        display.setTextSize(2); 
        display.setCursor(20, startY + lineHeight + 5);
        display.print(editValue, 2); 
        display.setTextSize(1);
        display.setCursor(0, 56); 
        display.print("Selec: Salvar | Menu: Cancel");
    } 
    else if (currentMenu == MENU_SET_SPOOL_WEIGHT) {
        display.println("Peso Carretel");
        display.drawLine(0, 9, SCREEN_WIDTH-1, 9, SSD1306_WHITE);
        display.setCursor(0, startY); 
        display.print("(g) Caixa "); 
        display.println(boxIndex + 1);
        display.setTextSize(2); 
        display.setCursor(20, startY + lineHeight + 5);
        display.print(editValue, 0); 
        display.setTextSize(1);
        display.setCursor(0, 56); 
        display.print("Selec: Salvar | Menu: Cancel");
    }
}

void handleButtons() {
    unsigned long currentMillis = millis();
    
    // Ler o estado dos botões digitais (LOW quando pressionado devido ao pull-up)
    bool currentMenuBtn = digitalRead(BUTTON_MENU_PIN) == LOW;
    bool currentSelectBtn = digitalRead(BUTTON_SELECT_PIN) == LOW;
    bool currentBackBtn = digitalRead(BUTTON_BACK_PIN) == LOW;
    bool currentNextBtn = digitalRead(BUTTON_NEXT_PIN) == LOW;
    
    // Se qualquer botão for pressionado, sai da tela de splash
    if (!splashScreenShown && (currentMenuBtn || currentSelectBtn || currentNextBtn || currentBackBtn)) {
        splashScreenShown = true;
        currentPage = 0;
        Serial.println("Botão pressionado - saindo da tela de splash");
    }
    
    // Debug do estado dos botões
    static unsigned long lastSerialPrint = 0;
    if (currentMillis - lastSerialPrint > 250) {
        if (currentMenuBtn || currentSelectBtn || currentBackBtn || currentNextBtn) {
            Serial.print("Botões: ");
            if (currentMenuBtn) Serial.print("MENU ");
            if (currentSelectBtn) Serial.print("SELECT ");
            if (currentBackBtn) Serial.print("BACK ");
            if (currentNextBtn) Serial.print("NEXT ");
            Serial.println();
            lastSerialPrint = currentMillis;
        }
    }

    if (currentMillis - lastDebounceTime > DEBOUNCE_DELAY) {
        if (currentMenuBtn && lastButtonMenuState != currentMenuBtn) {
            lastDebounceTime = currentMillis;
            Serial.println("AÇÃO: Botão MENU pressionado");
            if (currentMenu == MAIN_SCREEN) {
                if (currentPage < 4) {
                   currentBoxForMenu = currentPage; 
                   currentMenu = MENU_MAIN; 
                   menuSelection = 0;
                } else { 
                   currentPage = 0; 
                }
            } else if (currentMenu == MENU_MAIN) { 
                currentMenu = MAIN_SCREEN;
            } else if (currentMenu == MENU_SET_DENSITY || currentMenu == MENU_SET_SPOOL_WEIGHT) { 
                currentMenu = MENU_MAIN; 
            }
        }
        
        if (currentSelectBtn && lastButtonSelectState != currentSelectBtn) {
            lastDebounceTime = currentMillis;
            Serial.println("AÇÃO: Botão SELECT pressionado");
            
            if (currentMenu == MAIN_SCREEN) { 
                if (currentPage >= 0 && currentPage < 4) {
                    currentBoxForMenu = currentPage;
                    currentMenu = MENU_MAIN;
                    menuSelection = 0;
                }
            } else if (currentMenu == MENU_MAIN) {
                switch (menuSelection) {
                    case 0: 
                        currentMenu = MENU_SET_DENSITY; 
                        if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
                            editValue = filamentDensity[currentBoxForMenu]; 
                            xSemaphoreGive(dataMutex);
                        }
                        break;
                    case 1: 
                        currentMenu = MENU_SET_SPOOL_WEIGHT; 
                        if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
                            editValue = spoolWeight[currentBoxForMenu]; 
                            xSemaphoreGive(dataMutex);
                        }
                        break;
                }
            } else if (currentMenu == MENU_SET_DENSITY) { 
                if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
                    filamentDensity[currentBoxForMenu] = editValue; 
                    xSemaphoreGive(dataMutex);
                }
                saveToEEPROM(); 
                currentMenu = MENU_MAIN;
            } else if (currentMenu == MENU_SET_SPOOL_WEIGHT) { 
                if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
                    spoolWeight[currentBoxForMenu] = editValue; 
                    // Resetar o contador de uso quando o peso do carretel é alterado
                    filamentUsage[currentBoxForMenu] = 0;
                    xSemaphoreGive(dataMutex);
                }
                saveToEEPROM(); 
                currentMenu = MENU_MAIN; 
            }
        }
        
        if (currentNextBtn && lastButtonNextState != currentNextBtn) {
            lastDebounceTime = currentMillis;
            Serial.println("AÇÃO: Botão NEXT pressionado");
            if (currentMenu == MAIN_SCREEN) { 
                currentPage = (currentPage + 1) % TOTAL_PAGES;
                Serial.print("Mudando para página: ");
                Serial.println(currentPage);
            } else if (currentMenu == MENU_MAIN) { 
                menuSelection = (menuSelection + 1) % 2; 
            } else if (currentMenu == MENU_SET_DENSITY) { 
                editValue += 0.01; 
                if (editValue > 5.0) editValue = 0.8; 
            } else if (currentMenu == MENU_SET_SPOOL_WEIGHT) { 
                // Alterado para incremento de 50g e range até 1000g
                editValue += 50.0; 
                if (editValue > 1000.0) editValue = 0.0; 
            }
        }
        
        if (currentBackBtn && lastButtonBackState != currentBackBtn) {
            lastDebounceTime = currentMillis;
            Serial.println("AÇÃO: Botão BACK pressionado");
            
            if (currentMenu == MAIN_SCREEN) {
                // Comportamento normal - voltar uma página
                currentPage = (currentPage - 1 + TOTAL_PAGES) % TOTAL_PAGES;
                Serial.print("Mudando para página: ");
                Serial.println(currentPage);
            } else if (currentMenu == MENU_MAIN) { 
                menuSelection = (menuSelection - 1 + 2) % 2; 
            } else if (currentMenu == MENU_SET_DENSITY) { 
                editValue -= 0.01; 
                if (editValue < 0.8) editValue = 5.0; 
            } else if (currentMenu == MENU_SET_SPOOL_WEIGHT) { 
                // Alterado para decremento de 50g e range até 1000g
                editValue -= 50.0; 
                if (editValue < 0.0) editValue = 1000.0; 
            }
        }
        
        lastButtonMenuState = currentMenuBtn; 
        lastButtonNextState = currentNextBtn; 
        lastButtonBackState = currentBackBtn;
        lastButtonSelectState = currentSelectBtn;
    }
}

void resetFilamentUsage(int boxNumber) {
    if (boxNumber < 0 || boxNumber >= 4) return;
    
    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
        filamentUsage[boxNumber] = 0;
        xSemaphoreGive(dataMutex);
    }
    
    saveToEEPROM();
    Serial.print("Uso de filamento resetado para caixa #");
    Serial.println(boxNumber + 1);
}

// Funções para os encoders com IRAM_ATTR para garantir execução rápida na ISR
void IRAM_ATTR handleEncoder1() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastEncoderTime[0] > 50) { // Debounce
        if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
            filamentUsage[0]++;
            xSemaphoreGive(dataMutex);
        }
        lastEncoderTime[0] = currentMillis;
    }
}

void IRAM_ATTR handleEncoder2() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastEncoderTime[1] > 50) { // Debounce
        if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
            filamentUsage[1]++;
            xSemaphoreGive(dataMutex);
        }
        lastEncoderTime[1] = currentMillis;
    }
}

void IRAM_ATTR handleEncoder3() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastEncoderTime[2] > 50) { // Debounce
        if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
            filamentUsage[2]++;
            xSemaphoreGive(dataMutex);
        }
        lastEncoderTime[2] = currentMillis;
    }
}

void IRAM_ATTR handleEncoder4() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastEncoderTime[3] > 50) { // Debounce
        if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
            filamentUsage[3]++;
            xSemaphoreGive(dataMutex);
        }
        lastEncoderTime[3] = currentMillis;
    }
}

void loadFromEEPROM() {
    uint32_t initFlag;
    
    // Ler o flag de inicialização
    EEPROM.get(EEPROM_INITIALIZED_ADDR, initFlag);
    
    if (initFlag == EEPROM_INIT_FLAG) {
        Serial.println("Lendo dados salvos da EEPROM...");
        
        // Ler densidades do filamento
        for (int i = 0; i < 4; i++) {
            float density;
            EEPROM.get(EEPROM_DENSITY_ADDR + i * sizeof(float), density);
            if (density >= 0.8 && density <= 5.0) {
                filamentDensity[i] = density;
            }
        }
        
        // Ler pesos dos carretéis
        for (int i = 0; i < 4; i++) {
            float weight;
            EEPROM.get(EEPROM_SPOOL_WEIGHT_ADDR + i * sizeof(float), weight);
            if (weight >= 0.0 && weight <= 1000.0) {
                spoolWeight[i] = weight;
            }
        }
        
        // Ler contagens de uso do filamento
        for (int i = 0; i < 4; i++) {
            unsigned long usage;
            EEPROM.get(EEPROM_USAGE_ADDR + i * sizeof(unsigned long), usage);
            filamentUsage[i] = usage;
        }
        
        Serial.println("Dados carregados com sucesso da EEPROM.");
    } else {
        Serial.println("Primeira execução ou formato de EEPROM alterado. Inicializando com valores padrão...");
        
        // Valores padrão
        for (int i = 0; i < 4; i++) {
            filamentDensity[i] = 1.24; // Densidade padrão PLA
            spoolWeight[i] = INITIAL_FILAMENT_WEIGHT_G; // Peso padrão do carretel
            filamentUsage[i] = 0; // Resetar contador de uso
        }
        
        // Salvar configuração inicial
        saveToEEPROM();
    }
}

void saveToEEPROM() {
    // Salvar flag de inicialização
    EEPROM.put(EEPROM_INITIALIZED_ADDR, EEPROM_INIT_FLAG);
    
    // Salvar densidades do filamento
    for (int i = 0; i < 4; i++) {
        EEPROM.put(EEPROM_DENSITY_ADDR + i * sizeof(float), filamentDensity[i]);
    }
    
    // Salvar pesos dos carretéis
    for (int i = 0; i < 4; i++) {
        EEPROM.put(EEPROM_SPOOL_WEIGHT_ADDR + i * sizeof(float), spoolWeight[i]);
    }
    
    // Salvar contagens de uso do filamento
    for (int i = 0; i < 4; i++) {
        EEPROM.put(EEPROM_USAGE_ADDR + i * sizeof(unsigned long), filamentUsage[i]);
    }
    
    EEPROM.commit(); // Importante para ESP32 - grava efetivamente na EEPROM
    Serial.println("Dados salvos na EEPROM com sucesso.");
}

float calculateRemainingWeight(int boxNumber) {
    float remainingWeight = 0.0;
    
    // Usar timeout para evitar bloqueio
    if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
        // Assumindo que cada tick do encoder representa 1mm de filamento
        float usedLength = filamentUsage[boxNumber]; // em mm
        
        // Converter para cm
        float usedLengthCm = usedLength / 10.0;
        
        // Cálculo da área transversal para filamento de 1.75mm (padrão para a maioria das impressoras)
        float radius = 1.75 / 2.0; // raio em mm
        float areaInCm2 = 3.14159 * radius * radius / 100.0; // área em cm²
        
        // Volume usado em cm³
        float usedVolume = areaInCm2 * usedLengthCm;
        
        // Peso usado em gramas (densidade em g/cm³)
        float usedWeight = usedVolume * filamentDensity[boxNumber];
        
        // Peso restante
        remainingWeight = spoolWeight[boxNumber] - usedWeight;
        
        xSemaphoreGive(dataMutex);
    }
    
    return remainingWeight;
}

float calculateRemainingLength(int boxNumber) {
    float remainingLength = 0.0;
    
    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
        // Comprimento já usado em mm
        float usedLength = filamentUsage[boxNumber];
        
        // Estimativa do comprimento total baseado no peso do carretel
        float radius = 1.75 / 2.0; // raio em mm
        float areaInCm2 = 3.14159 * radius * radius / 100.0; // área em cm²
        
        // Volume total em cm³ (peso em g / densidade em g/cm³)
        float totalVolume = spoolWeight[boxNumber] / filamentDensity[boxNumber];
        
        // Comprimento total em cm (volume em cm³ / área em cm²)
        float totalLengthCm = totalVolume / areaInCm2;
        
        // Conversão para mm
        float totalLength = totalLengthCm * 10.0;
        
        // Comprimento restante
        remainingLength = totalLength - usedLength;
        
        xSemaphoreGive(dataMutex);
    }
    
    return remainingLength;
}

float calculateRemainingPercentage(int boxNumber) {
    float percentage = 100.0;
    
    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
        // Se não temos peso de carretel, retorna 100%
        if (spoolWeight[boxNumber] <= 0) {
            xSemaphoreGive(dataMutex);
            return percentage;
        }
        
        // Calcular peso restante
        float remainingWeight = calculateRemainingWeight(boxNumber);
        
        // Calcular porcentagem (evitando divisão por zero)
        if (spoolWeight[boxNumber] > 0) {
            percentage = (remainingWeight / spoolWeight[boxNumber]) * 100.0;
        }
        
        // Limitar entre 0 e 100
        if (percentage < 0) percentage = 0;
        if (percentage > 100) percentage = 100;
        
        xSemaphoreGive(dataMutex);
    }
    
    return percentage;
}

void reconnectMqtt() {
    unsigned long currentMillis = millis();
    
    // Tentar reconectar apenas após um intervalo 
    if (currentMillis - lastMqttAttempt < MQTT_RECONNECT_INTERVAL) return;
    
    lastMqttAttempt = currentMillis;
    
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi desconectado. Tentando reconectar...");
        WiFi.reconnect();
        return;
    }
    
    Serial.print("Tentando conectar ao servidor MQTT... ");
    
    // Tentativa de conexão com timeout para não bloquear
    client.setSocketTimeout(2); // 2 segundos timeout
    
    // Tentativa de conexão
    if (client.connect(mqtt_client_id, mqtt_user, mqtt_password)) {
        Serial.println("Conectado!");
        
        // Inscrever-se em tópicos após conectar
        client.subscribe("filament_monitor/command/#");
        Serial.println("Inscrito no topico 'filament_monitor/command/#'");
        
        // Publicar mensagem de status online
        client.publish("filament_monitor/status", "online", true);
    } else {
        Serial.print("Falha, rc=");
        Serial.print(client.state());
        Serial.println(" Tentando novamente em 5 segundos");
    }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    // Converter payload para string para facilitar manipulação
    char message[length + 1];
    for (unsigned int i = 0; i < length; i++) {
        message[i] = (char)payload[i];
    }
    message[length] = '\0';
    
    Serial.print("Mensagem recebida no tópico [");
    Serial.print(topic);
    Serial.print("]: ");
    Serial.println(message);
    
    // Processar comandos
    if (strstr(topic, "filament_monitor/command/reset") != NULL) {
        int boxNumber = -1;
        
        // Verificar se é um comando para uma caixa específica
        if (sscanf(topic, "filament_monitor/command/reset/%d", &boxNumber) == 1) {
            if (boxNumber >= 1 && boxNumber <= 4) {
                resetFilamentUsage(boxNumber - 1);
                char responseTopic[50];
                sprintf(responseTopic, "filament_monitor/response/reset/%d", boxNumber);
                client.publish(responseTopic, "OK");
            }
        }
        // Ou se é um comando para todas as caixas
        else if (strcmp(message, "all") == 0) {
            for (int i = 0; i < 4; i++) {
                resetFilamentUsage(i);
            }
            client.publish("filament_monitor/response/reset", "All boxes reset");
        }
    }
    // Comando para configurar densidade
    else if (strstr(topic, "filament_monitor/command/density") != NULL) {
        int boxNumber = -1;
        float density = 0.0;
        
        if (sscanf(topic, "filament_monitor/command/density/%d", &boxNumber) == 1) {
            if (boxNumber >= 1 && boxNumber <= 4 && sscanf(message, "%f", &density) == 1) {
                if (density >= 0.8 && density <= 5.0) {
                    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
                        filamentDensity[boxNumber - 1] = density;
                        xSemaphoreGive(dataMutex);
                        saveToEEPROM();
                        
                        char responseTopic[50];
                        sprintf(responseTopic, "filament_monitor/response/density/%d", boxNumber);
                        char response[20];
                        sprintf(response, "%.2f", density);
                        client.publish(responseTopic, response);
                    }
                }
            }
        }
    }
    // Comando para configurar peso do carretel
    else if (strstr(topic, "filament_monitor/command/weight") != NULL) {
        int boxNumber = -1;
        float weight = 0.0;
        
        if (sscanf(topic, "filament_monitor/command/weight/%d", &boxNumber) == 1) {
            if (boxNumber >= 1 && boxNumber <= 4 && sscanf(message, "%f", &weight) == 1) {
                if (weight >= 0.0 && weight <= 1000.0) {
                    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
                        spoolWeight[boxNumber - 1] = weight;
                        // Também resetar o contador quando o peso é alterado via MQTT
                        filamentUsage[boxNumber - 1] = 0;
                        xSemaphoreGive(dataMutex);
                        saveToEEPROM();
                        
                        char responseTopic[50];
                        sprintf(responseTopic, "filament_monitor/response/weight/%d", boxNumber);
                        char response[20];
                        sprintf(response, "%.1f", weight);
                        client.publish(responseTopic, response);
                    }
                }
            }
        }
    }
}

void publishData() {
    if (!client.connected() || !mqttEnabled) return;
    
    char topic[50];
    char payload[20];
    
    // Publicar status do sistema primeiro (mais importante)
    client.publish("filament_monitor/status", "online", false);
    
    // Colocar um pequeno delay para não sobrecarregar
    vTaskDelay(5 / portTICK_PERIOD_MS);
    
    // Publicar dados para cada caixa
    for (int i = 0; i < 4; i++) {
        // Usar timeout para evitar bloqueios
        if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
            // Temperatura
            sprintf(topic, "filament_monitor/temperature/%d", i + 1);
            sprintf(payload, "%.1f", temperatures[i]);
            client.publish(topic, payload);
            
            // Pequeno delay entre publicações
            vTaskDelay(5 / portTICK_PERIOD_MS);
            
            // Umidade
            sprintf(topic, "filament_monitor/humidity/%d", i + 1);
            sprintf(payload, "%.1f", humidities[i]);
            client.publish(topic, payload);
            
            vTaskDelay(5 / portTICK_PERIOD_MS);
            
            // Uso do filamento
            sprintf(topic, "filament_monitor/usage/%d", i + 1);
            sprintf(payload, "%lu", filamentUsage[i]);
            client.publish(topic, payload);
            
            vTaskDelay(5 / portTICK_PERIOD_MS);
            
            // Densidade
            sprintf(topic, "filament_monitor/density/%d", i + 1);
            sprintf(payload, "%.2f", filamentDensity[i]);
            client.publish(topic, payload);
            
            vTaskDelay(5 / portTICK_PERIOD_MS);
            
            // Peso do carretel
            sprintf(topic, "filament_monitor/weight/%d", i + 1);
            sprintf(payload, "%.1f", spoolWeight[i]);
            client.publish(topic, payload);
            
            xSemaphoreGive(dataMutex);
            
            vTaskDelay(5 / portTICK_PERIOD_MS);
            
            // Dados calculados (usam funções que já usam semáforo)
            float remainingWeight = calculateRemainingWeight(i);
            sprintf(topic, "filament_monitor/remaining_weight/%d", i + 1);
            sprintf(payload, "%.1f", remainingWeight);
            client.publish(topic, payload);
            
            vTaskDelay(5 / portTICK_PERIOD_MS);
            
            float remainingPercentage = calculateRemainingPercentage(i);
            sprintf(topic, "filament_monitor/remaining_percentage/%d", i + 1);
            sprintf(payload, "%.1f", remainingPercentage);
            client.publish(topic, payload);
            
            vTaskDelay(5 / portTICK_PERIOD_MS);
        }
    }
    
    // Estatísticas do WiFi
    sprintf(payload, "%d", WiFi.RSSI());
    client.publish("filament_monitor/system/wifi_rssi", payload);
    
    // Tempo ligado
    sprintf(payload, "%lu", millis() / 1000);
    client.publish("filament_monitor/system/uptime", payload);
}

bool checkMqttConnection() {
    if (!client.connected()) {
        reconnectMqtt();
    }
    return client.connected();
}

// Função para verificar comandos via Serial para debug
void checkSerialCommands() {
    if (Serial.available() > 0) {
        String command = "";
        
        // Ler comando completo (até encontrar um caractere de controle como Enter)
        while (Serial.available() > 0) {
            char c = Serial.read();
            if (c >= 32 && c <= 126) { // Caracteres ASCII imprimíveis
                command += c;
            } else {
                break; // Caractere de controle, encerrar
            }
            delay(10); // Pequeno delay para garantir leitura completa
        }
        
        command.trim(); // Remover espaços
        Serial.print("Comando recebido: ");
        Serial.println(command);
        
        // Processar comando único
        if (command.length() == 1) {
            char cmd = command.charAt(0);
            switch (cmd) {
                case 'n': // Simular botão NEXT
                    Serial.println("Simulando botão NEXT");
                    lastButtonNextState = HIGH; // Para botões com PULLUP, inativo é HIGH
                    lastDebounceTime = 0;
                    break;
                case 'b': // Simular botão BACK
                    Serial.println("Simulando botão BACK");
                    lastButtonBackState = HIGH;
                    lastDebounceTime = 0;
                    break;
                case 'm': // Simular botão MENU
                    Serial.println("Simulando botão MENU");
                    lastButtonMenuState = HIGH;
                    lastDebounceTime = 0;
                    break;
                case 's': // Simular botão SELECT
                    Serial.println("Simulando botão SELECT");
                    lastButtonSelectState = HIGH;
                    lastDebounceTime = 0;
                    break;
                case 'q': // Toggle MQTT
                    mqttEnabled = !mqttEnabled;
                    Serial.print("MQTT: ");
                    Serial.println(mqttEnabled ? "ATIVADO" : "DESATIVADO");
                    
                    if (!mqttEnabled && client.connected()) {
                        client.disconnect();
                        Serial.println("Desconectado do servidor MQTT");
                    }
                    break;
                case '1': // Pulso único do encoder da caixa 1
                    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
                        filamentUsage[0]++;
                        xSemaphoreGive(dataMutex);
                        Serial.print("SIMULAÇÃO: Pulso do encoder da Caixa #1, Contador: ");
                        Serial.println(filamentUsage[0]);
                    }
                    break;
                case '2': // Pulso único do encoder da caixa 2
                    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
                        filamentUsage[1]++;
                        xSemaphoreGive(dataMutex);
                        Serial.print("SIMULAÇÃO: Pulso do encoder da Caixa #2, Contador: ");
                        Serial.println(filamentUsage[1]);
                    }
                    break;
                case '3': // Pulso único do encoder da caixa 3
                    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
                        filamentUsage[2]++;
                        xSemaphoreGive(dataMutex);
                        Serial.print("SIMULAÇÃO: Pulso do encoder da Caixa #3, Contador: ");
                        Serial.println(filamentUsage[2]);
                    }
                    break;
                case '4': // Pulso único do encoder da caixa 4
                    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
                        filamentUsage[3]++;
                        xSemaphoreGive(dataMutex);
                        Serial.print("SIMULAÇÃO: Pulso do encoder da Caixa #4, Contador: ");
                        Serial.println(filamentUsage[3]);
                    }
                    break;
            }
        } 
        // Processar comandos de simulação contínua
        else if (command.length() >= 3) {
            // Verificar se o comando é do formato "1on", "1off", "1on500", etc.
            char boxChar = command.charAt(0);
            int boxIndex = -1;
            
            if (boxChar >= '1' && boxChar <= '4') {
                boxIndex = boxChar - '1'; // Converter char para índice (0-3)
                
                // Verificar se o comando contém "on" e possivelmente um número
                if (command.indexOf("on") == 1) {
                    simulateEncoder[boxIndex] = true;
                    lastSimulatedPulse[boxIndex] = millis();
                    
                    // Verificar se há um valor de delay especificado após "on"
                    if (command.length() > 3) {
                        String delayStr = command.substring(3);
                        int delay = delayStr.toInt();
                        
                        // Validar o delay dentro dos limites
                        if (delay >= MIN_PULSE_INTERVAL && delay <= MAX_PULSE_INTERVAL) {
                            simulatePulseInterval[boxIndex] = delay;
                            Serial.print("SIMULAÇÃO CONTÍNUA: Iniciada para Caixa #");
                            Serial.print(boxIndex + 1);
                            Serial.print(" com intervalo de ");
                            Serial.print(delay);
                            Serial.println("ms");
                        } else {
                            Serial.print("SIMULAÇÃO CONTÍNUA: Iniciada para Caixa #");
                            Serial.print(boxIndex + 1);
                            Serial.println(" com intervalo padrão (1000ms)");
                            simulatePulseInterval[boxIndex] = 1000; // Valor padrão se fora dos limites
                        }
                    } else {
                        // Sem valor especificado, usar o padrão
                        simulatePulseInterval[boxIndex] = 1000;
                        Serial.print("SIMULAÇÃO CONTÍNUA: Iniciada para Caixa #");
                        Serial.print(boxIndex + 1);
                        Serial.println(" com intervalo padrão (1000ms)");
                    }
                } 
                else if (command.indexOf("off") == 1) {
                    simulateEncoder[boxIndex] = false;
                    Serial.print("SIMULAÇÃO CONTÍNUA: Finalizada para Caixa #");
                    Serial.println(boxIndex + 1);
                }
            }
        }
    }
}

// Função para verificar e processar a simulação de encoders
void checkEncoderSimulation() {
  unsigned long currentMillis = millis();
  
  for (int i = 0; i < 4; i++) {
    if (simulateEncoder[i] && (currentMillis - lastSimulatedPulse[i] >= simulatePulseInterval[i])) {
      // Tempo para simular um novo pulso
      if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE) {
        filamentUsage[i]++; // Simula sempre avanço do filamento
        xSemaphoreGive(dataMutex);
      }
      
      lastSimulatedPulse[i] = currentMillis;
      
      // Log do pulso simulado
      Serial.print("SIMULAÇÃO: Pulso do encoder da Caixa #");
      Serial.print(i + 1);
      Serial.print(", Contador: ");
      Serial.println(filamentUsage[i]);
    }
  }
}