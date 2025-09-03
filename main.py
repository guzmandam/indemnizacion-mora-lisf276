import httpx
import typer
import pandas as pd
import datetime
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal, getcontext
import calendar

BANXICO_TOKEN_CONSULTA = "eddfb44c7004878e71665ef06f6914f0db7a98ac92de85bda173a8171375ffb7"
BANXICO_API_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{idSerie}/datos/{fechaInicio}/{fechaFin}"

BANXICO_SERIES = {
    "CCP_UDIS": "SF3368",
    "UDIS": "SP68257"
}

app = typer.Typer()

def retrieve_banxico_series_data(serie: str, fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
    url = BANXICO_API_URL.format(idSerie=serie, fechaInicio=fecha_inicio, fechaFin=fecha_fin)
    try:
        response = httpx.get(url, headers={"Bmx-Token": BANXICO_TOKEN_CONSULTA})
        response.raise_for_status()
        series = response.json()["bmx"]["series"]
        
        df = pd.DataFrame(series[0]["datos"])
        df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y")
        df["dato"] = df["dato"].astype(float)
        
        df.set_index("fecha", inplace=True)
        
        return df
    except httpx.HTTPStatusError as e:
        print(e)
        return pd.DataFrame()

def retrieve_udis_daily_value(date: str) -> float:
    df = retrieve_banxico_series_data(BANXICO_SERIES["UDIS"], date, date)
    if df.empty:
        raise ValueError("No data available for the given date")
    return df["dato"].iloc[-1]

def retrieve_ccp_udis_monthly(fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
    """Obtiene los valores mensuales de CCP-UDIS desde Banxico"""
    df = retrieve_banxico_series_data(BANXICO_SERIES["CCP_UDIS"], fecha_inicio, fecha_fin)
    if df.empty:
        raise ValueError("No hay datos disponibles para el período especificado")
    return df

def get_days_in_month(year: int, month: int) -> int:
    """Obtiene el número de días en un mes específico"""
    return calendar.monthrange(year, month)[1]

def count_days_in_period(start_date: datetime.date, end_date: datetime.date, inclusive: bool = True) -> int:
    """Cuenta los días entre dos fechas, con opción de inclusividad en ambos extremos"""
    delta = end_date - start_date
    days = delta.days
    if inclusive:
        days += 1  # Incluye ambos extremos
    return days

def partition_by_month(start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
    """Particiona un intervalo de fechas por mes calendario"""
    if start_date > end_date:
        raise ValueError("La fecha de inicio debe ser anterior o igual a la fecha final")
    
    result = []
    current_date = start_date
    
    while current_date <= end_date:
        year = current_date.year
        month = current_date.month
        
        # Último día del mes actual
        last_day_of_month = datetime.date(year, month, get_days_in_month(year, month))
        
        # Período efectivo para este mes
        period_end = min(last_day_of_month, end_date)
        
        month_data = {
            "month": f"{year}-{month:02d}",
            "period_start": current_date,
            "period_end": period_end,
            "days": count_days_in_period(current_date, period_end)
        }
        
        result.append(month_data)
        
        # Avanzar al primer día del siguiente mes
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
        
        current_date = next_month
    
    return result

def calculate_mora_interest(
    p0_mxn: float,
    t0: str,
    tf: str,
    udi_t0: Optional[float] = None,
    udi_tf: Optional[float] = None,
    ccp_table: Optional[List[Dict[str, Any]]] = None,
    inclusivity: bool = True
) -> Dict[str, Any]:
    """Calcula la indemnización por mora conforme al Art. 276 de la LISF (México)
    
    Args:
        p0_mxn: Principal en pesos (MXN)
        t0: Fecha de inicio de mora (formato ISO YYYY-MM-DD)
        tf: Fecha de cálculo/pago (formato ISO YYYY-MM-DD)
        udi_t0: Valor UDI en t0 (opcional, se obtiene de Banxico si no se proporciona)
        udi_tf: Valor UDI en tf (opcional, se obtiene de Banxico si no se proporciona)
        ccp_table: Tabla mensual de CCP-UDIS (opcional, se obtiene de Banxico si no se proporciona)
        inclusivity: Política de conteo de días (por defecto, inclusivo en ambos extremos)
        
    Returns:
        Diccionario con los resultados del cálculo
    """
    # Configurar precisión para cálculos decimales
    getcontext().prec = 28
    
    # Convertir fechas a objetos datetime.date
    start_date = datetime.date.fromisoformat(t0)
    end_date = datetime.date.fromisoformat(tf)
    
    # Obtener valores UDI si no se proporcionan
    if udi_t0 is None:
        udi_t0 = retrieve_udis_daily_value(t0)
    if udi_tf is None:
        udi_tf = retrieve_udis_daily_value(tf)
    
    # Obtener tabla CCP-UDIS si no se proporciona
    if ccp_table is None:
        # Formato para consulta Banxico: primer día del mes de t0 hasta último día del mes de tf
        first_day_month_t0 = datetime.date(start_date.year, start_date.month, 1).isoformat()
        last_day_month_tf = datetime.date(end_date.year, end_date.month, 
                                        get_days_in_month(end_date.year, end_date.month)).isoformat()
        
        ccp_df = retrieve_ccp_udis_monthly(first_day_month_t0, last_day_month_tf)
        
        # Convertir DataFrame a formato requerido
        ccp_table = []
        for date, row in ccp_df.iterrows():
            # Asegurar que date sea un objeto datetime
            if isinstance(date, pd.Timestamp):
                month_str = f"{date.year}-{date.month:02d}-01"
            else:
                # Si date no es un Timestamp, convertirlo
                date_obj = pd.Timestamp(date)
                month_str = f"{date_obj.year}-{date_obj.month:02d}-01"
            ccp_table.append({"month": month_str, "ccp_pct": row["dato"]})
    
    # Crear diccionario para acceso rápido a tasas CCP por mes
    ccp_dict = {item["month"][:7]: item["ccp_pct"] for item in ccp_table}
    
    # Particionar el intervalo por mes calendario
    monthly_partitions = partition_by_month(start_date, end_date)
    
    # Calcular factores mensuales y acumulados
    monthly_breakdown = []
    phi_cum = Decimal('1.0')
    total_days = 0
    
    # Denominación inicial en UDI
    U0 = Decimal(str(p0_mxn)) / Decimal(str(udi_t0))  # P0_mxn / UDI_t0
    U_prev = U0  # Saldo en UDI al inicio del período
    
    for month_data in monthly_partitions:
        month_key = month_data["month"]
        d_j = month_data["days"]  # Días en mora para este mes
        total_days += d_j
        
        # Obtener CCP para este mes (o usar el del mes anterior si no está disponible)
        ccp_pct = None
        current_month = datetime.date.fromisoformat(f"{month_key}-01")
        
        # Buscar CCP para este mes o meses anteriores si no está disponible
        while ccp_pct is None:
            if month_key in ccp_dict:
                ccp_pct = ccp_dict[month_key]
                break
            
            # Retroceder un mes
            if current_month.month == 1:
                current_month = datetime.date(current_month.year - 1, 12, 1)
            else:
                current_month = datetime.date(current_month.year, current_month.month - 1, 1)
            
            month_key_prev = f"{current_month.year}-{current_month.month:02d}"
            
            if month_key_prev in ccp_dict:
                ccp_pct = ccp_dict[month_key_prev]
                break
            
            # Si no se encuentra ningún valor después de varios intentos, lanzar error
            if (current_month.year * 12 + current_month.month) < (start_date.year * 12 + start_date.month - 12):
                raise ValueError(f"No se encontró valor CCP-UDIS para el mes {month_key} ni meses anteriores")
        
        # Calcular factores
        r_a_j = Decimal(str(1.25)) * Decimal(str(ccp_pct)) / Decimal('100')  # 1.25 * CCP_j / 100
        r_d_j = r_a_j / Decimal('365')  # r_a_j / 365
        F_j = Decimal('1') + r_d_j * Decimal(str(d_j))  # 1 + r_d_j * d_j
        
        # Calcular interés mensual en UDI
        interest_udi_month = U0 * (F_j - Decimal('1'))  # Interés generado este mes en UDI
        interest_mxn_month = float(interest_udi_month * Decimal(str(udi_tf)))  # Convertir a MXN usando UDI de tf
        
        # Actualizar saldo en UDI
        U_current = U0 * F_j
        
        # Actualizar factor acumulado
        phi_cum *= F_j
        
        # Agregar al desglose mensual
        monthly_breakdown.append({
            "month": month_data["month"],
            "period_start": month_data["period_start"].isoformat(),
            "period_end": month_data["period_end"].isoformat(),
            "d_j": d_j,
            "ccp_pct": float(ccp_pct),
            "r_a_j": float(r_a_j),
            "r_d_j": float(r_d_j),
            "F_j": float(F_j),
            "Phi_cum": float(phi_cum),
            "interest_udi_month": float(interest_udi_month),
            "interest_mxn_month": round(interest_mxn_month, 2)
        })
        
        # Actualizar saldo para el siguiente mes
        U_prev = U_current

    monthly_breakdown_df = pd.DataFrame(monthly_breakdown)
    sum_monthly_int_udi = monthly_breakdown_df["interest_udi_month"].sum()
    sum_monthly_int_udi_mxn = monthly_breakdown_df["interest_mxn_month"].sum()
    
    # Denominación en UDI y actualización
    Phi = phi_cum  # Producto acumulado de factores mensuales
    Ufin = U0 * Phi  # U0 * Phi
    
    # Conversión a MXN
    P_upd_mxn = float(U0 * Decimal(str(udi_tf)))  # U0 * UDI_tf
    interest_mxn = float((Ufin - U0) * Decimal(str(udi_tf)))  # (Ufin - U0) * UDI_tf
    total_mxn = float(Ufin * Decimal(str(udi_tf)))  # Ufin * UDI_tf
    
    # Redondear a 2 decimales para valores finales en MXN
    P_upd_mxn = round(P_upd_mxn, 2)
    interest_mxn = round(interest_mxn, 2)
    total_mxn = sum_monthly_int_udi_mxn + P_upd_mxn#round(total_mxn, 2)
    
    return {
        "n_periods": len(monthly_breakdown),
        "total_days": total_days,
        "Phi": float(Phi),
        "P_upd_mxn": P_upd_mxn,
        "interest_mxn": sum_monthly_int_udi_mxn,
        "total_mxn": total_mxn,
        "monthly_breakdown": monthly_breakdown,
        "U0": float(U0),
        "Ufin": float(Ufin),
        "udi_t0": udi_t0,
        "udi_tf": udi_tf
    }

@app.command()
def calcular(
    p0_mxn: float = typer.Option(..., help="Principal en pesos (MXN)"),
    t0: str = typer.Option(..., help="Fecha de inicio de mora (formato ISO YYYY-MM-DD)"),
    tf: str = typer.Option(..., help="Fecha de cálculo/pago (formato ISO YYYY-MM-DD)"),
    udi_t0: float = typer.Option(None, help="Valor UDI en t0 (opcional)"),
    udi_tf: float = typer.Option(None, help="Valor UDI en tf (opcional)"),
    inclusivity: bool = typer.Option(True, help="Política de conteo de días (por defecto, inclusivo en ambos extremos)")
):
    """Calcula la indemnización por mora conforme al Art. 276 de la LISF (México)"""
    try:
        # Validar fechas
        datetime.date.fromisoformat(t0)
        datetime.date.fromisoformat(tf)
        
        # Calcular indemnización
        result = calculate_mora_interest(
            p0_mxn=p0_mxn,
            t0=t0,
            tf=tf,
            udi_t0=udi_t0,
            udi_tf=udi_tf,
            inclusivity=inclusivity
        )
        
        # Mostrar resultados
        print(f"\nCálculo de indemnización por mora (Art. 276 LISF)")
        print(f"==================================================")
        print(f"Principal: ${p0_mxn:.2f} MXN")
        print(f"Período: {t0} a {tf}")
        print(f"UDI inicial: {result['udi_t0']}")
        print(f"UDI final: {result['udi_tf']}")
        print(f"\nResultados:")
        print(f"- Número de períodos: {result['n_periods']}")
        print(f"- Total de días en mora: {result['total_days']}")
        print(f"- Factor acumulado (Phi): {result['Phi']:.10f}")
        print(f"- Principal en UDI (U0): {result['U0']:.10f}")
        print(f"- Saldo final en UDI (Ufin): {result['Ufin']:.10f}")
        print(f"- Principal actualizado: ${result['P_upd_mxn']:.2f} MXN")
        print(f"- Interés moratorio: ${result['interest_mxn']:.2f} MXN")
        print(f"- Total a pagar: ${result['total_mxn']:.2f} MXN")
        
        print(f"\nDesglose mensual:")
        print(f"{'Mes':<10} {'Días':<6} {'CCP(%)':<8} {'r_a_j':<8} {'r_d_j':<12} {'F_j':<12} {'Phi_cum':<12} {'Int_UDI':<12} {'Int_MXN':<12}")
        for month in result['monthly_breakdown']:
            print(f"{month['month']:<10} {month['d_j']:<6} {month['ccp_pct']:<8.4f} {month['r_a_j']:<8.6f} {month['r_d_j']:<12.10f} {month['F_j']:<12.10f} {month['Phi_cum']:<12.10f} {month['interest_udi_month']:<12.10f} ${month['interest_mxn_month']:<11.2f}")
            
    except Exception as e:
        print(f"Error: {e}")

@app.command()
def consultar_udis(fecha: str = typer.Option(..., help="Fecha en formato ISO YYYY-MM-DD")):
    """Consulta el valor de las UDIS para una fecha específica"""
    try:
        valor = retrieve_udis_daily_value(fecha)
        print(f"Valor UDI para {fecha}: {valor}")
    except Exception as e:
        print(f"Error: {e}")

@app.command()
def consultar_ccp_udis(fecha_inicio: str = typer.Option(..., help="Fecha inicio en formato ISO YYYY-MM-DD"),
                      fecha_fin: str = typer.Option(..., help="Fecha fin en formato ISO YYYY-MM-DD")):
    """Consulta los valores mensuales de CCP-UDIS para un período"""
    try:
        df = retrieve_ccp_udis_monthly(fecha_inicio, fecha_fin)
        print(f"Valores CCP-UDIS para el período {fecha_inicio} a {fecha_fin}:")
        for fecha, row in df.iterrows():
            # Asegurar que fecha sea un objeto datetime
            if isinstance(fecha, pd.Timestamp):
                fecha_str = fecha.strftime('%Y-%m')
            else:
                # Si fecha no es un Timestamp, convertirlo
                fecha_obj = pd.Timestamp(fecha)
                fecha_str = fecha_obj.strftime('%Y-%m')
            print(f"{fecha_str}: {row['dato']}%")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    app()
