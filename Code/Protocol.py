import asyncio
import csv
import os
import sys
import re
from bleak import BleakClient, BleakScanner, BleakError
import matplotlib.pyplot as plt
from Process.process_calibration import process_file
import threading

# directorio raíz de reportes
dir_processed = "Processed"
os.makedirs(dir_processed, exist_ok=True)

# UUIDs BLE
SERVICE_UUID     = "a1b2c3d4-0001-1200-0000-00000000f012"
CHAR_CMD_UUID    = "a1b2c3d4-0002-1200-0000-00000000f012"
CHAR_RESULT_UUID = "a1b2c3d4-0003-1200-0000-00000000f012"

# Carpeta raíz de datos
DIR_DATA = "Data"

# Variables globales
datos_por_peso = None
buffer_datos = []
peso_actual = None
sensor_actual = None
ble_client = None  # Cliente BLE global
ble_connected = False  # Estado de conexión BLE
calibration_canceled = False  # Bandera de cancelación

async def discover_and_connect(name_filter="ProtsenFSR", timeout=5, retries=5):
    global ble_client, ble_connected
    
    if ble_client and ble_client.is_connected:
        return ble_client
    
    address = None
    for i in range(1, retries+1):
        print(f"Escaneo BLE intento {i}/{retries}...")
        devices = await BleakScanner.discover(timeout=timeout)
        for d in devices:
            if d.name and name_filter in d.name:
                address = d.address
                print(f"Dispositivo encontrado: {d.name} [{address}]")
                break
        if address:
            break
    if not address:
        raise Exception("No se encontró el dispositivo BLE.")

    ble_client = BleakClient(address)
    for i in range(1, retries+1):
        try:
            print(f"Conectando intento {i}/{retries}...")
            await ble_client.connect(timeout=timeout)
            if ble_client.is_connected:
                ble_connected = True
                print("Conectado al dispositivo BLE.")
                return ble_client
        except (BleakError, asyncio.TimeoutError) as e:
            print(f"Fallo conexión: {e}")
    raise Exception("No se pudo conectar al dispositivo BLE.")

async def disconnect_ble():
    global ble_client, ble_connected
    if ble_client and ble_client.is_connected:
        await ble_client.disconnect()
        ble_client = None
        ble_connected = False
        print("Desconectado del dispositivo BLE.")
    return True

def ensure_sensor_folder(sensor):
    path = os.path.join(DIR_DATA, f"sensor{sensor}")
    os.makedirs(path, exist_ok=True)
    return path

def list_calibrations(sensor):
    folder = ensure_sensor_folder(sensor)
    files = []
    pattern = re.compile(rf"^calibracion_sensor{sensor}_(\d+)\.csv$")
    for fn in os.listdir(folder):
        m = pattern.match(fn)
        if m:
            files.append((int(m.group(1)), fn))
    files.sort()
    return [fn for _, fn in files]

def next_calibration_index(sensor):
    nums = []
    for fn in list_calibrations(sensor):
        m = re.search(rf"_{sensor}_(\d+)\.csv$", fn)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1

async def calibracion_ble(client):
    global datos_por_peso, buffer_datos, peso_actual, sensor_actual, calibration_canceled

    if not client.is_connected:
        raise Exception("BLE no conectado para calibración")

    # Handler BLE → buffer_datos
    def handler(_, data):
        msg = data.decode().strip()
        if msg.startswith("Calib"):
            buffer_datos.append(msg)

    await client.start_notify(CHAR_RESULT_UUID, handler)

    try:
        # Reset bandera de cancelación
        calibration_canceled = False
        
        # Número de muestras
        while datos_por_peso is None:
            try:
                datos_por_peso = int(input("Número de muestras por peso: "))
                if datos_por_peso <= 0:
                    print("Debe ser > 0.")
                    datos_por_peso = None
            except ValueError:
                print("Entrada inválida.")

        # Selección de sensor
        while True:
            s = input("Sensor (0-3): ").strip()
            if s in ("0","1","2","3"):
                sensor_actual = s
                await client.write_gatt_char(CHAR_CMD_UUID, f"s{sensor_actual}".encode())
                await asyncio.sleep(0.2)
                break
            print("Sensor inválido.")

        sensor_folder = ensure_sensor_folder(sensor_actual)

        # Menú de calibración
        while True:
            print(f"\n--- Gestión Sensor {sensor_actual} ---")
            print("(L)istar calibraciones")
            print("(N)ueva calibración automática")
            print("(D)eleción de calibración")
            print("(R)eportar calibración")
            print("(C)ancelar calibración")
            print("(Q)uitar a modo principal")
            opt = input("Opción: ").strip().lower()

            if opt == 'l':
                files = list_calibrations(sensor_actual)
                if not files:
                    print("  (vacío)")
                else:
                    for fn in files:
                        print(" ", fn)

            elif opt == 'd':
                files = list_calibrations(sensor_actual)
                if not files:
                    print("Nada que borrar.")
                    continue
                for i, fn in enumerate(files, 1):
                    print(f" {i}: {fn}")
                try:
                    idx = int(input("Número a borrar: "))
                    to_del = files[idx-1]

                    # 1) Borrar la calibración .csv
                    calib_path = os.path.join(sensor_folder, to_del)
                    os.remove(calib_path)
                    print(f"Eliminado calibración: {to_del}.")

                    # 2) Borrar todos los archivos procesados relacionados
                    report_folder = os.path.join(dir_processed, f"sensor{sensor_actual}")
                    basename = os.path.splitext(to_del)[0]  # sin extensión
                    for fname in os.listdir(report_folder):
                        if fname.startswith(basename):
                            os.remove(os.path.join(report_folder, fname))
                            print(f"Eliminado reporte: {fname}")

                except Exception:
                    print("Índice inválido.")

            elif opt == 'n':
                # Nueva calibración automática
                n = next_calibration_index(sensor_actual)
                filename = f"calibracion_sensor{sensor_actual}_{n}.csv"
                fullpath = os.path.join(sensor_folder, filename)
                with open(fullpath, 'w', newline='') as f:
                    csv.writer(f).writerow(['Sensor','Peso_g','Lectura'])
                print(f"Iniciando calibración: {filename}")
                print("Presione 'c' en cualquier momento para cancelar")

                await client.write_gatt_char(CHAR_CMD_UUID, b"b")
                await asyncio.sleep(0.5)

                for peso in range(250, 4001, 250):
                    if calibration_canceled:
                        print("Calibración cancelada por el usuario")
                        break
                        
                    print(f"\nPeso actual: {peso} g")
                    print(f"Coloque {peso}g en el sensor y presione Enter")
                    print("(C)ancelar calibración")
                    
                    user_input = input().strip().lower()
                    if user_input == 'c':
                        calibration_canceled = True
                        print("Calibración cancelada por el usuario")
                        break
                    
                    buffer_datos.clear()
                    print(f"Recolectando {datos_por_peso} muestras para {peso} g...")
                    
                    for i in range(datos_por_peso):
                        if calibration_canceled:
                            break
                            
                        # Verificar si el usuario quiere cancelar durante la recolección
                        if i > 0 and i % 5 == 0:  # Cada 5 muestras
                            print(f"Muestra {i+1}/{datos_por_peso} (presione 'c' para cancelar)")
                        else:
                            print(f"Muestra {i+1}/{datos_por_peso}")
                        
                        await client.write_gatt_char(CHAR_CMD_UUID, b"t")
                        await asyncio.sleep(0.1)
                        
                        # Esperar respuesta o posible cancelación
                        start_time = asyncio.get_event_loop().time()
                        while len(buffer_datos) <= i and not calibration_canceled:
                            elapsed = asyncio.get_event_loop().time() - start_time
                            if elapsed > 2.0:  # Timeout de 2 segundos
                                print("Timeout esperando respuesta, reintentando...")
                                await client.write_gatt_char(CHAR_CMD_UUID, b"t")
                                start_time = asyncio.get_event_loop().time()
                            await asyncio.sleep(0.1)
                            
                        # Verificar si el usuario presionó c durante la espera
                        if calibration_canceled:
                            break
                            
                        # Esperar 10 segundos entre muestras
                        if i < datos_por_peso - 1:
                            print("Esperando 10 segundos para próxima muestra...")
                            await asyncio.sleep(10)
                    
                    if calibration_canceled:
                        break
                        
                    # Guardar las muestras recolectadas para este peso
                    with open(fullpath, 'a', newline='') as f:
                        writer = csv.writer(f)
                        for msg in buffer_datos[:datos_por_peso]:
                            lectura = msg.split(':')[-1].strip()
                            writer.writerow([sensor_actual, peso, lectura])
                    print(f"Guardadas {min(len(buffer_datos), datos_por_peso)} muestras para {peso} g.")

                await client.write_gatt_char(CHAR_CMD_UUID, b"i")
                await asyncio.sleep(0.2)
                
                if not calibration_canceled:
                    print(f"Terminada calibración {filename}")
                else:
                    # Eliminar archivo si se canceló
                    if os.path.exists(fullpath):
                        os.remove(fullpath)
                        print("Archivo de calibración eliminado debido a cancelación")

            elif opt == 'c':
                calibration_canceled = True
                print("Calibración marcada para cancelación en el próximo paso")

            elif opt == 'r':
                files = list_calibrations(sensor_actual)
                if not files:
                    print("No hay calibraciones para reportar.")
                    continue
                for i, fn in enumerate(files, 1):
                    print(f" {i}: {fn}")
                try:
                    sel = int(input("Selecciona número a reportar: "))
                    fn = files[sel-1]
                except Exception:
                    print("Selección inválida.")
                    continue

                full_csv = os.path.join(sensor_folder, fn)
                out_dir  = os.path.join(dir_processed, f"sensor{sensor_actual}")
                os.makedirs(out_dir, exist_ok=True)

                print(f"\nProcesando {fn} …")
                props_df, plot_png = process_file(full_csv, out_dir)

                # Mostrar propiedades
                print("\n=== Propiedades estáticas ===")
                print(props_df.to_string(index=False))

                # Mostrar gráfica
                try:
                    img = plt.imread(plot_png)
                    plt.figure(figsize=(6,4))
                    plt.imshow(img)
                    plt.axis('off')
                    plt.title(f"Regresión: {fn}")
                    plt.show()
                except Exception as e:
                    print(f"No pude abrir la gráfica: {e}")

            elif opt == 'q':
                break
            else:
                print("Opción inválida.")

    finally:
        await client.write_gatt_char(CHAR_CMD_UUID, b"i")
        await asyncio.sleep(0.2)
        await client.stop_notify(CHAR_RESULT_UUID)

async def operacion_ble(client):
    import threading

    if not client.is_connected:
        raise Exception("BLE no conectado para operación")
    
    os.makedirs(DIR_DATA, exist_ok=True)
    op_path = os.path.join(DIR_DATA, "operacion.csv")
    nuevo = not os.path.exists(op_path)
    with open(op_path, 'a', newline='') as f:
        if nuevo:
            csv.writer(f).writerow(['Sensor','Valor'])

    def handler_save(_, data):
        msg = data.decode().strip()
        if msg.startswith("Op S"):
            parts = msg[4:].split(':')
            canal = int(parts[0]); valor = float(parts[1])
            with open(op_path, 'a', newline='') as f2:
                csv.writer(f2).writerow([canal, f"{valor:.2f}"])
            print(f"Sensor {canal} = {valor:.2f}")

    await client.start_notify(CHAR_RESULT_UUID, handler_save)
    await client.write_gatt_char(CHAR_CMD_UUID, b"o")
    await asyncio.sleep(0.2)

    print("Recolección en curso. Presiona Enter para detener...")
    stop_event = asyncio.Event()

    def esperar_enter():
        input()
        asyncio.run_coroutine_threadsafe(stop_event.set(), asyncio.get_event_loop())
    threading.Thread(target=esperar_enter, daemon=True).start()

    await stop_event.wait()

    await client.write_gatt_char(CHAR_CMD_UUID, b"i")
    await asyncio.sleep(0.2)
    await client.stop_notify(CHAR_RESULT_UUID)
    print("Modo operación finalizado.")

def gestion_calibraciones_offline():
    # Selección de sensor
    while True:
        s = input("Sensor a gestionar (0-3, o enter para volver): ").strip()
        if not s:
            return
        if s not in ("0","1","2","3"):
            print("Sensor inválido.")
            continue

        folder = ensure_sensor_folder(s)
        out_dir = os.path.join(dir_processed, f"sensor{s}")
        os.makedirs(out_dir, exist_ok=True)

        while True:
            print(f"\n--- Gestión offline Sensor {s} ---")
            print("(L)istar calibraciones")
            print("(D)eleción de calibración")
            print("(R)eportar calibración")
            print("(Q)uitar gestión sensor")
            opt2 = input("Opción: ").strip().lower()

            if opt2 == 'l':
                files = list_calibrations(s)
                if not files:
                    print("  (vacío)")
                else:
                    for fn in files:
                        print(" ", fn)

            elif opt2 == 'd':
                files = list_calibrations(s)
                if not files:
                    print("Nada que borrar.")
                    continue
                for i, fn in enumerate(files, 1):
                    print(f" {i}: {fn}")
                try:
                    idx = int(input("Número a borrar: "))
                    to_del = files[idx-1]

                    # 1) Borrar la calibración .csv
                    calib_path = os.path.join(folder, to_del)
                    os.remove(calib_path)
                    print(f"Eliminado calibración: {to_del}.")

                    # 2) Borrar todos los archivos procesados relacionados
                    report_folder = os.path.join(dir_processed, f"sensor{s}")
                    basename = os.path.splitext(to_del)[0]  # sin extensión
                    for fname in os.listdir(report_folder):
                        if fname.startswith(basename):
                            os.remove(os.path.join(report_folder, fname))
                            print(f"Eliminado reporte: {fname}")

                except Exception:
                    print("Índice inválido.")

            elif opt2 == 'r':
                files = list_calibrations(s)
                if not files:
                    print("No hay calibraciones para reportar.")
                    continue
                for i, fn in enumerate(files, 1):
                    print(f" {i}: {fn}")
                try:
                    sel = int(input("Selecciona número a reportar: "))
                    fn = files[sel-1]
                except:
                    print("Selección inválida.")
                    continue

                csv_path = os.path.join(folder, fn)
                print(f"\nProcesando {fn} …")
                props_df, plot_png = process_file(csv_path, out_dir)

                print("\n=== Propiedades estáticas ===")
                print(props_df.to_string(index=False))

                # Mostrar gráfica
                try:
                    img = plt.imread(plot_png)
                    plt.figure(figsize=(6,4))
                    plt.imshow(img)
                    plt.axis('off')
                    plt.title(f"Regresión: {fn}")
                    plt.show()
                except Exception as e:
                    print(f"No pude abrir la gráfica: {e}")

            elif opt2 == 'q':
                break
            else:
                print("Opción inválida.")


async def main():
    global ble_client, ble_connected
    
    while True:
        print("\n== Menú Principal ==")
        print("1 - Calibración          (requiere BLE)")
        print("2 - Operación            (requiere BLE)")
        print("3 - Gestión calibraciones (offline)")
        print("4 - Conectar BLE")
        print("5 - Desconectar BLE")
        print("q - Salir")
        opt = input("Opción: ").strip().lower()

        if opt == '1':
            if not ble_connected:
                print("Primero debe conectar BLE")
                continue
            try:
                await calibracion_ble(ble_client)
            except Exception as e:
                print(f"Error en calibración: {e}")
        
        elif opt == '2':
            if not ble_connected:
                print("Primero debe conectar BLE")
                continue
            try:
                await operacion_ble(ble_client)
            except Exception as e:
                print(f"Error en operación: {e}")
        
        elif opt == '3':
            # Gestión de archivos y reportes sin BLE
            gestion_calibraciones_offline()
        
        elif opt == '4':
            try:
                await discover_and_connect()
                print("BLE conectado exitosamente")
            except Exception as e:
                print(f"Error de conexión: {e}")
        
        elif opt == '5':
            if ble_connected:
                await disconnect_ble()
                print("BLE desconectado")
            else:
                print("BLE ya desconectado")
        
        elif opt == 'q':
            if ble_connected:
                await disconnect_ble()
            print("Saliendo.")
            break
        
        else:
            print("Opción inválida.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrumpido por usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# ================== FUNCIONES WRAPPER PARA GUI ==================

class CalibrationProgress:
    """Clase para manejar callbacks de progreso y confirmaciones"""
    def __init__(self):
        self.confirmed = False
        self.progress_callback = None
        self.cancel_event = None

# Instancia global para manejar confirmaciones
_progress_handler = CalibrationProgress()

def set_progress_callback(callback):
    """Establece el callback de progreso para la GUI"""
    _progress_handler.progress_callback = callback

def confirm_weight():
    """Confirma que el peso ha sido colocado"""
    _progress_handler.confirmed = True

def set_cancel_event(event):
    """Establece el evento de cancelación"""
    _progress_handler.cancel_event = event

async def calibracion_ble_wrapper(samples, sensor):
    """Wrapper para calibración BLE desde GUI"""
    global buffer_datos, sensor_actual, calibration_canceled
    
    # Verificar conexión BLE
    if not ble_connected or not ble_client or not ble_client.is_connected:
        raise Exception("BLE no conectado")
    
    # Inicializar variables
    buffer_datos = []
    sensor_actual = sensor
    calibration_canceled = False
    
    try:
        # Handler BLE → buffer_datos
        def handler(_, data):
            msg = data.decode().strip()
            if msg.startswith("Calib"):
                buffer_datos.append(msg)
        
        await ble_client.start_notify(CHAR_RESULT_UUID, handler)
        
        # Configurar sensor
        await ble_client.write_gatt_char(CHAR_CMD_UUID, f"s{sensor_actual}".encode())
        await asyncio.sleep(0.2)
        
        # Crear archivo de calibración
        n = next_calibration_index(sensor_actual)
        filename = f"calibracion_sensor{sensor_actual}_{n}.csv"
        sensor_folder = ensure_sensor_folder(sensor_actual)
        fullpath = os.path.join(sensor_folder, filename)
        
        with open(fullpath, 'w', newline='') as f:
            csv.writer(f).writerow(['Sensor','Peso_g','Lectura'])
        
        # Iniciar modo calibración
        await ble_client.write_gatt_char(CHAR_CMD_UUID, b"b")
        await asyncio.sleep(0.5)
        
        weights = list(range(250, 4001, 250))
        total_steps = len(weights) * samples
        current_step = 0
        
        for peso in weights:
            # Verificar cancelación
            if (calibration_canceled or 
                (_progress_handler.cancel_event and _progress_handler.cancel_event.is_set())):
                break
                
            # Notificar a la GUI que espere confirmación
            if _progress_handler.progress_callback:
                _progress_handler.progress_callback(
                    current_step, 
                    total_steps, 
                    f"Coloque {peso}g en el sensor y presione Continuar",
                    {'peso_actual': peso, 'esperar_confirmacion': True}
                )
            
            # Esperar confirmación del usuario
            _progress_handler.confirmed = False
            while not _progress_handler.confirmed and not calibration_canceled:
                if (_progress_handler.cancel_event and 
                    _progress_handler.cancel_event.is_set()):
                    calibration_canceled = True
                    break
                await asyncio.sleep(0.1)
            
            if calibration_canceled:
                break
                
            # Limpiar buffer y recolectar muestras
            buffer_datos.clear()
            
            for i in range(samples):
                if (calibration_canceled or 
                    (_progress_handler.cancel_event and _progress_handler.cancel_event.is_set())):
                    break
                    
                current_step += 1
                
                # Actualizar progreso
                if _progress_handler.progress_callback:
                    _progress_handler.progress_callback(
                        current_step, 
                        total_steps, 
                        f"Recolectando muestra {i+1}/{samples} para {peso}g",
                        {'muestra_actual': i+1, 'muestras_total': samples}
                    )
                
                # Solicitar muestra
                await ble_client.write_gatt_char(CHAR_CMD_UUID, b"t")
                
                # Esperar respuesta con timeout
                start_time = asyncio.get_event_loop().time()
                while len(buffer_datos) <= i:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > 2.0:  # Timeout de 2 segundos
                        await ble_client.write_gatt_char(CHAR_CMD_UUID, b"t")
                        start_time = asyncio.get_event_loop().time()
                    
                    if (calibration_canceled or 
                        (_progress_handler.cancel_event and _progress_handler.cancel_event.is_set())):
                        break
                        
                    await asyncio.sleep(0.1)
                
                if calibration_canceled:
                    break
                    
                # Esperar entre muestras (excepto la última)
                if i < samples - 1:
                    for sec in range(10, 0, -1):
                        if (calibration_canceled or 
                            (_progress_handler.cancel_event and _progress_handler.cancel_event.is_set())):
                            break
                            
                        if _progress_handler.progress_callback:
                            _progress_handler.progress_callback(
                                current_step,
                                total_steps,
                                f"Esperando {sec} segundos para próxima muestra...",
                                {'espera_segundos': sec}
                            )
                        await asyncio.sleep(1)
            
            if calibration_canceled:
                break
                
            # Guardar muestras para este peso
            with open(fullpath, 'a', newline='') as f:
                writer = csv.writer(f)
                for msg in buffer_datos[:samples]:
                    lectura = msg.split(':')[-1].strip()
                    writer.writerow([sensor_actual, peso, lectura])
        
        # Finalizar modo calibración
        await ble_client.write_gatt_char(CHAR_CMD_UUID, b"i")
        await asyncio.sleep(0.2)
        await ble_client.stop_notify(CHAR_RESULT_UUID)
        
        # Verificar si se completó o se canceló
        if calibration_canceled:
            if os.path.exists(fullpath):
                os.remove(fullpath)
            return None
        else:
            return fullpath
            
    except Exception as e:
        # Limpiar en caso de error
        try:
            await ble_client.write_gatt_char(CHAR_CMD_UUID, b"i")
            await ble_client.stop_notify(CHAR_RESULT_UUID)
        except:
            pass
        
        if 'fullpath' in locals() and os.path.exists(fullpath):
            os.remove(fullpath)
        raise e

async def operacion_ble_wrapper():
    """Wrapper para operación BLE desde GUI"""
    if not ble_connected or not ble_client:
        raise Exception("BLE no conectado")
    
    try:
        await operacion_ble(ble_client)
    finally:
        pass  # No desconectar automáticamente

async def connect_ble_wrapper():
    """Wrapper para conectar BLE desde GUI"""
    return await discover_and_connect()

async def disconnect_ble_wrapper():
    """Wrapper para desconectar BLE desde GUI"""
    return await disconnect_ble()

def is_ble_connected():
    """Verifica si BLE está conectado"""
    return ble_connected and ble_client and ble_client.is_connected