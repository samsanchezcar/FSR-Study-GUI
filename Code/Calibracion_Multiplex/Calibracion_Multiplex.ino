#include <ArduinoBLE.h>

// Pines del MUX
#define MUX_SIG        A0
#define MUX_S0         2
#define MUX_S1         3

// Pin para el LED externo
#define LED_PIN        4

// BLE UUIDs
#define SERVICE_UUID       "a1b2c3d4-0001-1200-0000-00000000f012"
#define CHAR_CMD_UUID      "a1b2c3d4-0002-1200-0000-00000000f012"
#define CHAR_RESULT_UUID   "a1b2c3d4-0003-1200-0000-00000000f012"

// Estados de funcionamiento
enum Mode { IDLE, MENU, OPERACION, CALIBRACION };
Mode modo = MENU;
uint8_t canalCalib = 0;

// BLE
BLEService protsenService(SERVICE_UUID);
BLECharacteristic cmdCharacteristic(CHAR_CMD_UUID, BLEWrite, 20);
BLECharacteristic resultCharacteristic(CHAR_RESULT_UUID, BLERead | BLENotify, 32);

// Parpadeo LED
const unsigned long LED_INTERVAL = 1000;
unsigned long lastLedToggle = 0;
bool ledState = false;

// Prototipos
void mostrar_menu();
void onCommandReceived(BLEDevice central, BLECharacteristic chr);
void SetMuxChannel(uint8_t channel);
void funcion_operacion();
void takeCalibrationSample();

void setup() {
  pinMode(MUX_SIG, INPUT);
  pinMode(MUX_S0, OUTPUT);
  pinMode(MUX_S1, OUTPUT);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  delay(1000);  // Permitir inicialización incluso sin monitor serial

  // Solo esperar Serial si está conectado
  if (Serial) {
    while (!Serial);
  }

  if (!BLE.begin()) {
    Serial.println("ERROR: BLE no inicializado");
    while (1);
  }

  BLE.setLocalName("ProtsenFSR");
  BLE.setAdvertisedService(protsenService);
  protsenService.addCharacteristic(cmdCharacteristic);
  protsenService.addCharacteristic(resultCharacteristic);
  BLE.addService(protsenService);
  cmdCharacteristic.setEventHandler(BLEWritten, onCommandReceived);

  BLE.advertise();
  Serial.println("Esperando conexión BLE...");
}

void loop() {
  BLEDevice central = BLE.central();

  if (central) {
    Serial.print("Conectado a: "); Serial.println(central.address());
    mostrar_menu();

    while (central.connected()) {
      unsigned long now = millis();
      if (now - lastLedToggle >= LED_INTERVAL) {
        lastLedToggle = now;
        ledState = !ledState;
        digitalWrite(LED_PIN, ledState);
      }

      if (modo == OPERACION) {
        funcion_operacion();
      } else {
        delay(10);
      }
    }

    Serial.println("Desconectado BLE");
    digitalWrite(LED_PIN, LOW);
    modo = MENU;
    BLE.advertise();
  }
}

void mostrar_menu() {
  const char *menuStr =
    "Menu:\n"
    "o: Operacion\n"
    "b: Calibracion\n"
    "sN: Seleccionar canal N (0-3)\n"
    "t: Tomar 1 muestra de calibracion\n"
    "i: Idle\n";
  resultCharacteristic.writeValue(menuStr);
  Serial.println("Enviado menú BLE");
}

void onCommandReceived(BLEDevice, BLECharacteristic chr) {
  int len = chr.valueLength();
  char buf[21];
  chr.readValue((uint8_t*)buf, len);
  buf[len] = '\0';
  String cmd = String(buf);
  Serial.print("Cmd BLE: "); Serial.println(cmd);

  if (cmd == "o") {
    modo = OPERACION;
    resultCharacteristic.writeValue("Modo: Operacion");
  }
  else if (cmd == "b") {
    modo = CALIBRACION;
    resultCharacteristic.writeValue("Modo: Calibracion");
  }
  else if (cmd.startsWith("s")) {
    int c = cmd.substring(1).toInt();
    if (c >= 0 && c <= 3) {
      canalCalib = c;
      SetMuxChannel(canalCalib);
      char msg[32];
      snprintf(msg, sizeof(msg), "Canal seleccionado: S%u", canalCalib);
      resultCharacteristic.writeValue(msg);
    } else {
      resultCharacteristic.writeValue("Canal fuera de rango (0-3)");
    }
  }
  else if (cmd == "t" && modo == CALIBRACION) {
    takeCalibrationSample();
  }
  else if (cmd == "i") {
    modo = IDLE;
    resultCharacteristic.writeValue("Modo: Idle");
  }
  else {
    resultCharacteristic.writeValue("Comando no reconocido");
  }
}

void SetMuxChannel(uint8_t channel) {
  digitalWrite(MUX_S0, bitRead(channel, 0));
  digitalWrite(MUX_S1, bitRead(channel, 1));
}

void funcion_operacion() {
  for (uint8_t i = 0; i < 4; i++) {
    if (modo != OPERACION) return;
    SetMuxChannel(i);
    delay(490);  // Tiempo de asentamiento
    int lectura = analogRead(MUX_SIG);
    float valor = (lectura - 264) * (11.0 / 1023.0);
    valor = constrain(valor, 0.0, 11.0);

    char buf[32];
    snprintf(buf, sizeof(buf), "Op S%u:%.2f", i, valor);
    resultCharacteristic.writeValue(buf);
    Serial.println(buf);

    delay(10);
  }
}

void takeCalibrationSample() {
  SetMuxChannel(canalCalib);
  delay(100);
  int lectura = analogRead(MUX_SIG);
  char buf[32];
  snprintf(buf, sizeof(buf), "Calib S%u:%d", canalCalib, lectura);
  resultCharacteristic.writeValue(buf);
  Serial.println(buf);
}
