import numpy as np
import matplotlib.pyplot as plt

# R_feedback fijo
R_feedback = 100e3  # 100kΩ

# Fuerza en Newtons (0.1 N a 40 N)
fuerza = np.linspace(0.1, 40, 200)

# Aproximación empírica de la resistencia del FSR (no lineal)
R_FSR = 1e6 / fuerza**0.8  # Ohmios

# Ganancia del amplificador no inversor
ganancia = 1 + (R_feedback / R_FSR)

# Valor de referencia de entrada (VREF)
VREF = 1  # Voltios (puede ser 0.2 a 0.5 V dependiendo del divisor resistivo)

# Voltaje de salida
Vout = ganancia * VREF

# Limitar la salida a 3.3 V (máximo del sistema)
Vout = np.clip(Vout, 0, 3.3)

# Graficar
plt.figure(figsize=(8,5))
plt.plot(fuerza, Vout, label='Voltaje de salida (Vout)', color='red', linewidth=2)
plt.plot(ganancia, Vout, label='Ganancia', color='blue', linewidth=1)
plt.xlabel('Fuerza aplicada (N)')
plt.ylabel('Voltaje de salida [V]')
plt.title('Vout vs Fuerza aplicada - FSR402 + Amplificador No Inversor')
plt.grid(True)
plt.legend()
plt.ylim(0, 3.5)
plt.tight_layout()
plt.show()
