import json
import os
import re

import google_auth_oauthlib.flow
import pytz
import requests
import streamlit as st
from firebase_admin import firestore
from googleapiclient.discovery import build

# Allow insecure transport for local development (http instead of https)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

FIREBASE_API_KEY = st.secrets.firebase.api_key
GOOGLE_CLIENT_SECRETS_FILE = "google_credentials.json"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
]


def firebase_sign_up(email: str, password: str):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resp = requests.post(url, json=payload)
    if not resp.ok:
        error_msg = resp.json().get("error", {}).get("message", "Unknown error")
        raise Exception(error_msg)
    return resp.json()


def firebase_sign_in(email: str, password: str):
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={FIREBASE_API_KEY}"
    )
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resp = requests.post(url, json=payload)
    if not resp.ok:
        error_msg = resp.json().get("error", {}).get("message", "Unknown error")
        raise Exception(error_msg)
    return resp.json()


def get_google_login_url():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=st.secrets.google_auth.redirect_uri,
    )
    # Generate authorization URL and store the verifier in session state
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    st.session_state.google_auth_state = state
    st.session_state.google_auth_verifier = flow.code_verifier
    return authorization_url


def handle_google_callback():
    if "code" in st.query_params and "google_auth_verifier" in st.session_state:
        try:
            # Clear params IMMEDIATELY so re-runs don't try the same code twice
            code = st.query_params["code"]
            st.query_params.clear()

            flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRETS_FILE,
                scopes=SCOPES,
                redirect_uri=st.secrets.google_auth.redirect_uri,
            )
            # Use the saved verifier to satisfy PKCE
            flow.fetch_token(code=code, code_verifier=st.session_state.google_auth_verifier)

            credentials = flow.credentials
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()

            st.session_state.user = {
                "email": user_info.get("email"),
                "first_name": user_info.get("given_name", "User"),
                "last_name": user_info.get("family_name", ""),
            }
            # Final cleanup
            for key in ["google_auth_state", "google_auth_verifier"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        except Exception as e:
            # Only show errors that are NOT "Missing code verifier" or common Grant errors
            if "invalid_grant" in str(e).lower():
                st.error("Login link expired. Please click 'Sign in with Google' again.")
            else:
                st.error(f"Google Login Error: {str(e)}")
            st.query_params.clear()


def render_authentication(db) -> bool:
    if "user" not in st.session_state:
        st.session_state.user = None

    # Handle completion of Google Sign-in flow
    handle_google_callback()

    if st.session_state.user:
        return True

    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.markdown(
                "<h1 style='text-align: center;'>Diabetes Manager Login</h1>",
                unsafe_allow_html=True,
            )

            # Google Login Button (Custom Styled)
            login_url = get_google_login_url()
            st.markdown(
                f"""
                <div style="display: flex; justify-content: center; margin-bottom: 2rem;">
                    <a href="{login_url}" target="_self" style="background-color: #4285f4; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; display: flex; align-items: center; border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.25);">
                        <img src="https://lh3.googleusercontent.com/COxitqgJr1sJnIDe8-jiKhxDx1FrYbtRHKJ9z_hELisAlapwE9LUPh6fcXIfb5vwpbMl4xl9H9TRFPc5NOO8Sb3VSgIBrfRYvW6cUA" style="width: 20px; margin-right: 10px; background: white; border-radius: 2px; padding: 1px;">
                        Sign in with Google
                    </a>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)

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
                            else:
                                # Create a basic profile if search fails
                                db.collection("users").document(user["localId"]).set(
                                    {
                                        "first_name": "New User",
                                        "last_name": "",
                                        "email": email,
                                        "created_at": firestore.SERVER_TIMESTAMP,
                                    }
                                )
                                st.session_state.user = {
                                    "email": email,
                                    "first_name": "New User",
                                    "last_name": "",
                                }
                            st.success(
                                f"Welcome back, {st.session_state.user['first_name']}! 😊"
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"Authentication failed: {str(e)}")

    st.stop()
