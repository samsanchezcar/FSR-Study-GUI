import sys
import asyncio
import os
from PyQt5 import QtCore, QtWidgets, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Process.process_calibration import process_file
import Protocol
import threading

# Colores actualizados
PALETTE = {
    'primary':    "#506CFB",  # Azul principal
    'accent':     "#5D80D9",  # Púrpura para acentos
    'background': "#FFFFFF",  # Fondo blanco
    'text':       "#FFFFFF",  # Texto en botones
    'connected':  "#2ECC71",  # Verde para estado conectado
    'disconnected': "#E74C3C" # Rojo para estado desconectado
}

class BLEWorker(QtCore.QThread):
    """Ejecuta corutinas BLE sin bloquear la UI."""
    finished = QtCore.pyqtSignal(object)
    error    = QtCore.pyqtSignal(str)
    status_update = QtCore.pyqtSignal(str, str)  # message, color
    progress_update = QtCore.pyqtSignal(int, int, str, dict)  # current, total, message, extra_data
    confirmation_required = QtCore.pyqtSignal(int)  # peso actual
    operation_log = QtCore.pyqtSignal(str)  # mensajes de operación

    def __init__(self, coro, *args):
        super().__init__()
        self.coro = coro
        self.args = args
        self._loop = asyncio.new_event_loop()
        self._stopped = False
        self.cancel_event = threading.Event()
        self.confirm_event = threading.Event()

    def run(self):
        try:
            # Configurar handler de progreso
            Protocol.set_progress_callback(self._progress_callback)
            Protocol.set_cancel_event(self.cancel_event)
            
            # Ejecutar en el loop de este hilo
            asyncio.set_event_loop(self._loop)
            res = self._loop.run_until_complete(self.coro(*self.args))
            if not self._stopped:
                self.finished.emit(res)
        except Exception as e:
            if not self._stopped:
                self.error.emit(str(e))
        finally:
            self._loop.close()

    def stop(self):
        """Detiene el hilo de forma segura"""
        self._stopped = True
        self.cancel_event.set()
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.wait()

    def _progress_callback(self, current, total, message, extra_data):
        """Envía actualizaciones de progreso a la GUI"""
        self.progress_update.emit(current, total, message, extra_data)
        
        # Si se requiere confirmación, emitir señal especial
        if extra_data.get('esperar_confirmacion', False):
            self.confirmation_required.emit(extra_data['peso_actual'])

    def confirm_weight(self):
        """Confirma que el peso ha sido colocado"""
        self.confirm_event.set()
        Protocol.confirm_weight()

class PlotCanvas(FigureCanvas):
    """Canvas para mostrar imágenes o gráficas."""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor(PALETTE['background'])
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)

    def show_image(self, path):
        import matplotlib.image as mpimg
        self.ax.clear()
        img = mpimg.imread(path)
        self.ax.imshow(img)
        self.ax.axis('off')
        self.draw()

class StatusIndicator(QtWidgets.QWidget):
    """Widget para mostrar un círculo de estado y un texto."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Círculo de estado
        self.indicator = QtWidgets.QLabel()
        self.indicator.setFixedSize(16, 16)
        self.indicator.setStyleSheet("background: #E74C3C; border-radius: 8px;")
        
        # Texto
        self.text = QtWidgets.QLabel("Desconectado")
        self.text.setStyleSheet("color: white; font-weight: bold;")
        
        layout.addWidget(self.indicator)
        layout.addWidget(self.text)
        layout.addStretch()

    def set_status(self, connected):
        if connected:
            self.indicator.setStyleSheet("background: #2ECC71; border-radius: 8px;")
            self.text.setText("Conectado")
        else:
            self.indicator.setStyleSheet("background: #E74C3C; border-radius: 8px;")
            self.text.setText("Desconectado")

class CalibrationDialog(QtWidgets.QDialog):
    """Diálogo para mostrar progreso de calibración"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibración en Progreso")
        self.setFixedSize(500, 300)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Barra de progreso
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # Etiqueta de estado
        self.status_label = QtWidgets.QLabel("Preparando calibración...")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Etiqueta de tiempo de espera
        self.wait_label = QtWidgets.QLabel("")
        self.wait_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.wait_label)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        self.confirm_btn = QtWidgets.QPushButton("Confirmar Peso")
        self.confirm_btn.setVisible(False)
        self.cancel_btn = QtWidgets.QPushButton("Cancelar")
        
        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        # Conexiones
        self.confirm_btn.clicked.connect(self.confirm)
        self.cancel_btn.clicked.connect(self.cancel)
        
        # Variables
        self.worker = None
        self.current_weight = 0
    
    def set_worker(self, worker):
        """Establece el worker asociado"""
        self.worker = worker
        self.worker.progress_update.connect(self.update_progress)
        self.worker.confirmation_required.connect(self.request_confirmation)
        self.worker.finished.connect(self.accept)
        self.worker.error.connect(self.reject)
    
    def update_progress(self, current, total, message, extra_data):
        """Actualiza la interfaz con el progreso"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        
        self.status_label.setText(message)
        
        # Mostrar cuenta regresiva si está disponible
        if 'espera_segundos' in extra_data:
            secs = extra_data['espera_segundos']
            self.wait_label.setText(f"Tiempo restante: {secs} segundos")
        else:
            self.wait_label.setText("")
    
    def request_confirmation(self, peso):
        """Solicita confirmación de peso colocado"""
        self.current_weight = peso
        self.confirm_btn.setVisible(True)
        self.status_label.setText(f"Coloque {peso}g en el sensor y presione Confirmar")
    
    def confirm(self):
        """Confirma que el peso ha sido colocado"""
        if self.worker:
            self.worker.confirm_weight()
        self.confirm_btn.setVisible(False)
    
    def cancel(self):
        """Cancela la calibración"""
        if self.worker:
            self.worker.cancel_event.set()
        self.reject()

class WelcomePage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        
        title = QtWidgets.QLabel("Bienvenido a ProtsenFSR Controller")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #506CFB;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        
        subtitle = QtWidgets.QLabel("Sistema de calibración y operación de sensores FSR")
        subtitle.setStyleSheet("font-size: 16px; color: #5D80D9;")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        
        logo = QtWidgets.QLabel()
        logo_path = os.path.join('Img','ProtosUN.jpg')
        if os.path.exists(logo_path):
            px = QtGui.QPixmap(logo_path).scaled(300, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            logo.setPixmap(px)
        logo.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(30)
        layout.addWidget(logo)
        layout.addStretch()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ProtsenFSR Controller')
        self.resize(1000, 600)
        # Estilos globales
        self.setStyleSheet(f"""
            QMainWindow {{ background: {PALETTE['background']}; }}
            QLabel#title {{ font-size: 22px; font-weight: bold; margin: 12px; color: {PALETTE['primary']}; }}
            QPushButton {{
                background: {PALETTE['primary']};
                color: {PALETTE['text']};
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {PALETTE['accent']};
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #666666;
            }}
            QListWidget {{
                border: 1px solid #DDDDDD;
                border-radius: 5px;
                background: #FFFFFF;
            }}
            QTextEdit {{
                border: 1px solid #DDDDDD;
                border-radius: 5px;
                background: #FFFFFF;
            }}
            QFormLayout QLabel {{
                font-weight: bold;
                color: {PALETTE['primary']};
            }}
        """)
        # Sidebar con gradiente y logo
        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0,y1:0,x2:0,y2:1,
                    stop:0 {PALETTE['primary']}, stop:1 {PALETTE['accent']}
                );
                border-top-right-radius: 20px;
                border-bottom-right-radius: 20px;
            }}
        """)
        sb_layout = QtWidgets.QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(10,20,10,20)
        sb_layout.setSpacing(15)
        # Logo
        logo = QtWidgets.QLabel()
        logo_path = os.path.join('Img','ProtosUN.jpg')
        if os.path.exists(logo_path):
            px = QtGui.QPixmap(logo_path).scaled(180,80,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
            logo.setPixmap(px)
        logo.setAlignment(QtCore.Qt.AlignCenter)
        sb_layout.addWidget(logo)
        
        # Estado BLE
        self.ble_status_indicator = StatusIndicator()
        sb_layout.addWidget(self.ble_status_indicator)
        
        # Botones Conexión
        self.btn_connect = QtWidgets.QPushButton('Conectar BLE')
        self.btn_disconnect = QtWidgets.QPushButton('Desconectar BLE')
        self.btn_disconnect.setEnabled(False)  # Inicialmente desconectado
        
        for btn in (self.btn_connect, self.btn_disconnect):
            btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            btn.setFixedHeight(40)
            sb_layout.addWidget(btn)
        
        # Botones Nav
        self.btn_calib = QtWidgets.QPushButton('Calibración BLE')
        self.btn_oper  = QtWidgets.QPushButton('Operación BLE')
        self.btn_off   = QtWidgets.QPushButton('Offline')
        # Inicialmente deshabilitados hasta conectar
        self.btn_calib.setEnabled(False)
        self.btn_oper.setEnabled(False)
        
        for btn in (self.btn_calib, self.btn_oper, self.btn_off):
            btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            btn.setFixedHeight(40)
            sb_layout.addWidget(btn)
        sb_layout.addStretch()
        
        # Conexiones de botones BLE
        self.btn_connect.clicked.connect(self.connect_ble)
        self.btn_disconnect.clicked.connect(self.disconnect_ble)
        
        # Stack de páginas
        self.stack = QtWidgets.QStackedWidget()
        self.stack.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border-radius: 12px;
                padding: 15px;
            }
        """)
        self._build_pages()
        self.btn_calib.clicked.connect(lambda: self.stack.setCurrentWidget(self.calib_page))
        self.btn_oper.clicked.connect(lambda: self.stack.setCurrentWidget(self.oper_page))
        self.btn_off.clicked.connect(lambda: self.stack.setCurrentWidget(self.offline_page))
        # Layout principal
        main = QtWidgets.QWidget()
        ml = QtWidgets.QHBoxLayout(main)
        ml.setContentsMargins(12,12,12,12)
        ml.setSpacing(8)
        ml.addWidget(sidebar)
        ml.addWidget(self.stack,1)
        self.setCentralWidget(main)
        
        # Mostrar página de bienvenida inicialmente
        self.stack.setCurrentWidget(self.welcome_page)
        
        # Worker BLE persistente
        self.ble_worker = None
        self.calib_dialog = None
    
    def _make_title(self,text):
        lbl = QtWidgets.QLabel(text, objectName='title')
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        return lbl
    
    def _build_pages(self):
        # Página de bienvenida
        self.welcome_page = WelcomePage()
        self.stack.addWidget(self.welcome_page)
        
        # Calibración BLE
        self.calib_page = QtWidgets.QWidget()
        v1 = QtWidgets.QVBoxLayout(self.calib_page)
        v1.addWidget(self._make_title('Calibración BLE'))
        
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.samples_spin = QtWidgets.QSpinBox()
        self.samples_spin.setRange(1,1000)
        self.samples_spin.setValue(10)
        self.sensor_combo = QtWidgets.QComboBox()
        self.sensor_combo.addItems(['0','1','2','3'])
        form.addRow('Muestras/peso:', self.samples_spin)
        form.addRow('Sensor:', self.sensor_combo)
        v1.addLayout(form)
        
        hb = QtWidgets.QHBoxLayout()
        self.btn_new = QtWidgets.QPushButton('Nueva Calibración')
        self.btn_list = QtWidgets.QPushButton('Listar')
        self.btn_delete = QtWidgets.QPushButton('Borrar')
        self.btn_report = QtWidgets.QPushButton('Reportar')
        
        # Estilo mejorado para botones de calibración
        for b in (self.btn_new, self.btn_list, self.btn_delete, self.btn_report):
            b.setFixedHeight(40)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['primary']};
                    color: {PALETTE['text']};
                    border: none;
                    border-radius: 8px;
                    padding: 8px 12px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 80px;
                }}
                QPushButton:hover {{
                    background: {PALETTE['accent']};
                }}
                QPushButton:pressed {{
                    background: #5A4FB0;
                }}
            """)
            hb.addWidget(b)
        v1.addLayout(hb)
        
        self.list_calib = QtWidgets.QListWidget()
        self.list_calib.setFixedHeight(120)
        v1.addWidget(self.list_calib)
        
        # Operación BLE
        self.oper_page = QtWidgets.QWidget()
        v2 = QtWidgets.QVBoxLayout(self.oper_page)
        v2.addWidget(self._make_title('Operación BLE'))
        
        h2 = QtWidgets.QHBoxLayout()
        self.btn_oper_start = QtWidgets.QPushButton('Iniciar')
        self.btn_oper_stop = QtWidgets.QPushButton('Detener')
        self.btn_oper_stop.setEnabled(False)
        
        # Estilo mejorado para botones de operación
        for b in (self.btn_oper_start, self.btn_oper_stop):
            b.setFixedHeight(45)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['primary']};
                    color: {PALETTE['text']};
                    border: none;
                    border-radius: 10px;
                    padding: 10px 20px;
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 120px;
                }}
                QPushButton:hover {{
                    background: {PALETTE['accent']};
                }}
                QPushButton:pressed {{
                    background: #5A4FB0;
                }}
                QPushButton:disabled {{
                    background: #CCCCCC;
                    color: #666666;
                }}
            """)
            h2.addWidget(b)
        v2.addLayout(h2)
        
        self.log_oper = QtWidgets.QTextEdit()
        self.log_oper.setReadOnly(True)
        v2.addWidget(self.log_oper, 1)
        
        self.btn_oper_start.clicked.connect(self.start_oper)
        self.btn_oper_stop.clicked.connect(self.stop_oper)
        
        self.stack.addWidget(self.oper_page)
        
        # Offline
        self.offline_page = QtWidgets.QWidget()
        v3 = QtWidgets.QVBoxLayout(self.offline_page)
        v3.addWidget(self._make_title('Gestión Offline'))
        
        h3 = QtWidgets.QHBoxLayout()
        self.off_sensor = QtWidgets.QComboBox()
        self.off_sensor.addItems(['0','1','2','3'])
        h3.addWidget(QtWidgets.QLabel('Sensor:'))
        h3.addWidget(self.off_sensor)
        
        self.off_list = QtWidgets.QPushButton('Listar')
        self.off_delete = QtWidgets.QPushButton('Borrar')
        self.off_report = QtWidgets.QPushButton('Reportar')
        
        # Estilo mejorado para botones offline
        for b in (self.off_list, self.off_delete, self.off_report):
            b.setFixedHeight(40)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['primary']};
                    color: {PALETTE['text']};
                    border: none;
                    border-radius: 8px;
                    padding: 8px 12px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 80px;
                }}
                QPushButton:hover {{
                    background: {PALETTE['accent']};
                }}
                QPushButton:pressed {{
                    background: #5A4FB0;
                }}
            """)
            h3.addWidget(b)

        v3.addLayout(h3)

        self.list_off = QtWidgets.QListWidget()
        v3.addWidget(self.list_off, 1)
        self.stack.addWidget(self.offline_page)
        
        # Conexiones
        self.btn_new.clicked.connect(self.run_new_calib)
        self.btn_list.clicked.connect(self.run_list_calib)
        self.btn_delete.clicked.connect(self.run_delete_calib)
        self.btn_report.clicked.connect(self.run_report_calib)
        
        self.off_list.clicked.connect(self.list_offline)
        self.off_delete.clicked.connect(self.delete_offline)
        self.off_report.clicked.connect(self.report_offline)
        
        self.stack.addWidget(self.calib_page)
    
    # Handlers BLE
    def connect_ble(self):
        # Verificar si ya hay un worker activo
        if self.ble_worker and self.ble_worker.isRunning():
            return
        
        self.ble_worker = BLEWorker(Protocol.connect_ble_wrapper)
        self.ble_worker.error.connect(self.show_error)
        self.ble_worker.finished.connect(self.on_ble_connected)
        self.ble_worker.finished.connect(self.cleanup_worker)
        self.ble_worker.error.connect(self.cleanup_worker)
        self.ble_worker.start()
    
    def on_ble_connected(self):
        self.ble_status_indicator.set_status(True)
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.btn_calib.setEnabled(True)
        self.btn_oper.setEnabled(True)
    
    def disconnect_ble(self):
        # Verificar si ya hay un worker activo
        if self.ble_worker and self.ble_worker.isRunning():
            return
        
        self.ble_worker = BLEWorker(Protocol.disconnect_ble_wrapper)
        self.ble_worker.error.connect(self.show_error)
        self.ble_worker.finished.connect(self.on_ble_disconnected)
        self.ble_worker.finished.connect(self.cleanup_worker)
        self.ble_worker.error.connect(self.cleanup_worker)
        self.ble_worker.start()
    
    def on_ble_disconnected(self):
        self.ble_status_indicator.set_status(False)
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_calib.setEnabled(False)
        self.btn_oper.setEnabled(False)
    
    def cleanup_worker(self):
        """Limpia el worker después de finalizar"""
        if self.ble_worker:
            self.ble_worker.stop()
            self.ble_worker = None
    
    # Handlers Calibración BLE
    def run_new_calib(self):
        n = self.samples_spin.value()
        s = self.sensor_combo.currentText()
        
        # Crear worker para calibración
        worker = BLEWorker(Protocol.calibracion_ble_wrapper, n, s)
        
        # Crear diálogo de progreso
        self.calib_dialog = CalibrationDialog(self)
        self.calib_dialog.set_worker(worker)
        
        # Conectar señales
        worker.finished.connect(self.handle_calib_success)
        worker.error.connect(self.show_error)
        worker.finished.connect(self.calib_dialog.accept)
        
        # Iniciar worker y mostrar diálogo
        worker.start()
        self.calib_dialog.exec_()
    
    def handle_calib_success(self, path):
        if path:
            self.show_info(f'Calibración guardada en:\n{path}')
            self.run_list_calib()
    
    def run_list_calib(self):
        s = self.sensor_combo.currentText()
        files = Protocol.list_calibrations(s)
        self.list_calib.clear()
        self.list_calib.addItems(files)
    
    def run_delete_calib(self):
        s = self.sensor_combo.currentText()
        sel = self.list_calib.currentItem()
        if not sel:
            return
        
        dfile = os.path.join(Protocol.DIR_DATA, f'sensor{s}', sel.text())
        try:
            os.remove(dfile)
        except Exception as e:
            return self.show_error(f'Error borrando CSV: {e}')
        
        # Borrar archivos procesados relacionados
        pf = os.path.join(Protocol.dir_processed, f'sensor{s}')
        bs = os.path.splitext(sel.text())[0]
        if os.path.isdir(pf):
            for f in os.listdir(pf):
                if f.startswith(bs):
                    try:
                        os.remove(os.path.join(pf, f))
                    except:
                        pass
        
        self.run_list_calib()
        self.show_info('Calibración eliminada')
    
    def run_report_calib(self):
        s = self.sensor_combo.currentText()
        sel = self.list_calib.currentItem()
        if not sel:
            return
        
        name = sel.text()
        csvp = os.path.join(Protocol.DIR_DATA, f'sensor{s}', name)
        out = os.path.join(Protocol.dir_processed, f'sensor{s}')
        os.makedirs(out, exist_ok=True)
        
        try:
            props, img = process_file(csvp, out)
        except Exception as e:
            return self.show_error(f'Error procesando: {e}')
        
        self.show_report_dialog(props, img, name)
    
    # Handlers Operación BLE
    def start_oper(self):
        self.log_oper.append('Iniciando operación BLE...')
        self.btn_oper_start.setEnabled(False)
        self.btn_oper_stop.setEnabled(True)
        
        # Crear worker para operación
        worker = BLEWorker(Protocol.operacion_ble_wrapper)
        worker.operation_log.connect(self.log_oper.append)
        worker.finished.connect(self.on_oper_finished)
        worker.start()
        self.oper_worker = worker
    
    def on_oper_finished(self):
        self.log_oper.append('Operación finalizada')
        self.btn_oper_start.setEnabled(True)
        self.btn_oper_stop.setEnabled(False)
        self.oper_worker = None
    
    def stop_oper(self):
        if self.oper_worker:
            self.oper_worker.cancel_event.set()
            self.log_oper.append('Deteniendo operación...')
    
    # Handlers Offline
    def list_offline(self):
        s = self.off_sensor.currentText()
        files = Protocol.list_calibrations(s)
        self.list_off.clear()
        self.list_off.addItems(files)
    
    def delete_offline(self):
        s = self.off_sensor.currentText()
        sel = self.list_off.currentItem()
        if not sel:
            return
        
        try:
            calib_path = os.path.join(Protocol.DIR_DATA, f'sensor{s}', sel.text())
            os.remove(calib_path)
            
            # Borrar archivos procesados
            report_folder = os.path.join(Protocol.dir_processed, f'sensor{s}')
            basename = os.path.splitext(sel.text())[0]
            for fname in os.listdir(report_folder):
                if fname.startswith(basename):
                    os.remove(os.path.join(report_folder, fname))
            
            self.list_offline()
            self.show_info('Calibración eliminada')
        except Exception as e:
            self.show_error(f'Error eliminando: {e}')
    
    def report_offline(self):
        s = self.off_sensor.currentText()
        sel = self.list_off.currentItem()
        if not sel:
            return
        
        name = sel.text()
        csvp = os.path.join(Protocol.DIR_DATA, f'sensor{s}', name)
        out = os.path.join(Protocol.dir_processed, f'sensor{s}')
        os.makedirs(out, exist_ok=True)
        
        try:
            props, img = process_file(csvp, out)
        except Exception as e:
            return self.show_error(f'Error procesando: {e}')
        
        self.show_report_dialog(props, img, name)
    
    # Diálogo de reporte compartido
    def show_report_dialog(self, props, img, name):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f'Reporte Calibración: {name}')
        dlg.resize(800, 700)
        layout = QtWidgets.QVBoxLayout(dlg)
        
        # Propiedades en tabla
        table = QtWidgets.QTableWidget()
        table.setRowCount(props.shape[0])
        table.setColumnCount(props.shape[1])
        table.setHorizontalHeaderLabels(props.columns)
        
        for i in range(props.shape[0]):
            for j in range(props.shape[1]):
                item = QtWidgets.QTableWidgetItem(str(props.iat[i, j]))
                item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
                table.setItem(i, j, item)
        
        table.resizeColumnsToContents()
        table.setMaximumHeight(180)
        layout.addWidget(table)
        
        # Ecuación de regresión y sensibilidad
        eq_label = QtWidgets.QLabel(f"Ecuación de la curva característica:\n{props.at[0, 'Ecuacion_regresion']}")
        sens_label = QtWidgets.QLabel(f"Ecuación de sensibilidad:\n{props.at[0, 'Sensibilidad_eq']}")
        for lbl in (eq_label, sens_label):
            lbl.setStyleSheet("font-size: 14px; font-weight: bold; background: #f8f9fa; padding: 10px;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
        
        # Gráfica
        chart = PlotCanvas(dlg, width=7, height=5)
        chart.show_image(img)
        layout.addWidget(chart)
        
        # Botones
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        dlg.exec_()
    
    # Utilidades
    def show_error(self, msg):
        QtWidgets.QMessageBox.critical(self, 'Error', msg)
    
    def show_info(self, msg):
        QtWidgets.QMessageBox.information(self, 'Información', msg)
    
    def update_ble_status(self, message, color=None):
        # Actualiza el estado en la barra de estado si es necesario
        pass

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())