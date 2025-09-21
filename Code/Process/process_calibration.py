import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
import sys

def process_file(csv_path, output_dir):
    # Leer datos
    df = pd.read_csv(csv_path)
    if not {'Peso_g', 'Lectura'}.issubset(df.columns):
        raise ValueError(f"El CSV {csv_path} debe contener las columnas 'Peso_g' y 'Lectura'.")
    
    # Convertir lecturas ADC a voltios (10 bits, 3.3V)
    df['Voltaje'] = (df['Lectura'] * (3.3 / 1023.0)).round(3)  # 3 decimales
    
    pesos = df['Peso_g'].astype(float)
    voltajes = df['Voltaje'].astype(float)
    min_p, max_p = pesos.min(), pesos.max()
    min_v, max_v = voltajes.min(), voltajes.max()

    # FSO: diferencia entre voltaje máximo y mínimo
    fso_volts = max_v - min_v 
    alcance_g = max_p - min_p  # magnitud del rango en gramos

    # Precisión: desviación de cada grupo respecto a su media, en %FSO
    precision_list = []
    for peso, grupo in df.groupby('Peso_g'):
        sigma = grupo['Voltaje'].std(ddof=1)
        prec_pct = (sigma / fso_volts * 100).round(2) if fso_volts else np.nan
        precision_list.append(prec_pct)
    precision = np.nanmax(precision_list)

    # Resolución: voltios por gramo
    resol = (fso_volts / alcance_g).round(6) if alcance_g else np.nan

    # Regresión cuadrática voltaje vs ln(peso)
    df['ln_peso'] = np.log(pesos)
    x = df['ln_peso'].values
    y = voltajes.values
    coeffs = np.polyfit(x, y, 2)
    a, b, c = coeffs

    # Predicción y R^2
    y_pred = np.polyval(coeffs, x)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = (1 - ss_res / ss_tot).round(4) if ss_tot else np.nan

    # Ecuación de sensibilidad: dV/dP = (2a ln(P) + b) / P
    sens_eq = f"S(P) = (2*{a:.6f}*ln(P) + {b:.6f}) / P"

    # Guardar propiedades globales en CSV
    base = os.path.splitext(os.path.basename(csv_path))[0]
    props = {
        'Rango_min_g': [round(min_p, 1)],
        'Rango_max_g': [round(max_p, 1)],
        'Rango_min_V': [min_v],
        'Rango_max_V': [max_v],
        'Alcance_g': [round(alcance_g, 1)],
        'FSO_volts': [round(fso_volts, 3)],
        'Precision_%FSO': [precision],
        'Resolucion_V_per_g': [resol],
        'R2_regresion': [r2],
        'Sensibilidad_eq': [sens_eq],
        'Ecuacion_regresion': [f"V = {a:.6f}(ln(P))² + {b:.6f}ln(P) + {c:.6f}"]
    }
    props_df = pd.DataFrame(props)
    props_file = os.path.join(output_dir, f"{base}_properties.csv")
    props_df.to_csv(props_file, index=False)
    print(f"Propiedades globales guardadas en {props_file}")

    # Guardar coeficientes y ecuación de sensibilidad
    coef_file = os.path.join(output_dir, f"{base}_coeffs.txt")
    with open(coef_file, 'w') as f:
        f.write("Coeficientes regresión cuadrática (V vs ln(P)):\n")
        f.write(f"  a = {a:.6f}\n")
        f.write(f"  b = {b:.6f}\n")
        f.write(f"  c = {c:.6f}\n")
        f.write(f"R^2 = {r2:.6f}\n")
        f.write(f"Ecuación: V = {a:.6f}(ln(P))² + {b:.6f}ln(P) + {c:.6f}\n")
        f.write("\nEcuación de sensibilidad:\n")
        f.write(f"  {sens_eq}\n")
    print(f"Guardados coeficientes, R^2 y sensibilidad en {coef_file}")

    # Graficar regresión (con ecuación)
    xs = np.linspace(x.min(), x.max(), 200)
    ys = a*xs**2 + b*xs + c
    plt.figure(figsize=(8, 6))
    
    # Scatter plot
    plt.scatter(x, y, label='Datos', alpha=0.6)
    
    # Regression line
    plt.plot(xs, ys, 'r-', label=f'Ajuste cuadrático (R²={r2:.4f})', linewidth=2)
    
    # Add equation annotation
    eq_text = f"$V = {a:.4f}(\\ln P)^2 + {b:.4f}\\ln P + {c:.4f}$"
    plt.annotate(eq_text, xy=(0.05, 0.95), xycoords='axes fraction',
                fontsize=12, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))
    
    plt.xlabel('ln(Peso_g)', fontsize=12)
    plt.ylabel('Voltaje (V)', fontsize=12)
    plt.title(f'Curva Característica: {base}', fontsize=14)
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    plot_file = os.path.join(output_dir, f"{base}_regression.png")
    plt.savefig(plot_file, dpi=150)
    plt.close()

    # ———> DEVUELVO lo que me interesa para el reporte on‑the‑fly:
    # 1) el DataFrame de propiedades
    # 2) la ruta de la imagen generada
    return props_df, plot_file


def process_all(data_dir, output_dir):
    if not os.path.isdir(data_dir):
        print(f"Error: No existe el directorio de datos: {data_dir}")
        sys.exit(1)
    os.makedirs(output_dir, exist_ok=True)
    for sensor_folder in sorted(os.listdir(data_dir)):
        sensor_path = os.path.join(data_dir, sensor_folder)
        if not os.path.isdir(sensor_path):
            continue
        sensor_out = os.path.join(output_dir, sensor_folder)
        os.makedirs(sensor_out, exist_ok=True)
        for fname in sorted(os.listdir(sensor_path)):
            if fname.lower().endswith('.csv'):
                process_file(os.path.join(sensor_path, fname), sensor_out)


def main():
    parser = argparse.ArgumentParser(
        description='Procesa datos de calibración: propiedades estáticas, regresión y sensibilidad.')
    parser.add_argument('--data-dir', '-d', default='Data', help='Directorio raíz de datos')
    parser.add_argument('--output-dir', '-o', default='Processed', help='Directorio de salida')
    args = parser.parse_args()
    process_all(args.data_dir, args.output_dir)


if __name__ == '__main__':
    main()