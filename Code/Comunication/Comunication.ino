#include <ArduinoBLE.h>

// UUIDs personalizados para Protsen v1.2
BLEService protsenService("a1b2c3d4-0001-1200-0000-00000000f012");  // Servicio principal
BLECharacteristic cmdCharacteristic("a1b2c3d4-0002-1200-0000-00000000f012", BLEWrite, 20);  // Comando desde PC
BLECharacteristic resultCharacteristic("a1b2c3d4-0003-1200-0000-00000000f012", BLERead | BLENotify, 20); // Respuesta

void setup() {
  Serial.begin(9600);
  while (!Serial);

  if (!BLE.begin()) {
    Serial.println("Fallo al iniciar BLE");
    while (1);
  }

  BLE.setLocalName("ProtsenFSR");
  BLE.setAdvertisedService(protsenService);

  protsenService.addCharacteristic(cmdCharacteristic);
  protsenService.addCharacteristic(resultCharacteristic);
  BLE.addService(protsenService);

  resultCharacteristic.writeValue("Listo v1.2");
  BLE.advertise();

  Serial.println("Esperando conexión BLE...");
}

void loop() {
  BLEDevice central = BLE.central();

  if (central) {
    Serial.print("Conectado a: ");
    Serial.println(central.address());

    while (central.connected()) {
      if (cmdCharacteristic.written()) {
        char comando = (char)cmdCharacteristic.value()[0];
        Serial.print("Comando recibido: ");
        Serial.println(comando);

        String respuesta;

        if (comando == 'p') {
          int valorFSR = analogRead(A0);
          respuesta = "Presion: " + String(valorFSR);
        } else if (comando == 'c') {
          respuesta = "Tiempo (s): " + String(millis() / 1000);
        } else if (comando == 'v') {
          respuesta = "Version: v1.2";
        } else {
          respuesta = "Comando no reconocido";
        }

        resultCharacteristic.writeValue(respuesta.c_str());
        Serial.println("Respuesta enviada: " + respuesta);
      }
    }

    Serial.println("Desconectado.");
    BLE.advertise();  // 🔄 volver a anunciarse para permitir nueva conexión
    Serial.println("Esperando nueva conexión BLE...");
  }
}
