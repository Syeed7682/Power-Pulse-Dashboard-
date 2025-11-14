import os
import time
import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from plotly.subplots import make_subplots
# ---------------------- CONFIGURATION ----------------------
st.set_page_config(
    page_title="Energy Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Use simulation or real TinyTuya
USE_SIMULATION = True  # Set to False to control the real device

# CSV file for logging
CSV_FILE = "demo.csv"

# TinyTuya / mock config (replace with real values as needed)
DEV_ID = "a32bc8e7d1a6db3d9abhib "
ADDRESS = "103.72.212.110"
LOCAL_KEY = "abcdef1234567890"
VERSION = 3.3
DPS_INDEX_SWITCH = 1
DPS_INDEX_POWER = 19

# ================================================================
#  SESSION STATE INIT
# ================================================================
if "device_status" not in st.session_state:
    st.session_state.device_status = "OFF"   # default OFF

if "last_api_call" not in st.session_state:
    st.session_state.last_api_call = time.time()

# ================================================================
#  MOCK TINYTUYA CLASSES (minimal)
# ================================================================
class TinytuyaException(Exception):
    pass

class OutletDevice:
    """Minimal mock class to support dashboard logic."""
    def __init__(self, dev_id, address, local_key):
        self.dev_id = dev_id
        self.address = address
        self.local_key = local_key

    def set_version(self, version):
        pass

    def set_socketPersistent(self, state):
        pass

    def set_value(self, dp_id, value, nowait=False):
        target = "ON" if value else "OFF"
        st.session_state.device_status = target
        return {"ok": True}

    def status(self):
        is_on = st.session_state.device_status == "ON"
        return {
            "dps": {
                str(DPS_INDEX_SWITCH): is_on,
                str(DPS_INDEX_POWER): 150,
            }
        }

# ================================================================
#  SIMULATION / CONTROL WRAPPER
# ================================================================
def control_device(new_state: str) -> bool:
    """Simulate controlling the real device (updates session state)."""
    st.session_state.device_status = new_state
    st.session_state.last_api_call = time.time()
    return True

# ================================================================
#  HEADER
# ================================================================
st.markdown("""
<div style="
    text-align: center;
    font-size: 40px;
    font-family: 'Trebuchet MS', Helvetica, sans-serif;
    color: #FF6F61;
    font-weight: bold;
    text-shadow: 2px 2px 4px #000000;
">
    ⚡ Power Pulse Dashboard ⚡
</div>
""", unsafe_allow_html=True)

# ================================================================
#  SINGLE TOGGLE BUTTON (ONLY ONE ON/OFF BUTTON IN THE APP)
#  Placed before the OFF check so it's always available.
# ================================================================
col1, col2, col3 = st.columns([1.5, 1, 1])
with col2:
    toggle_label = "Turn OFF Device" if st.session_state.device_status == "ON" else "Turn ON Device"
    if st.button(toggle_label, key="toggle_device"):
        new_state = "OFF" if st.session_state.device_status == "ON" else "ON"
        control_device(new_state)
        st.rerun()

# ================================================================
#  IF DEVICE IS OFF → OFF-SCREEN MODE (no additional on/off buttons)
# ================================================================
if st.session_state.device_status == "OFF":
    st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
            <div style="text-align:center;">
                <h1 style="font-size:60px; color:red;">⚠️ Site Offline</h1>
                <p style="font-size:20px;">
                    The device is turned OFF. Use the single toggle button above to turn it ON.
                </p>
            </div>
        """, unsafe_allow_html=True)

    st.stop()  # <- Dashboard stops completely here when device is OFF

# ================================================================
#  DEVICE IS ON → SHOW DASHBOARD
# ================================================================
st.success("Device is ON — Dashboard Loaded ✔")

# --- 3. Data Loading (Cached for performance) ---

@st.cache_data(ttl=5) 
def load_data():
    """Loads and preprocesses the energy log data from CSV."""
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=[
            "Timestamp", "Voltage (V)", "Current (A)", "Power (W)", "Energy (kWh)", "Status"
        ])

    try:
        df = pd.read_csv(CSV_FILE)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", infer_datetime_format=True)
        df = df.dropna(subset=["Timestamp"])
        
        numeric_cols = ["Voltage (V)", "Current (A)", "Power (W)", "Energy (kWh)"]
        for col in numeric_cols:
             df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.drop_duplicates(subset=["Timestamp"], keep='last').sort_values("Timestamp").reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error loading or parsing CSV data: {e}")
        return pd.DataFrame(columns=[
            "Timestamp", "Voltage (V)", "Current (A)", "Power (W)", "Energy (kWh)", "Status"
        ])

# --- 4. Sidebar Controls and Auto-refresh ---
# ... (rest of your imports and functions) ...

# ...

with st.sidebar:
    st.header("Dashboard Settings")
    
    # Initialize session state for the refresh control if it doesn't exist
if 'auto_refresh_enabled' not in st.session_state:
    st.session_state.auto_refresh_enabled = True
if 'refresh_interval_seconds' not in st.session_state:
    st.session_state.refresh_interval_seconds = 10 # Default to 10 seconds

# ...

with st.sidebar:

    # Checkbox to enable/disable auto-refresh
    st.session_state.auto_refresh_enabled = st.checkbox(
        "Enable Automatic Refresh",
        value=st.session_state.auto_refresh_enabled,
        key="refresh_checkbox"
    )
    
    # Number input for the refresh interval, only enabled if the checkbox is checked
    st.session_state.refresh_interval_seconds = st.number_input(
        "Refresh Interval (seconds)",
        min_value=2,
        max_value=60,
        value=st.session_state.refresh_interval_seconds,
        step=1,
        key="refresh_interval_input",
        disabled=not st.session_state.auto_refresh_enabled,
        help="Set the time between automatic dashboard updates."
    )
    
    # Display current status in an info box
    if st.session_state.auto_refresh_enabled:
        st.success(f"Auto-refresh is **ON** ({st.session_state.refresh_interval_seconds}s)")
    else:
        st.warning("Auto-refresh is **OFF**. Data will only update on interaction.")
    
    st.markdown("---")
    st.subheader("Billing Configuration")
    cost_per_kwh = st.number_input(
        "Energy Cost per Unit (BDT/kWh)", 
        min_value=0.01, 
        # Using session state to retrieve the value if it exists, otherwise 7.50
        value=st.session_state.get('cost_per_kwh', 7.50),
        step=0.1, 
        format="%.2f",
        key="cost_input", # Using key to ensure session state is updated
        help="Enter the cost for 1 kilowatt-hour (kWh)."
    )
    st.session_state.cost_per_kwh = cost_per_kwh 
    
    st.markdown("---")
    

# 2. Re-enable the Auto-refresh trigger outside the sidebar
# The interval is set by the sidebar slider value, which defaults to 10 seconds.
st_autorefresh(interval=st.session_state.refresh_interval_seconds * 1000, key="data_refresher_unified")

# ... (rest of your dashboard code) ...



# --- 6. Data Loading and Visualization ---
df = load_data()

if df.empty or len(df) < 2: 
    st.info("Waiting for data. Ensure 'demo.csv' has at least 2 rows of data.")
else:
    
    # 6.1. Real-Time Metrics Display

    # Reload latest CSV data
    df_latest = pd.read_csv(CSV_FILE)

    # Ensure Timestamp is parsed (important for order)
    df_latest["Timestamp"] = pd.to_datetime(df_latest["Timestamp"], errors="coerce")
    df_latest = df_latest.sort_values(by="Timestamp", ascending=True)

    # Get the latest two rows for metrics
    latest = df_latest.iloc[-1]
    previous = df_latest.iloc[-2]

    st.subheader("Real-Time Metrics")

    col1, col2, col3, col4 = st.columns(4)

    # Calculate deltas
    power_delta = latest['Power (W)'] - previous['Power (W)']
    energy_delta = latest['Energy (kWh)'] - previous['Energy (kWh)']

    col1.metric("Voltage (V)", f"{latest['Voltage (V)']:.1f}")
    col2.metric("Current (A)", f"{latest['Current (A)']:.3f}")
    col3.metric("Power (W)", f"{latest['Power (W)']:.1f}", delta=f"{power_delta:.1f} W")
    col4.metric("Energy (kWh)", f"{latest['Energy (kWh)']:.3f}", delta=f"{energy_delta:.3f} kWh")

    st.markdown("---")


    # 6.2. Time Series Plots
    st.subheader("Historical Trends")

    ## Power Consumption Log


# Optional: display a dummy chart from CSV
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    if not df.empty:
        # --- START OF THE SINGLE, WORKABLE CHART ---
        fig_power = px.line(df, x="Timestamp", y="Power (W)",
                            title="Power Consumption Over Time (W)",
                            labels={"Power (W)": "Power (W)", "Timestamp": "Time"},
                            template="plotly_dark",
                            line_shape='spline'
                            )
        fig_power.update_traces(line=dict(width=3, color="#0E6F12"))
        fig_power.update_layout(hovermode="x unified")
        st.plotly_chart(fig_power, use_container_width=True)
        # --- END OF THE SINGLE, WORKABLE CHART ---
    else:
        st.write("CSV log is empty.")
else:
    st.write(f"No log file found at: **{CSV_FILE}**")

# Optional: Auto-refresh the dashboard every 10 seconds (e.g., to fetch new status/data)
st_autorefresh(interval=10000, key="data_refresher")

col_a, col_b = st.columns(2)

with col_a:
        fig_voltage = px.line(df, x="Timestamp", y="Voltage (V)", 
                              title="Voltage Stability Over Time (V)",
                              template="plotly_dark",
                              line_shape='spline'
                             )
        fig_voltage.update_traces(line=dict(width=2, color='#2196F3'))
        fig_voltage.update_layout(hovermode="x unified")
        st.plotly_chart(fig_voltage, use_container_width=True)
    
with col_b:
        fig_current = px.line(df, x="Timestamp", y="Current (A)", 
                              title="Current Load Over Time (A)",
                              template="plotly_dark",
                              line_shape='spline'
                             )
        fig_current.update_traces(line=dict(width=2, color="#FF6A00"))
        fig_current.update_layout(hovermode="x unified")
        st.plotly_chart(fig_current, use_container_width=True)

st.markdown("---")

# 6.3. Consumption Summary and Data Table
st.subheader("Consumption Summary")



# Reload latest CSV data
df_latest = pd.read_csv(CSV_FILE)

# Ensure Timestamp is parsed and sorted
df_latest["Timestamp"] = pd.to_datetime(df_latest["Timestamp"], errors="coerce")
df_latest = df_latest.sort_values(by="Timestamp", ascending=True)

# Compute summary values from latest CSV
total_energy = df_latest["Energy (kWh)"].max()
max_power = df_latest["Power (W)"].max()

current_cost_per_kwh = st.session_state.get('cost_per_kwh', 7.50)
total_cost_bdt = total_energy * current_cost_per_kwh

col_summary_1, col_summary_2, col_summary_3 = st.columns(3)

col_summary_1.metric("Total Accumulated Energy (kWh)", f"{total_energy:.3f} kWh")
col_summary_2.metric("Peak Power Recorded (W)", f"{max_power:.1f} W")
col_summary_3.metric("Estimated Total Cost (BDT)", f"৳ {total_cost_bdt:,.2f}")

# --- Add line chart for Power, Energy and Cost ---
if not df_latest.empty:
    # Compute cost series (cumulative cost based on cumulative Energy)
    df_latest = df_latest.copy()
    df_latest["Cost (BDT)"] = df_latest["Energy (kWh)"].astype(float) * float(current_cost_per_kwh)

    # Ensure numeric types and drop NaNs for plotting
    for col in ["Power (W)", "Energy (kWh)", "Cost (BDT)"]:
        df_latest[col] = pd.to_numeric(df_latest[col], errors="coerce")
    plot_df = df_latest.dropna(subset=["Timestamp", "Power (W)", "Energy (kWh)", "Cost (BDT)"])

    if not plot_df.empty:
        import plotly.graph_objects as go

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        # Power on primary y (left)
        fig.add_trace(
            go.Scatter(x=plot_df["Timestamp"], y=plot_df["Power (W)"],
                       mode="lines", name="Power (W)",
                       line=dict(color="#0E6F12", width=2)),
            secondary_y=False
        )
        # Energy on secondary y (right)
        fig.add_trace(
            go.Scatter(x=plot_df["Timestamp"], y=plot_df["Energy (kWh)"],
                       mode="lines", name="Energy (kWh)",
                       line=dict(color="#2196F3", width=2, dash="dash")),
            secondary_y=True
        )
        # Cost on secondary y (right)
        fig.add_trace(
            go.Scatter(x=plot_df["Timestamp"], y=plot_df["Cost (BDT)"],
                       mode="lines", name="Cost (BDT)",
                       line=dict(color="#FF6A00", width=2, dash="dot")),
            secondary_y=True
        )

        fig.update_layout(
            title="Power, Energy and Estimated Cost Over Time",
            template="plotly_dark",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_yaxes(title_text="Power (W)", secondary_y=False)
        fig.update_yaxes(title_text="Energy (kWh) / Cost (BDT)", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)


# --- Recent Data Log ---
st.markdown("### Recent Data Log")

# Reload CSV to always get the latest data
df_latest = pd.read_csv(CSV_FILE)


# Take the last 20 rows to show recent data
recent_df = df_latest.tail(10).reset_index(drop=True)

# Display the recent data log
st.dataframe(recent_df, use_container_width=True, hide_index=True)

