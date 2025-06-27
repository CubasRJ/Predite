#include "Ardu_Sec.h"
#include "thingProperties.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include <EmonLib.h>

#define ONE_WIRE_BUS 15
#define SW18010P_PIN 34
#define SCT013_PIN 35

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
EnergyMonitor emon;

unsigned long tempoAnterior = 0;
const unsigned long intervaloLeitura = 10000;
int pulsos = 0;
int ultimoEstado = LOW;

bool cloudIniciada = false;
bool cabecalhoEnviado = false;

const char* urlGoogleScript = "https://script.google.com/macros/s/AKfycbxKygvS-LmOcGA6MnEH8EnI5xFC1bxP2lSwYIpAdeXlt33WPdF4m9XXqUamewLHIj8/exec";
const char* nomePagina = "Maquina 1";

void conectarWiFi() {
  Serial.print("Conectando ao Wi-Fi");
  WiFi.begin(SECRET_WIFI_SSID, SECRET_WIFI_PASS);
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? "\nWi-Fi conectado!" : "\nFalha ao conectar ao Wi-Fi.");
}

void sincronizarRelogio() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) {
    Serial.println("Aguardando sincronização NTP...");
    delay(500);
  }
  Serial.println("Horário sincronizado.");
}

void enviarCabecalhoParaSheets() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(urlGoogleScript);
    http.addHeader("Content-Type", "application/json");

    String json = "{\"cabecalho\": true, \"linha\": [\"Data/Hora\", \"Temperatura\", \"Vibracao (Hz)\", \"Corrente (A)\"], \"pagina\": \"" + String(nomePagina) + "\"}";
    int resposta = http.POST(json);
    Serial.print("Cabeçalho enviado. Código de resposta: ");
    Serial.println(resposta);
    http.end();
    cabecalhoEnviado = true;
  }
}

void enviarDadosParaSheets(int tempC, float vibHz, int corrente) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(urlGoogleScript);
    http.addHeader("Content-Type", "application/json");

    char buffer[128];
    snprintf(buffer, sizeof(buffer),
             "{\"temperatura\": %d, \"vibracaoHz\": %.2f, \"correnteA\": %d, \"pagina\": \"%s\"}",
             tempC, vibHz, corrente, nomePagina);

    String json = String(buffer);
    Serial.print("Payload JSON enviado: ");
    Serial.println(json);

    int resposta = http.POST(json);
    Serial.print("Dados enviados. Código de resposta: ");
    Serial.println(resposta);
    http.end();
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  conectarWiFi();
  sincronizarRelogio();

  pinMode(SW18010P_PIN, INPUT);
  sensors.begin();
  emon.current(SCT013_PIN, 30.0);  // Ajuste conforme o modelo

  initProperties();

  if (WiFi.status() == WL_CONNECTED) {
    ArduinoCloud.begin(ArduinoIoTPreferredConnection);
    cloudIniciada = true;
  }

  setDebugMessageLevel(2);
  ArduinoCloud.printDebugInfo();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi desconectado! Tentando reconectar...");
    conectarWiFi();
    cloudIniciada = false;
    cabecalhoEnviado = false;
  }

  if (WiFi.status() == WL_CONNECTED && !ArduinoCloud.connected()) {
    if (!cloudIniciada) {
      Serial.println("Reconectando com Arduino Cloud...");
      ArduinoCloud.begin(ArduinoIoTPreferredConnection);
      cloudIniciada = true;
      delay(2000);
    }
  }

  ArduinoCloud.update();

  int valorAnalogico = analogRead(SW18010P_PIN);
  const int limiar = 300;
  if (valorAnalogico > limiar && ultimoEstado == LOW) {
    pulsos++;
    ultimoEstado = HIGH;
  } else if (valorAnalogico <= limiar) {
    ultimoEstado = LOW;
  }

  if (millis() - tempoAnterior >= intervaloLeitura) {
    tempoAnterior = millis();

    sensors.requestTemperatures();
    float tempC_float = sensors.getTempCByIndex(0);
    int tempC = (tempC_float != DEVICE_DISCONNECTED_C) ? round(tempC_float) : -127;

    float freqHz = pulsos / (intervaloLeitura / 1000.0);
    vibracaoHz = freqHz;
    pulsos = 0;

    float corrente_float = emon.calcIrms(1480);
    int corrente = round(corrente_float);

    temperatura = tempC;
    correnteA = corrente;

    Serial.print("Temperatura: ");
    Serial.print(temperatura);
    Serial.print(" °C | Vibração: ");
    Serial.print(vibracaoHz);
    Serial.print(" Hz | Corrente: ");
    Serial.print(correnteA);
    Serial.println(" A");

    if (!cabecalhoEnviado) {
      enviarCabecalhoParaSheets();
    }
    enviarDadosParaSheets(temperatura, vibracaoHz, correnteA);
  }
}
