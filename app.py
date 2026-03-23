import streamlit as st

from auth import render_authentication
from data_layer import initialize_firestore, initialize_scheduler
from pages import (
    render_chatbot_page,
    render_diet_page,
    render_home_page,
    render_medication_page,
    render_schedule_page,
)

st.set_page_config(page_title="Diabetes Manager", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .st-emotion-cache-1v0mbdj {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)

db = initialize_firestore()
initialize_scheduler(db)
render_authentication(db)

st.sidebar.title("Navigation")
menu = st.sidebar.radio(
    "Main Menu",
    ["Home", "Chatbot", "Schedule", "Diet Plan", "Medication Reminders"],
)
if st.sidebar.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()

if menu == "Home":
    render_home_page()
elif menu == "Chatbot":
    render_chatbot_page()
elif menu == "Schedule":
    render_schedule_page(db)
elif menu == "Diet Plan":
    render_diet_page()
elif menu == "Medication Reminders":
    render_medication_page(db)
