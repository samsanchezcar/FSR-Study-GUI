import asyncio
from bleak import BleakClient, BleakScanner

# UUIDs del servicio y características BLE
SERVICE_UUID      = "a1b2c3d4-0001-1200-0000-00000000f012"
CHAR_CMD_UUID     = "a1b2c3d4-0002-1200-0000-00000000f012"
CHAR_RESULT_UUID  = "a1b2c3d4-0003-1200-0000-00000000f012"

async def main():
    print("Buscando ProtsenFSR...")
    devices = await BleakScanner.discover()
    target = next((d for d in devices if d.name and "ProtsenFSR" in d.name), None)

    if not target:
        print("No se encontró el dispositivo ProtsenFSR.")
        return

    print(f"✅ Encontrado: {target.name} [{target.address}]")
    async with BleakClient(target.address) as client:
        print("Conectado al Nano RP2040 Connect")

        # Handler de notificaciones
        def notification_handler(handle, data):
            print(f"{data.decode().strip()}")

        await client.start_notify(CHAR_RESULT_UUID, notification_handler)

        menu = """
Selecciona acción:
 1) Modo Operación (leer 4 sensores)          → comando 'o'
 2) Modo Calibración (leer canal actual)      → comando 'b'
 3) Seleccionar Canal de Calibración (0–3)    → comando 'sX'
 4) Modo Idle                                 → comando 'i'
 5) Salir                                     → 'q'
"""

        while True:
            print(menu)
            choice = input("Opción: ").strip().lower()

            if choice == "1":
                cmd = "o"
            elif choice == "2":
                cmd = "b"
            elif choice == "3":
                canal = input("   Canal (0-3): ").strip()
                if canal not in ("0","1","2","3"):
                    print("⚠️ Canal inválido")
                    continue
                cmd = f"s{canal}"
            elif choice == "4":
                cmd = "i"
            elif choice in ("5", "q", "salir"):
                print("🔌 Desconectando…")
                break
            else:
                print("Opción inválida")
                continue

            await client.write_gatt_char(CHAR_CMD_UUID, cmd.encode())
            print(f"Enviado: '{cmd}'")
            await asyncio.sleep(0.5)

        await client.stop_notify(CHAR_RESULT_UUID)
        print("Desconectado.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    except Exception as e:
        print(f"Error inesperado: {e}")
