import streamlit as st
import httpx
import pandas as pd
import datetime
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal, getcontext
import calendar

# Import all the core functions from main.py
from main import (
    retrieve_banxico_series_data,
    retrieve_udis_daily_value,
    retrieve_ccp_udis_monthly,
    get_days_in_month,
    count_days_in_period,
    partition_by_month,
    calculate_mora_interest
)

# Streamlit page configuration
st.set_page_config(
    page_title="Calculadora de Indemnización por Mora - Art. 276 LISF",
    page_icon="💰",
    layout="wide"
)

# Main title
st.title("💰 Calculadora de Indemnización por Mora")
st.subheader("Conforme al Artículo 276 de la LISF (México)")

# Sidebar for navigation
st.sidebar.title("Navegación")
opcion = st.sidebar.selectbox(
    "Selecciona una opción:",
    ["Calcular Indemnización", "Consultar UDIS", "Consultar CCP-UDIS"]
)

if opcion == "Calcular Indemnización":
    st.header("📊 Cálculo de Indemnización por Mora")
    
    # Input form
    with st.form("calculo_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            p0_mxn = st.number_input(
                "Principal en pesos (MXN)",
                min_value=0.01,
                value=100000.0,
                step=1000.0,
                format="%.2f"
            )
            
            t0 = st.date_input(
                "Fecha de inicio de mora",
                value=datetime.date(2023, 1, 1)
            )
            
            tf = st.date_input(
                "Fecha de cálculo/pago",
                value=datetime.date.today()
            )
        
        with col2:
            st.subheader("Valores UDI (Opcional)")
            st.caption("Si no se proporcionan, se obtendrán automáticamente de Banxico")
            
            udi_t0 = st.number_input(
                "Valor UDI en fecha inicial",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.6f"
            )
            
            udi_tf = st.number_input(
                "Valor UDI en fecha final",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.6f"
            )
            
            inclusivity = st.checkbox(
                "Conteo inclusivo de días",
                value=True,
                help="Incluye ambos extremos en el conteo de días"
            )
        
        submitted = st.form_submit_button("🧮 Calcular Indemnización")
    
    if submitted:
        # Validate dates
        if t0 >= tf:
            st.error("❌ La fecha de inicio debe ser anterior a la fecha final")
        else:
            try:
                with st.spinner("Calculando indemnización..."):
                    # Prepare parameters
                    t0_str = t0.isoformat()
                    tf_str = tf.isoformat()
                    udi_t0_param = udi_t0 if udi_t0 > 0 else None
                    udi_tf_param = udi_tf if udi_tf > 0 else None
                    
                    # Calculate
                    result = calculate_mora_interest(
                        p0_mxn=p0_mxn,
                        t0=t0_str,
                        tf=tf_str,
                        udi_t0=udi_t0_param,
                        udi_tf=udi_tf_param,
                        inclusivity=inclusivity
                    )
                
                # Display results
                st.success("✅ Cálculo completado exitosamente")
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Principal Actualizado",
                        f"${result['P_upd_mxn']:,.2f} MXN"
                    )
                
                with col2:
                    st.metric(
                        "Interés Moratorio",
                        f"${result['interest_mxn']:,.2f} MXN"
                    )
                
                with col3:
                    st.metric(
                        "Total a Pagar",
                        f"${result['total_mxn']:,.2f} MXN"
                    )
                
                with col4:
                    st.metric(
                        "Días en Mora",
                        f"{result['total_days']} días"
                    )
                
                # Detailed results
                st.subheader("📋 Resultados Detallados")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Información General:**")
                    st.write(f"• Principal: ${p0_mxn:,.2f} MXN")
                    st.write(f"• Período: {t0_str} a {tf_str}")
                    st.write(f"• UDI inicial: {result['udi_t0']:.6f}")
                    st.write(f"• UDI final: {result['udi_tf']:.6f}")
                    st.write(f"• Número de períodos: {result['n_periods']}")
                    st.write(f"• Total de días en mora: {result['total_days']}")
                
                with col2:
                    st.write("**Cálculos en UDI:**")
                    st.write(f"• Principal en UDI (U0): {result['U0']:.10f}")
                    st.write(f"• Saldo final en UDI (Ufin): {result['Ufin']:.10f}")
                    st.write(f"• Factor acumulado (Phi): {result['Phi']:.10f}")
                
                # Monthly breakdown table
                st.subheader("📅 Desglose Mensual")
                
                df_breakdown = pd.DataFrame(result['monthly_breakdown'])
                
                # Format the dataframe for better display
                df_display = df_breakdown.copy()
                df_display['CCP (%)'] = df_display['ccp_pct'].apply(lambda x: f"{x:.4f}%")
                df_display['r_a_j'] = df_display['r_a_j'].apply(lambda x: f"{x:.6f}")
                df_display['r_d_j'] = df_display['r_d_j'].apply(lambda x: f"{x:.10f}")
                df_display['F_j'] = df_display['F_j'].apply(lambda x: f"{x:.10f}")
                df_display['Phi_cum'] = df_display['Phi_cum'].apply(lambda x: f"{x:.10f}")
                df_display['Int_UDI'] = df_display['interest_udi_month'].apply(lambda x: f"{x:.10f}")
                df_display['Int_MXN'] = df_display['interest_mxn_month'].apply(lambda x: f"${x:,.2f}")
                
                # Select and rename columns for display
                df_final = df_display[[
                    'month', 'd_j', 'CCP (%)', 'r_a_j', 'r_d_j', 
                    'F_j', 'Phi_cum', 'Int_UDI', 'Int_MXN'
                ]].rename(columns={
                    'month': 'Mes',
                    'd_j': 'Días',
                    'r_a_j': 'r_a_j',
                    'r_d_j': 'r_d_j',
                    'F_j': 'F_j',
                    'Phi_cum': 'Phi_cum',
                    'Int_UDI': 'Interés UDI',
                    'Int_MXN': 'Interés MXN'
                })
                
                st.dataframe(df_final, use_container_width=True)
                
                # Download option
                csv = df_breakdown.to_csv(index=False)
                st.download_button(
                    label="📥 Descargar desglose en CSV",
                    data=csv,
                    file_name=f"indemnizacion_mora_{t0_str}_to_{tf_str}.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"❌ Error en el cálculo: {str(e)}")

elif opcion == "Consultar UDIS":
    st.header("📈 Consulta de Valores UDIS")
    
    with st.form("udis_form"):
        fecha_udis = st.date_input(
            "Fecha para consultar UDIS",
            value=datetime.date.today()
        )
        
        submitted_udis = st.form_submit_button("🔍 Consultar UDIS")
    
    if submitted_udis:
        try:
            with st.spinner("Consultando valor UDIS..."):
                valor_udis = retrieve_udis_daily_value(fecha_udis.isoformat())
            
            st.success("✅ Consulta exitosa")
            
            # Display result
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.metric(
                    "Valor UDIS",
                    f"{valor_udis:.6f}",
                    help=f"Valor para la fecha {fecha_udis.isoformat()}"
                )
            
            with col2:
                st.info(f"📅 **Fecha consultada:** {fecha_udis.strftime('%d de %B de %Y')}")
                st.info(f"💱 **Valor UDIS:** {valor_udis:.6f}")
        
        except Exception as e:
            st.error(f"❌ Error en la consulta: {str(e)}")

elif opcion == "Consultar CCP-UDIS":
    st.header("📊 Consulta de Valores CCP-UDIS")
    
    with st.form("ccp_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_inicio_ccp = st.date_input(
                "Fecha de inicio",
                value=datetime.date(2023, 1, 1)
            )
        
        with col2:
            fecha_fin_ccp = st.date_input(
                "Fecha de fin",
                value=datetime.date.today()
            )
        
        submitted_ccp = st.form_submit_button("🔍 Consultar CCP-UDIS")
    
    if submitted_ccp:
        if fecha_inicio_ccp >= fecha_fin_ccp:
            st.error("❌ La fecha de inicio debe ser anterior a la fecha final")
        else:
            try:
                with st.spinner("Consultando valores CCP-UDIS..."):
                    df_ccp = retrieve_ccp_udis_monthly(
                        fecha_inicio_ccp.isoformat(),
                        fecha_fin_ccp.isoformat()
                    )
                
                st.success("✅ Consulta exitosa")
                
                # Process and display results
                if not df_ccp.empty:
                    # Create display dataframe
                    ccp_data = []
                    for fecha, row in df_ccp.iterrows():
                        if isinstance(fecha, pd.Timestamp):
                            fecha_str = fecha.strftime('%Y-%m')
                        else:
                            fecha_obj = pd.Timestamp(fecha)
                            fecha_str = fecha_obj.strftime('%Y-%m')
                        
                        ccp_data.append({
                            'Mes': fecha_str,
                            'CCP-UDIS (%)': f"{row['dato']:.4f}%",
                            'Valor': row['dato']
                        })
                    
                    df_display_ccp = pd.DataFrame(ccp_data)
                    
                    # Show summary
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Períodos", len(df_display_ccp))
                    
                    with col2:
                        st.metric("CCP Promedio", f"{df_display_ccp['Valor'].mean():.4f}%")
                    
                    with col3:
                        st.metric("CCP Máximo", f"{df_display_ccp['Valor'].max():.4f}%")
                    
                    # Show table
                    st.subheader("📋 Valores CCP-UDIS por Mes")
                    st.dataframe(
                        df_display_ccp[['Mes', 'CCP-UDIS (%)']],
                        use_container_width=True
                    )
                    
                    # Download option
                    csv_ccp = df_display_ccp.to_csv(index=False)
                    st.download_button(
                        label="📥 Descargar datos en CSV",
                        data=csv_ccp,
                        file_name=f"ccp_udis_{fecha_inicio_ccp.isoformat()}_to_{fecha_fin_ccp.isoformat()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("⚠️ No se encontraron datos para el período especificado")
            
            except Exception as e:
                st.error(f"❌ Error en la consulta: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>💼 Calculadora de Indemnización por Mora - Art. 276 LISF</p>
        <p>🏛️ Datos obtenidos de Banco de México (Banxico)</p>
    </div>
    """,
    unsafe_allow_html=True
)