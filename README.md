# FSR-Study-GUI 📊🖥️

Este repositorio contiene una **interfaz gráfica de usuario (GUI)**, scripts, datos y diseños asociados para el estudio de **Force Sensitive Resistors (FSR)**.  
El proyecto facilita la adquisición, visualización y análisis de datos provenientes de sensores FSR con fines de investigación, calibración y prototipado.

---

## 📂 Estructura del repositorio

- `Design/` → Archivos CAD y de fabricación (`.ipt`, `.stl`, `.gcode`, etc.).  
- `GUI/` → Código fuente de la interfaz gráfica (por ejemplo `GUI/main.py`).  
- `Data/` → Conjuntos de datos experimentales y ejemplos de calibración.  
- `Scripts/` → Scripts para procesamiento y análisis (por ejemplo `Scripts/analizar_datos.py`).  
- `Results/` → Gráficas y reportes generados.  
- `Docs/` → Documentación adicional, diagramas y capturas.  
- `README.md` → Este archivo.

---

## ⚙️ Tecnologías y dependencias

- **Python 3.8+** (recomendado 3.9+).  
- Bibliotecas típicas: `numpy`, `pandas`, `matplotlib`, `pyqt5` o `tkinter` según la implementación.  
- **Arduino (C/C++)** — adquisición de datos desde sensores FSR (si aplica).  
- Se recomienda usar **Git LFS** para archivos pesados (`.stl`, `.gcode`, `.ipt`) si su tamaño excede ~50 MB.

---

## 🚀 Instalación rápida

1. Clona el repositorio:
   ```bash
   git clone https://github.com/Protsen-UN/FSR-Study-GUI.git
   cd FSR-Study-GUI
   ```

2. (Opcional) crea y activa un entorno virtual:
   ```bash
   # Crear entorno
   python -m venv venv

   # Windows (PowerShell)
   .\venv\Scripts\Activate.ps1

   # Windows (cmd)
   .\venv\Scripts\activate.bat

   # macOS / Linux
   source venv/bin/activate
   ```

3. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Ejecuta la GUI (ejemplo):
   ```bash
   python GUI/main.py
   ```
   o si tu GUI está en la raíz:
   ```bash
   python main.py
   ```

5. Ejecuta scripts de análisis (ejemplo):
   ```bash
   python Scripts/analizar_datos.py
   ```

---

## 🧪 Uso y recomendaciones experimentales

- Verifica la calibración de cada sensor antes de cada experimento.  
- Comprueba el rango y la linealidad del FSR en el rango que te interesa.  
- Para modelos 3D y `.gcode` revisa escala y prueba con piezas de calibración antes de imprimir.  
- Si vas a mantener archivos grandes en el repositorio, usa **Git LFS** (ver sección abajo).

---

## 📈 Objetivos del proyecto

- Evaluar el comportamiento de sensores FSR bajo condiciones controladas.  
- Obtener curvas fuerza–resistencia y evaluar sensibilidad y repetibilidad.  
- Proveer una GUI para adquisición, visualización en tiempo real y análisis posterior.  
- Compartir scripts y diseños para reproducibilidad y docencia.

---

## 📝 Git LFS (opcional, recomendado para archivos grandes)

Si tienes archivos grandes (`.stl`, `.gcode`, `.ipt`) y quieres que el repositorio sea ligero y clonable:

```bash
# instala Git LFS (solo una vez por máquina)
git lfs install

# comienza a trackear extensiones grandes
git lfs track "*.stl"
git lfs track "*.gcode"
git lfs track "*.ipt"

# agrega el .gitattributes y los archivos grandes como de costumbre
git add .gitattributes
git add Design/*.stl Design/*.gcode Design/*.ipt
git commit -m "Track large design files with Git LFS"
git push origin main
```

---

## 🤝 Cómo contribuir

1. Haz fork del repositorio.  
2. Crea una rama nueva:
   ```bash
   git checkout -b feature/nombre-de-la-funcion
   ```
3. Realiza tus cambios, haz commits claros y descriptivos.  
4. Envía un Pull Request describiendo los cambios y cómo probarlos.

---

## 👤 Autor / Contacto

**Samuel David Sanchez Cardenas**  
📧 samsanchezcar@gmail.com

---

## 🙏 Agradecimientos

- Grupo de investigación **Protsen - Universidad Nacional de Colombia**.  
- Colaboradores, estudiantes y profesores que apoyaron la experimentación, pruebas y documentación.  
- Comunidades y librerías de código abierto que hicieron posible este proyecto.

---

## 📄 Licencia

Este proyecto está bajo la **MIT License**. Consulta el archivo `LICENSE` para el texto completo.

---

---

# FSR-Study-GUI 📊🖥️ (English version)

This repository contains a **Graphical User Interface (GUI)**, scripts, datasets and design files to study **Force Sensing Resistors (FSR)**.  
The project facilitates data acquisition, visualization and analysis from FSR sensors for research, calibration and prototyping purposes.

---

## 📂 Repository structure

- `Design/` → CAD and fabrication files (`.ipt`, `.stl`, `.gcode`, etc.).  
- `GUI/` → GUI source code (e.g. `GUI/main.py`).  
- `Data/` → Experimental datasets and calibration examples.  
- `Scripts/` → Processing and analysis scripts (e.g. `Scripts/analyze_data.py`).  
- `Results/` → Generated plots and reports.  
- `Docs/` → Additional documentation, diagrams and screenshots.  
- `README.md` → This document.

---

## ⚙️ Technologies & dependencies

- **Python 3.8+** (3.9+ recommended).  
- Common libraries: `numpy`, `pandas`, `matplotlib`, `pyqt5` or `tkinter` depending on implementation.  
- **Arduino (C/C++)** for sensor acquisition (if applicable).  
- Consider **Git LFS** for large binary files (`.stl`, `.gcode`, `.ipt`) to keep repository lightweight.

---

## 🚀 Quick start

1. Clone:
   ```bash
   git clone https://github.com/Protsen-UN/FSR-Study-GUI.git
   cd FSR-Study-GUI
   ```

2. (Optional) create virtual env and activate it (see Spanish section).

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run GUI:
   ```bash
   python GUI/main.py
   ```

5. Run analysis:
   ```bash
   python Scripts/analyze_data.py
   ```

---

## 📈 Project goals

- Analyze FSR response under controlled conditions.  
- Obtain force–resistance curves and evaluate sensor performance.  
- Provide a user-friendly GUI for acquisition and visualization.  
- Share designs and code for reproducibility and teaching.

---

## 🤝 Contributing

Fork → Branch → Commit → Pull Request. Provide tests or example data where possible.

---

## 👤 Author / Contact

**Samuel David Sanchez Cardenas**  
📧 samsanchezcar@gmail.com

---

## 🙏 Acknowledgements

- **Protsen Research Group - Universidad Nacional de Colombia**.  
- Colleagues and contributors who assisted with prototyping, testing, and documentation.  
- Open-source libraries and communities.

---

## 📄 License

This project is released under the **MIT License**. See `LICENSE` for full text.
