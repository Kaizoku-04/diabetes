from datetime import datetime

import firebase_admin
import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from firebase_admin import credentials, firestore

from services import send_sms_reminder


def initialize_firestore():
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(
                {
                    "type": st.secrets.firebase.type,
                    "project_id": st.secrets.firebase.project_id,
                    "private_key_id": st.secrets.firebase.private_key_id,
                    "private_key": st.secrets.firebase.private_key,
                    "client_email": st.secrets.firebase.client_email,
                    "client_id": st.secrets.firebase.client_id,
                    "auth_uri": st.secrets.firebase.auth_uri,
                    "token_uri": st.secrets.firebase.token_uri,
                    "auth_provider_x509_cert_url": st.secrets.firebase.auth_provider_x509_cert_url,
                    "client_x509_cert_url": st.secrets.firebase.client_x509_cert_url,
                }
            )
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Firebase initialization error: {str(e)}")

    return firestore.client()


def log_medication_taken(db, med_name: str):
    db.collection("med_history").add(
        {
            "user": st.session_state.user["first_name"],
            "medicine": med_name,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
    )


def check_reminders(db):
    user_email = st.session_state.get("user", {}).get("email", None)
    if user_email:
        now = datetime.now().strftime("%H:%M")
        reminders = db.collection("reminders").where("User", "==", user_email).stream()
        for rem in reminders:
            rem_data = rem.to_dict()
            if rem_data.get("Time") == now:
                send_sms_reminder(
                    f"Time to take {rem_data.get('Medicine')}", st.secrets.user.phone
                )


def initialize_scheduler(db):
    if "scheduler" not in st.session_state:
        scheduler = BackgroundScheduler()
        scheduler.add_job(lambda: check_reminders(db), "interval", minutes=1)
        scheduler.start()
        st.session_state.scheduler = scheduler
