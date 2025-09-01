# Calculadora de Indemnización por Mora (Art. 276 LISF)

Este servicio calcula la indemnización por mora conforme al Artículo 276 de la Ley de Instituciones de Seguros y Fianzas (LISF) de México para obligaciones en MXN denominadas en UDI, con devengo diario (÷365) y capitalización mensual, usando CCP-UDIS mensual (×1.25) y UDIS diarias para la denominación y conversión.

## Características

- Cálculo de indemnización por mora según Art. 276 LISF
- Consulta automática de valores UDI y CCP-UDIS desde Banxico
- Desglose mensual detallado de factores y acumulados
- Precisión en cálculos intermedios y redondeo a 2 decimales en resultados finales

## Requisitos

- Python 3.7+
- Dependencias: httpx, typer, pandas

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

### Cálculo de indemnización por mora

```bash
python3 main.py calcular --p0-mxn MONTO --t0 FECHA_INICIO --tf FECHA_FIN [--udi-t0 VALOR_UDI_INICIAL] [--udi-tf VALOR_UDI_FINAL] [--inclusivity BOOL]
```

Donde:
- `--p0-mxn`: Principal en pesos mexicanos (MXN)
- `--t0`: Fecha de inicio de mora en formato ISO YYYY-MM-DD
- `--tf`: Fecha de cálculo/pago en formato ISO YYYY-MM-DD
- `--udi-t0`: (Opcional) Valor UDI en t0. Si no se proporciona, se consulta automáticamente
- `--udi-tf`: (Opcional) Valor UDI en tf. Si no se proporciona, se consulta automáticamente
- `--inclusivity`: (Opcional) Política de conteo de días (por defecto, True = inclusivo en ambos extremos)

### Consulta de valores UDI

```bash
python3 main.py consultar-udis --fecha FECHA
```

Donde:
- `--fecha`: Fecha en formato ISO YYYY-MM-DD

### Consulta de valores CCP-UDIS

```bash
python3 main.py consultar-ccp-udis --fecha-inicio FECHA_INICIO --fecha-fin FECHA_FIN
```

Donde:
- `--fecha-inicio`: Fecha de inicio en formato ISO YYYY-MM-DD
- `--fecha-fin`: Fecha de fin en formato ISO YYYY-MM-DD

## Ejemplo

```bash
python3 main.py calcular --p0-mxn 10000 --t0 2023-01-01 --tf 2023-03-15
```

Resultado:

```
Cálculo de indemnización por mora (Art. 276 LISF)
==================================================
Principal: $10000.00 MXN
Período: 2023-01-01 a 2023-03-15
UDI inicial: [valor consultado]
UDI final: [valor consultado]

Resultados:
- Número de períodos: 3
- Total de días en mora: 74
- Factor acumulado (Phi): [valor calculado]
- Principal en UDI (U0): [valor calculado]
- Saldo final en UDI (Ufin): [valor calculado]
- Principal actualizado: $[valor] MXN
- Interés moratorio: $[valor] MXN
- Total a pagar: $[valor] MXN

Desglose mensual:
[tabla con desglose mensual]
```

## Lógica de negocio

### Definiciones

- Particionar [t0, tf] por mes calendario. Para cada mes j:
  - d_j = número de días en mora dentro de ese mes (respetando inclusividad y límites)
  - CCP_j = tasa anual publicada para ese mes (en %)
  - r_a_j = 1.25 × CCP_j/100
  - r_d_j = r_a_j/365 (devengo diario)
  - F_j = 1 + r_d_j × d_j (capitalización mensual)

### Denominación en UDI y actualización

- Denominar el principal en UDI a t0: U0 = P0_mxn / UDI_t0
- Factor total: Φ = ∏(j=1 a n) F_j
- Saldo en UDI al final: Ufin = U0 × Φ
- Conversión a MXN en tf:
  - P_upd_mxn = U0 × UDI_tf
  - interest_mxn = (Ufin - U0) × UDI_tf
  - total_mxn = Ufin × UDI_tf

### Reglas y consideraciones

- Base de días: ACT/365 (no 360)
- Inclusividad: por defecto, conteo inclusivo en ambos extremos
- Meses parciales: el primer y último mes suelen ser parciales; contar solo días efectivos
- Orden temporal: calcular Phi en orden cronológico por mes
- Precisión: usar decimal con alta precisión en cálculos intermedios; redondear al final a 2 decimales MXN

## Notas

- El cálculo se basa en la Ley de Instituciones de Seguros y Fianzas (LISF) de México
- Si no hay publicación del CCP-UDIS para un mes específico, se usa la del mes inmediato anterior
- Los valores UDI y CCP-UDIS se obtienen automáticamente de la API de Banxico