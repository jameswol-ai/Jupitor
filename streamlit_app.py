import streamlit as st
import pandas as pd
from engine.random import ForexEngine  # Random Forex Intelligence
from engine.sai import SaiArchitect    # Sai Structural/Arch Engine

st.set_page_config(page_title="Arc OS", layout="wide")

# Persistent State Management
if 'arc_state' not in st.session_state:
    st.session_state.arc_state = {"market": None, "structural": None}

def main():
    st.title("Arc | AI Operating System")
    
    # Sidebar: System Controls
    with st.sidebar:
        st.header("Mode Selection")
        mode = st.radio("Intelligence Engine", ["Forex (Random)", "Arch (Sai)"])
    
    # Engine Dispatcher
    if mode == "Forex (Random)":
        render_forex_module()
    else:
        render_arch_module()

def render_forex_module():
    st.subheader("Random: Forex Intelligence")
    # Live indices for UGX/KES/SSP
    df = ForexEngine.get_live_indices()
    st.dataframe(df)

def render_arch_module():
    st.subheader("Sai: Architectural Synthesis")
    # Eurocode structural checks & 3D projection
    col1, col2 = st.columns(2)
    with col1:
        st.write("Structural Analysis Input")
    with col2:
        st.write("3D Isometric Projection")

if __name__ == "__main__":
    main()
