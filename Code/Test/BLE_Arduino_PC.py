import asyncio
from bleak import BleakClient, BleakScanner

# UUIDs personalizados del proyecto Protsen v1.2
SERVICE_UUID = "a1b2c3d4-0001-1200-0000-00000000f012"
CHAR_COMMAND_UUID = "a1b2c3d4-0002-1200-0000-00000000f012"
CHAR_RESULT_UUID  = "a1b2c3d4-0003-1200-0000-00000000f012"

async def main():
    print("🔍 Buscando dispositivos BLE...")
    devices = await BleakScanner.discover()

    nano_address = None
    for d in devices:
        if d.name and "ProtsenFSR" in d.name:
            nano_address = d.address
            print(f"✅ Dispositivo encontrado: {d.name} ({nano_address})")
            break

    if not nano_address:
        print("❌ No se encontró el dispositivo ProtsenFSR.")
        return

    async with BleakClient(nano_address) as client:
        print("🔗 Conectado al Arduino Protsen v1.2")

        # Manejo de notificaciones
        def notification_handler(handle, data):
            print("📥 Respuesta del Arduino:", data.decode(errors="ignore"))

        await client.start_notify(CHAR_RESULT_UUID, notification_handler)

        while True:
            cmd = input("📤 Enviar comando ('p'=presión, 'c'=contador, 'v'=versión, 'q'=salir): ").strip().lower()
            if cmd == "q":
                break
            elif cmd not in ["p", "c", "v"]:
                print("⚠️ Comando inválido")
                continue

            await client.write_gatt_char(CHAR_COMMAND_UUID, cmd.encode())
            await asyncio.sleep(1)

        await client.stop_notify(CHAR_RESULT_UUID)
        print("🔌 Desconectado.")

# Ejecutar el script
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
