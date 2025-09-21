#include <ArduinoBLE.h>

// Pines MUX
#define MUX_SIG  A0   // Entrada analógica
#define MUX_S0   2    // Selector bit 0
#define MUX_S1   3    // Selector bit 1

// Pin para LED de estado (parpadeo)
#define LED_PIN 3     // D3

// BLE UUIDs
#define SERVICE_UUID      "a1b2c3d4-0001-1200-0000-00000000f012"
#define CHAR_CMD_UUID     "a1b2c3d4-0002-1200-0000-00000000f012"
#define CHAR_RESULT_UUID  "a1b2c3d4-0003-1200-0000-00000000f012"

// Modos de operación
enum Mode { IDLE, OPERACION, CALIBRACION };
Mode modo = IDLE;
uint8_t canalCalib = 0;

// Servicio y características BLE
BLEService protsenService(SERVICE_UUID);
BLECharacteristic cmdCharacteristic(CHAR_CMD_UUID, BLEWrite, 20);
BLECharacteristic resultCharacteristic(CHAR_RESULT_UUID, BLERead | BLENotify, 32);

// Variables para parpadeo con millis()
unsigned long previousBlink = 0;
const unsigned long blinkInterval = 1000;
bool ledState = false;

// Prototipos de funciones
void onCommandReceived(BLEDevice central, BLECharacteristic chr);
void SetMuxChannel(uint8_t channel);
void funcion_operacion();
void funcion_calibracion(uint8_t canal);

void setup() {
  // Configura pines multiplexor y LED
  pinMode(MUX_SIG, INPUT);
  pinMode(MUX_S0, OUTPUT);
  pinMode(MUX_S1, OUTPUT);
  pinMode(LED_PIN, OUTPUT);

  Serial.begin(115200);
  while (!Serial);

  // Inicializa BLE
  if (!BLE.begin()) {
    Serial.println("ERROR: inicializacion BLE fallida");
    while (1);
  }

  BLE.setLocalName("ProtsenFSR");
  BLE.setAdvertisedService(protsenService);
  protsenService.addCharacteristic(cmdCharacteristic);
  protsenService.addCharacteristic(resultCharacteristic);
  BLE.addService(protsenService);

  resultCharacteristic.writeValue("Ready v1.2");
  BLE.advertise();
  Serial.println("BLE listo");

  // Asigna manejador de escritura de comandos
  cmdCharacteristic.setEventHandler(BLEWritten, onCommandReceived);
}

void loop() {
  // Parpadeo de LED sin bloquear
  unsigned long currentMillis = millis();
  if (currentMillis - previousBlink >= blinkInterval) {
    previousBlink = currentMillis;
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState);
  }

  // Reanuncia publicidad si no hay conexión
  if (!BLE.connected()) {
    BLE.advertise();
    return;
  }

  // Procesa conexión central
  BLEDevice central = BLE.central();
  Serial.print("Conectado a: ");
  Serial.println(central.address());

  while (central.connected()) {
    switch (modo) {
      case OPERACION:
        funcion_operacion();
        break;
      case CALIBRACION:
        funcion_calibracion(canalCalib);
        break;
      case IDLE:
      default:
        delay(100);
        break;
    }
  }

  // Al desconectar, reanuncia servicio
  Serial.println("Desconectado");
  BLE.advertise();
}

void onCommandReceived(BLEDevice central, BLECharacteristic chr) {
  int len = chr.valueLength();
  uint8_t buf[21];
  chr.readValue(buf, len);
  buf[len] = '\0';
  String cmd = String((char*)buf);

  if (cmd == "o") {
    modo = OPERACION;
    resultCharacteristic.writeValue("Modo: Operacion");
  } else if (cmd == "b") {
    modo = CALIBRACION;
    char msg[32];
    snprintf(msg, sizeof(msg), "Modo: Calibracion, Canal=%u", canalCalib);
    resultCharacteristic.writeValue(msg);
  } else if (cmd.startsWith("s")) {
    uint8_t c = cmd.substring(1).toInt();
    if (c < 4) {
      canalCalib = c;
      char msg[32];
      snprintf(msg, sizeof(msg), "Canal Calib set a %u", canalCalib);
      resultCharacteristic.writeValue(msg);
    } else {
      resultCharacteristic.writeValue("Error: canal fuera de rango");
    }
  } else if (cmd == "i") {
    modo = IDLE;
    resultCharacteristic.writeValue("Modo: Idle");
  } else {
    resultCharacteristic.writeValue("Cmd no reconocido");
  }
}

void SetMuxChannel(uint8_t channel) {
  digitalWrite(MUX_S0, bitRead(channel, 0));
  digitalWrite(MUX_S1, bitRead(channel, 1));
}

void funcion_operacion() {
  String outStr;
  for (uint8_t i = 0; i < 4; i++) {
    SetMuxChannel(i);
    delay(10);
    int lectura = analogRead(MUX_SIG);
    float valor = (lectura - 264) * (1.0 / 1023.0)x * 11.0;
    valor = constrain(valor, 0.0, 11.0);
    outStr += "S" + String(i) + ":" + String(valor, 2) + " ";
  }

  resultCharacteristic.writeValue(outStr.c_str());
  Serial.println(outStr);
  delay(500);
}

void funcion_calibracion(uint8_t canal) {
  SetMuxChannel(canal);
  delay(10);
  int lectura = analogRead(MUX_SIG);
  char buf[32];
  snprintf(buf, sizeof(buf), "Calib S%u:%d", canal, lectura);
  resultCharacteristic.writeValue(buf);
  Serial.println(buf);
  delay(500);
}
