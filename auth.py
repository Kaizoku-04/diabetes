import re

import pytz
import requests
import streamlit as st
from firebase_admin import firestore

FIREBASE_API_KEY = st.secrets.firebase.api_key


def firebase_sign_up(email: str, password: str):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


def firebase_sign_in(email: str, password: str):
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={FIREBASE_API_KEY}"
    )
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


def render_authentication(db) -> bool:
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user:
        return True

    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.markdown(
                "<h1 style='text-align: center;'>Diabetes Manager Login</h1>",
                unsafe_allow_html=True,
            )

            auth_mode = st.radio(
                "Choose action",
                ["Login", "Sign Up"],
                horizontal=True,
                label_visibility="collapsed",
            )

            with st.form("auth_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")

                if auth_mode == "Sign Up":
                    first_name = st.text_input("First Name")
                    last_name = st.text_input("Last Name")
                    confirm_password = st.text_input("Confirm Password", type="password")
                    phone = st.text_input("Phone Number (+1234567890)")
                    if phone and not re.match(r"^\+[1-9]\d{1,14}$", phone):
                        st.error("Please enter valid E.164 format: +[country code][number]")
                    utc_index = pytz.common_timezones.index("UTC")
                    timezone = st.selectbox(
                        "Timezone", pytz.common_timezones, index=utc_index
                    )

                submitted = st.form_submit_button(
                    "Login" if auth_mode == "Login" else "Sign Up"
                )

                if submitted:
                    try:
                        if auth_mode == "Sign Up":
                            if password != confirm_password:
                                st.error("Passwords do not match!")
                            else:
                                user = firebase_sign_up(email, password)
                                db.collection("users").document(user["localId"]).set(
                                    {
                                        "first_name": first_name,
                                        "last_name": last_name,
                                        "email": email,
                                        "phone": phone,
                                        "timezone": timezone,
                                        "created_at": firestore.SERVER_TIMESTAMP,
                                    }
                                )
                                st.session_state.user = {
                                    "email": email,
                                    "first_name": first_name,
                                    "last_name": last_name,
                                }
                                st.success(f"Welcome, {first_name}! 🎉")
                                st.rerun()
                        else:
                            user = firebase_sign_in(email, password)
                            user_doc = db.collection("users").document(user["localId"]).get()
                            if user_doc.exists:
                                user_data = user_doc.to_dict()
                                st.session_state.user = {
                                    "email": email,
                                    "first_name": user_data.get("first_name", "User"),
                                    "last_name": user_data.get("last_name", ""),
                                }
                                st.success(
                                    f"Welcome back, {st.session_state.user['first_name']}! 😊"
                                )
                                st.rerun()
                            else:
                                st.error("User details not found in the database.")
                    except Exception as e:
                        st.error(f"Authentication failed: {str(e)}")

    st.stop()
