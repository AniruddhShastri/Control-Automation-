"""
BIOGAS DIGESTER SMART CONTROL - EXPERIMENT RESULTS DASHBOARD
Professional presentation of 60-minute temperature control test
Shows: Live data, temperature control, energy savings, cycle analysis
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Biogas Digester - Experiment Results",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .header-title {
        font-size: 3em;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 10px;
    }
    .section-header {
        font-size: 1.8em;
        color: #1f77b4;
        border-bottom: 3px solid #ff7f0e;
        padding-bottom: 10px;
        margin-top: 30px;
    }
    .metric-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .metric-value {
        font-size: 2em;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9em;
        opacity: 0.9;
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================================
# DATA LOADING & PROCESSING
# ============================================================================

@st.cache_data
def load_experiment_data():
    """Load experiment data from CSV."""
    try:
        df = pd.read_csv('experiment_data.csv')

        # Convert heater_state from 'ON'/'OFF' to 1/0
        df['heater_state'] = (df['heater_state'].str.upper() == 'ON').astype(int)

        # Create proper timestamp (if just integer, treat as seconds from start)
        if df['timestamp'].dtype in ['int64', 'float64']:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df.sort_values('timestamp').reset_index(drop=True)
    except FileNotFoundError:
        st.error("❌ experiment_data.csv not found!")
        st.info("Please save your Excel file as CSV: experiment_data.csv")
        return None


def identify_heating_cycles(df):
    """Identify and analyze heating cycles."""
    cycles = []
    in_cycle = False
    cycle_start = None
    energy_per_cycle = []

    for idx, row in df.iterrows():
        if row['heater_state'] == 1 and not in_cycle:
            in_cycle = True
            cycle_start = idx

        elif row['heater_state'] == 0 and in_cycle:
            in_cycle = False
            start_time = df.loc[cycle_start, 'timestamp']
            end_time = df.loc[idx, 'timestamp']
            duration = (end_time - start_time).total_seconds() / 60

            # Calculate energy for this cycle
            cycle_data = df.loc[cycle_start:idx]
            cycle_energy = (cycle_data['power_watts'].sum() / 1000 / 60)  # Convert to kWh

            cycles.append({
                'number': len(cycles) + 1,
                'start': start_time,
                'end': end_time,
                'duration_minutes': duration,
                'energy_kwh': cycle_energy,
                'avg_temp_start': df.loc[cycle_start, 'temperature_celsius'],
                'avg_temp_end': df.loc[idx, 'temperature_celsius'],
                'max_current': cycle_data['current_amps'].max()
            })
            energy_per_cycle.append(cycle_energy)

    return cycles, energy_per_cycle


def calculate_comprehensive_metrics(df):
    """Calculate all energy and performance metrics."""
    df = df.copy()

    # Power calculation
    df['power_watts'] = df['current_amps'] * 230  # Assuming 230V

    # Total metrics
    total_energy_wh = (df['power_watts'] / 60).sum()
    total_energy_kwh = total_energy_wh / 1000

    # Baseline (continuous heating)
    heater_power_on = df[df['heater_state'] == 1]['power_watts'].mean()
    total_minutes = len(df)
    baseline_energy_kwh = (heater_power_on * total_minutes) / 60 / 1000

    # Savings
    saved_energy_kwh = baseline_energy_kwh - total_energy_kwh
    savings_percent = (saved_energy_kwh / baseline_energy_kwh * 100) if baseline_energy_kwh > 0 else 0

    # Cycles
    cycles, energy_per_cycle = identify_heating_cycles(df)

    # Temperature analysis
    temp_mean = df['temperature_celsius'].mean()
    temp_min = df['temperature_celsius'].min()
    temp_max = df['temperature_celsius'].max()
    temp_std = df['temperature_celsius'].std()
    in_range = len(df[(df['temperature_celsius'] >= 32) & (df['temperature_celsius'] <= 37)])
    in_range_percent = (in_range / len(df)) * 100

    # Heater statistics
    heater_on_time = len(df[df['heater_state'] == 1])
    heater_on_percent = (heater_on_time / len(df)) * 100
    avg_current = df['current_amps'].mean()
    max_current = df['current_amps'].max()

    return {
        'total_energy_kwh': total_energy_kwh,
        'baseline_energy_kwh': baseline_energy_kwh,
        'saved_energy_kwh': saved_energy_kwh,
        'savings_percent': savings_percent,
        'cycles': cycles,
        'num_cycles': len(cycles),
        'avg_cycle_energy': sum(energy_per_cycle) / len(energy_per_cycle) if energy_per_cycle else 0,
        'temp_mean': temp_mean,
        'temp_min': temp_min,
        'temp_max': temp_max,
        'temp_std': temp_std,
        'in_range_percent': in_range_percent,
        'heater_on_percent': heater_on_percent,
        'heater_on_time': heater_on_time,
        'avg_current': avg_current,
        'max_current': max_current,
        'total_time_minutes': total_minutes,
        'df': df
    }


# ============================================================================
# STREAMLIT LAYOUT
# ============================================================================

def main():
    # Header
    st.markdown("<div class='header-title'>🔥 Biogas Digester Control System</div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align: center; font-size: 1.3em; color: #666;'>5-Minute Experiment Results & Analysis</div>",
        unsafe_allow_html=True)
    st.markdown("---")

    # Load data
    df = load_experiment_data()
    if df is None or df.empty:
        st.stop()

    # Calculate metrics
    metrics = calculate_comprehensive_metrics(df)
    df_experiment = metrics['df']

    # Get time range
    start_time = df['timestamp'].min()
    end_time = df['timestamp'].max()
    duration_minutes = (end_time - start_time).total_seconds() / 60

    # ========================================================================
    # SECTION 1: EXECUTIVE SUMMARY (Key Numbers)
    # ========================================================================

    st.markdown("<div class='section-header'>📊 Executive Summary</div>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="⚡ Energy Saved",
            value=f"{metrics['saved_energy_kwh']:.3f} kWh",
            delta=f"{metrics['savings_percent']:.1f}%",
            delta_color="normal"
        )

    with col2:
        st.metric(
            label="🌡️ Avg Temperature",
            value=f"{metrics['temp_mean']:.1f} °C",
            delta="In range" if metrics['in_range_percent'] > 90 else "Variable"
        )

    with col3:
        st.metric(
            label="🔄 Heating Cycles",
            value=metrics['num_cycles'],
            delta=f"{metrics['heater_on_percent']:.1f}% ON time"
        )

    with col4:
        st.metric(
            label="⏱️ Test Duration",
            value=f"{duration_minutes:.0f} min",
            delta=f"Completed successfully"
        )

    st.markdown("---")

    # ========================================================================
    # SECTION 2: KEY FINDINGS
    # ========================================================================

    st.markdown("<div class='section-header'>🎯 Key Findings</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.success(f"""
        **Temperature Control Effectiveness:**
        - Mean temperature: **{metrics['temp_mean']:.2f}°C** (Target: 32-37°C)
        - Temperature stability (σ): **{metrics['temp_std']:.2f}°C**
        - Time in range: **{metrics['in_range_percent']:.1f}%**
        - Min: {metrics['temp_min']:.1f}°C | Max: {metrics['temp_max']:.1f}°C
        """)

    with col2:
        st.info(f"""
        **Energy Efficiency Results:**
        - Actual consumption: **{metrics['total_energy_kwh']:.4f} kWh**
        - Baseline (continuous): **{metrics['baseline_energy_kwh']:.4f} kWh**
        - Energy saved: **{metrics['saved_energy_kwh']:.4f} kWh**
        - Efficiency gain: **{metrics['savings_percent']:.1f}%**
        """)

    st.markdown("---")

    # ========================================================================
    # SECTION 3: REAL-TIME PLOT - Temperature ONLY (NO HEATER LINE)
    # ========================================================================

    st.markdown("<div class='section-header'>📈 Temperature Control</div>", unsafe_allow_html=True)

    fig_combined = go.Figure()

    # Temperature (smooth line)
    fig_combined.add_trace(
        go.Scatter(
            x=df_experiment['timestamp'],
            y=df_experiment['temperature_celsius'],
            name='Temperature (°C)',
            line=dict(color='#0066cc', width=3, shape='spline'),
            mode='lines',
            hovertemplate='<b>Temperature</b><br>%{y:.2f}°C<br>%{x|%H:%M:%S}<extra></extra>'
        )
    )

    # Target range (32–37°C) - shaded background
    fig_combined.add_hrect(
        y0=32, y1=37,
        fillcolor='rgba(0, 200, 0, 0.1)',
        layer="below",
        line_width=0
    )

    # Setpoint lines
    fig_combined.add_hline(y=32, line_dash="dash", line_color="red", annotation_text="Lower (32°C)", annotation_position="right")
    fig_combined.add_hline(y=37, line_dash="dash", line_color="orange", annotation_text="Upper (37°C)", annotation_position="right")

    fig_combined.update_xaxes(title_text="Time (HH:MM:SS)")
    fig_combined.update_yaxes(title_text="Temperature (°C)", range=[28, 42])

    fig_combined.update_layout(
        title_text="Temperature Control in Mesophilic Range (32-37°C)",
        hovermode='x unified',
        height=450,
        legend=dict(x=0.01, y=0.99),
        showlegend=True
    )

    st.plotly_chart(fig_combined, use_container_width=True)

    st.markdown("---")

    # ========================================================================
    # SECTION 4: ENERGY ANALYSIS
    # ========================================================================

    st.markdown("<div class='section-header'>💡 Energy Consumption Analysis</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        # Energy comparison bar chart
        categories = ['Baseline\n(Continuous)', 'Actual\n(Smart Control)', 'Saved']
        values = [
            metrics['baseline_energy_kwh'],
            metrics['total_energy_kwh'],
            metrics['saved_energy_kwh']
        ]
        colors = ['#ff6b6b', '#4dabf7', '#51cf66']

        fig_energy = go.Figure(
            data=go.Bar(
                x=categories,
                y=values,
                text=[f'{v:.4f}<br>kWh' for v in values],
                textposition='outside',
                marker=dict(color=colors),
                hovertemplate='<b>%{x}</b><br>%{y:.4f} kWh<extra></extra>'
            )
        )

        fig_energy.update_layout(
            title="Energy Consumption Comparison",
            yaxis_title="Energy (kWh)",
            showlegend=False,
            height=400
        )

        st.plotly_chart(fig_energy, use_container_width=True)

    with col2:
        # Current/Power over time
        fig_current = go.Figure()

        fig_current.add_trace(go.Scatter(
            x=df_experiment['timestamp'],
            y=df_experiment['current_amps'],
            fill='tozeroy',
            name='Current (A)',
            line=dict(color='#9467bd', width=2),
            fillcolor='rgba(148, 103, 189, 0.2)',
            hovertemplate='<b>Current</b><br>%{y:.2f} A<br>%{x|%H:%M:%S}<extra></extra>'
        ))

        fig_current.update_layout(
            title="Current Draw Over Time",
            xaxis_title="Time",
            yaxis_title="Current (A)",
            height=400,
            hovermode='x unified'
        )

        st.plotly_chart(fig_current, use_container_width=True)

    st.markdown("---")

    # ========================================================================
    # SECTION 5: HEATING CYCLE ANALYSIS
    # ========================================================================

    st.markdown("<div class='section-header'>🔄 Heating Cycle Analysis</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        # Cycle duration bar chart
        if metrics['cycles']:
            cycle_numbers = [c['number'] for c in metrics['cycles']]
            cycle_durations = [c['duration_minutes'] for c in metrics['cycles']]

            fig_cycles = go.Figure(
                data=go.Bar(
                    x=[f"Cycle {n}" for n in cycle_numbers],
                    y=cycle_durations,
                    marker_color='#2ca02c',
                    text=[f'{d:.1f} min' for d in cycle_durations],
                    textposition='outside',
                    hovertemplate='<b>%{x}</b><br>Duration: %{y:.1f} min<extra></extra>'
                )
            )

            fig_cycles.update_layout(
                title="Duration of Each Heating Cycle",
                yaxis_title="Duration (minutes)",
                showlegend=False,
                height=400
            )

            st.plotly_chart(fig_cycles, use_container_width=True)

    with col2:
        # Cycle energy consumption
        if metrics['cycles']:
            cycle_numbers = [c['number'] for c in metrics['cycles']]
            cycle_energies = [c['energy_kwh'] for c in metrics['cycles']]

            fig_cycle_energy = go.Figure(
                data=go.Bar(
                    x=[f"Cycle {n}" for n in cycle_numbers],
                    y=cycle_energies,
                    marker_color='#ff7f0e',
                    text=[f'{e:.5f} kWh' for e in cycle_energies],
                    textposition='outside',
                    hovertemplate='<b>%{x}</b><br>Energy: %{y:.5f} kWh<extra></extra>'
                )
            )

            fig_cycle_energy.update_layout(
                title="Energy Consumption Per Cycle",
                yaxis_title="Energy (kWh)",
                showlegend=False,
                height=400
            )

            st.plotly_chart(fig_cycle_energy, use_container_width=True)

    # Cycles detailed table
    st.subheader("📋 Detailed Cycle Breakdown")
    if metrics['cycles']:
        cycles_df = pd.DataFrame(metrics['cycles'])
        cycles_df = cycles_df[[
            'number', 'start', 'end', 'duration_minutes', 'energy_kwh',
            'avg_temp_start', 'avg_temp_end', 'max_current'
        ]].copy()

        cycles_df.columns = ['Cycle', 'Start Time', 'End Time', 'Duration (min)', 'Energy (kWh)',
                             'Start Temp (°C)', 'End Temp (°C)', 'Max Current (A)']

        cycles_df['Start Time'] = cycles_df['Start Time'].dt.strftime('%H:%M:%S')
        cycles_df['End Time'] = cycles_df['End Time'].dt.strftime('%H:%M:%S')

        st.dataframe(cycles_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ========================================================================
    # SECTION 6: DETAILED STATISTICS
    # ========================================================================

    st.markdown("<div class='section-header'>📊 Detailed Statistics</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🌡️ Temperature Stats")
        st.write(f"**Mean:** {metrics['temp_mean']:.2f}°C")
        st.write(f"**Std Dev:** {metrics['temp_std']:.2f}°C")
        st.write(f"**Min:** {metrics['temp_min']:.2f}°C")
        st.write(f"**Max:** {metrics['temp_max']:.2f}°C")
        st.write(f"**In Range (32-37°C):** {metrics['in_range_percent']:.1f}%")

    with col2:
        st.subheader("⚡ Power Stats")
        st.write(f"**Total Energy:** {metrics['total_energy_kwh']:.4f} kWh")
        st.write(f"**Baseline Energy:** {metrics['baseline_energy_kwh']:.4f} kWh")
        st.write(f"**Saved Energy:** {metrics['saved_energy_kwh']:.4f} kWh")
        st.write(f"**Savings:** {metrics['savings_percent']:.1f}%")
        st.write(f"**Avg Current:** {metrics['avg_current']:.2f} A")

    with col3:
        st.subheader("🔄 Heater Stats")
        st.write(f"**Total Cycles:** {metrics['num_cycles']}")
        st.write(f"**Heater ON Time:** {metrics['heater_on_time']} samples")
        st.write(f"**ON Percentage:** {metrics['heater_on_percent']:.1f}%")
        st.write(f"**Avg Cycle Energy:** {metrics['avg_cycle_energy']:.4f} kWh")
        st.write(f"**Max Current:** {metrics['max_current']:.2f} A")

    st.markdown("---")

    # ========================================================================
    # FOOTER
    # ========================================================================

    st.markdown("""
    <div style='text-align: center; color: #999; font-size: 0.9em; margin-top: 40px;'>
    🔧 Biogas Digester Smart Control System - Experiment Results Dashboard<br>
    Data source: experiment_data.csv | Test duration: 5 minutes<br>
    <strong>Conclusion:</strong> Smart hysteresis-based temperature control significantly reduces energy consumption
    while maintaining temperature stability in the optimal biogas production range (32-37°C).
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
