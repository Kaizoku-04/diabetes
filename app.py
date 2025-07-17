import streamlit as st
import pandas as pd
from datetime import datetime
from twilio.rest import Client
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from apscheduler.schedulers.background import BackgroundScheduler
import re
import pytz
def get_nutrition_info(food):
    try:
        response = requests.get(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={
                "api_key": st.secrets.usda.api_key,
                "query": food,
                "pageSize": 1
            }
        )
        response.raise_for_status()
        data = response.json()
        
        if data['foods']:
            nutrients = data['foods'][0]['foodNutrients']
            return {
                'carbs': next(n['value'] for n in nutrients if n['nutrientName'] == 'Carbohydrate, by difference'), 
                'protein': next(n['value'] for n in nutrients if n['nutrientName'] == 'Protein')
                }
        return None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None
# Initialize Firebase (if not already initialized)
# firebase_client_config = {
#     "apiKey": st.secrets["firebase"]["api_key"],
#     "authDomain": st.secrets["firebase"]["auth_domain"],
#     "projectId": st.secrets["firebase"]["project_id"],
#     "storageBucket": st.secrets["firebase"]["storage_bucket"],
#     "messagingSenderId": st.secrets["firebase"]["messaging_sender_id"],
#     "appId": st.secrets["firebase"]["app_id"],
#     "databaseURL": ""
# }

# firebase_client = pyrebase.initialize_app(firebase_client_config)
# auth_client = firebase_client.auth()

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate({
                "type": st.secrets.firebase.type,
                "project_id": st.secrets.firebase.project_id,
                "private_key_id": st.secrets.firebase.private_key_id,
                "private_key": st.secrets.firebase.private_key,
                "client_email": st.secrets.firebase.client_email,
                "client_id": st.secrets.firebase.client_id,
                "auth_uri": st.secrets.firebase.auth_uri,
                "token_uri": st.secrets.firebase.token_uri,
                "auth_provider_x509_cert_url": st.secrets.firebase.auth_provider_x509_cert_url,
                "client_x509_cert_url": st.secrets.firebase.client_x509_cert_url
            })
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase initialization error: {str(e)}")

db = firestore.client()
def log_medication_taken(med_name):
    db.collection("med_history").add({
        "user": st.session_state.user["first_name"],
        "medicine": med_name,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

def check_reminders():
    user_email = st.session_state.get("user", {}).get("email", None)  # Safe access
    if user_email:
        now = datetime.now().strftime("%H:%M")
        reminders = db.collection("reminders").where("User", "==", user_email).stream()
        for rem in reminders:
            rem_data = rem.to_dict()
            if rem_data.get('Time') == now:
                send_sms_reminder(f"Time to take {rem_data.get('Medicine')}", st.secrets.user.phone)

# Initialize scheduler once
if 'scheduler' not in st.session_state:
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_reminders, 'interval', minutes=1)
    scheduler.start()
    st.session_state.scheduler = scheduler


# SMS Reminder Function
def send_sms_reminder(message, phone_number):
    try:
        account_sid = st.secrets["twilio"]["account_sid"]
        auth_token = st.secrets["twilio"]["auth_token"]
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=message,
            from_=st.secrets["twilio"]["phone_number"],
            to=phone_number
        )
        st.success("Reminder sent successfully!")
    except Exception as e:
        st.error(f"Failed to send SMS: {e}")

# Page Configuration    
st.set_page_config(page_title="Diabetes Manager", layout="wide")

# Hide Streamlit branding with CSS
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
# Hide Streamlit branding & footer
hide_streamlit_style_ = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .st-emotion-cache-1v0mbdj {display: none;}  /* Hides 'Powered by Streamlit' */
    </style>
"""
st.markdown(hide_streamlit_style_, unsafe_allow_html=True)
# Authentication System
if 'user' not in st.session_state:
    st.session_state.user = None

#sign up and sign in functions
FIREBASE_API_KEY = st.secrets.firebase.api_key
def firebase_sign_up(email: str, password: str):
    url = (
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp"
        f"?key={FIREBASE_API_KEY}"
    )
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()   # ⇒ has `idToken`, `localId`, `refreshToken`, etc.

def firebase_sign_in(email: str, password: str):
    url = (
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={FIREBASE_API_KEY}"
    )
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()   # ⇒ has `idToken`, `localId`, `refreshToken`, etc.


# Show login/signup form if not authenticated
if not st.session_state.user:
    # Centered container
    with st.container():
        col1, col2, col3 = st.columns([1,3,1])
        with col2:
            st.markdown("<h1 style='text-align: center;'>Diabetes Manager Login</h1>", unsafe_allow_html=True)
            
            # Toggle between login/signup
            if 'auth_mode' not in st.session_state:
                st.session_state.auth_mode = 'login'
            
            auth_mode = st.radio("Choose action", ["Login", "Sign Up"], 
                                horizontal=True, label_visibility="collapsed")
            
            # Form container
            with st.form("auth_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                
                if auth_mode == "Sign Up":
                    first_name = st.text_input("First Name")
                    last_name = st.text_input("Last Name")  
                    confirm_password = st.text_input("Confirm Password", type="password")
                    PHONE_REGEX = r"^\+[1-9]\d{1,14}$"
                    phone = st.text_input("Phone Number (+1234567890)")
                    if not re.match(PHONE_REGEX, phone):
                        st.error("Please enter valid E.164 format: +[country code][number]")
                    utc_index = pytz.common_timezones.index("UTC")
                    timezone = st.selectbox("Timezone", pytz.common_timezones, index=utc_index)
                submitted = st.form_submit_button("Login" if auth_mode == "Login" else "Sign Up")
                
                if submitted:
                    try:
                        if auth_mode == "Sign Up":
                            if password != confirm_password:
                                st.error("Passwords do not match!")
                            else:
                                # Create user with client SDK
                                user = firebase_sign_up(email, password)
                                # Add user to Firestore
                                db.collection("users").document(user['localId']).set({
                                    "first_name": first_name,
                                    "last_name": last_name,
                                    "email": email,
                                    "phone": phone,
                                    "timezone": timezone,  # Default
                                    "created_at": firestore.SERVER_TIMESTAMP
                                
                                })
                                st.session_state.user = {
                                    "email": email,
                                    "first_name": first_name,
                                    "last_name": last_name
                                }
                                st.success(f"Welcome, {first_name}! 🎉")
                                st.rerun()
                        else:  # Login
                            user = firebase_sign_in(email, password)
                            user_doc = db.collection("users").document(user['localId']).get()
                            if user_doc.exists:
                                user_data = user_doc.to_dict()
                                st.session_state.user = {
                                    "email": email,
                                    "first_name": user_data.get("first_name", "User"),
                                    "last_name": user_data.get("last_name", "")
                                }
                                st.success(f"Welcome back, {st.session_state.user['first_name']}! 😊")
                                st.rerun()
                            else:
                                st.error("User details not found in the database.")
                    except Exception as e:
                        st.error(f"Authentication failed: {str(e)}")
    
    st.stop()

# Main app content (only shown after login)
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Main Menu", ["Home", "Chatbot", "Schedule", "Diet Plan", "Medication Reminders"])
if st.sidebar.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()
# Home Page
if menu == "Home":
    st.title(f"Welcome back, {st.session_state.user["first_name"]}!")
    today = datetime.today().strftime("%A, %B %d")
    st.markdown(f"**Today is {today}** - Here's your daily overview:")
    col1, col2, col3 = st.columns(3)
    col1.metric("Next Appointment", "Dr. Smith\n3:00 PM")
    col2.metric("Medications Due", "2 Remaining")
    col3.metric("Blood Sugar", "120 mg/dL")
#chatbot
elif menu == "Chatbot":
    st.title("Health Assistant Chatbot")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Gemini integration
    def get_gemini_response(prompt):
        try:
            import google.generativeai as genai
            
            # Configure Gemini
            genai.configure(api_key=st.secrets["google_gemini"]["api_key"])
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
            
            # Create diabetes-focused chat
            chat = model.start_chat(history=[])
            
            # Add system prompt and user question
            response = chat.send_message(f"""
            [System Prompt] You are a diabetes management assistant. Important:
            - Always state "I am not a doctor" before medical advice
            - Cite sources from ADA (American Diabetes Association)
            - Never suggest altering medication without doctor consultation
            [User Question] {prompt}
            """)
            
            return response.text
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return "I'm having trouble connecting. Please try again later."

    # Quick responses for common questions
    QUICK_RESPONSES = {
        "emergency": "🚨 If experiencing confusion, seizures, or loss of consciousness, seek immediate medical help!",
        "hi": "Hello! I'm your diabetes assistant. How can I help today?",
        "thanks": "You're welcome! Remember to always consult your healthcare team for personal advice."
    }

    EMERGENCY_KEYWORDS = {
    "emergency": "🚨 Seek immediate medical help for:",
    "hypo": "Hypoglycemia symptoms: Shaking, sweating. Treat with 15g fast-acting carbs",
    "hyper": "Hyperglycemia symptoms: Thirst, fatigue. Check blood sugar, contact doctor"
    }

    # Chat input
    if prompt := st.chat_input("Ask about diabetes"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Check for quick responses first
        lower_prompt = prompt.lower()
        quick_response = None
        for key in QUICK_RESPONSES:
            if key in lower_prompt:
                quick_response = QUICK_RESPONSES[key]
                break
        emergency_response = None
        for key in EMERGENCY_KEYWORDS:
            if key in lower_prompt:
                emergency_response = EMERGENCY_KEYWORDS[key]
                break
        # Get response from Gemini or quick responses
        with st.spinner("Analyzing your question..."):
            if quick_response:
                response = quick_response
            elif emergency_response:
                response = emergency_response
            else:
                response = get_gemini_response(prompt)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Rerun to show new messages
        st.rerun()

#schedule page
elif menu == "Schedule":
    st.title("Appointment Scheduler")
    
    # Add new appointment form
    with st.form("schedule_form"):
        doc_name = st.text_input("Doctor's Name")
        appt_date = st.date_input("Date")
        appt_time = st.time_input("Time")
        notes = st.text_area("Notes")
        
        if st.form_submit_button("Add Appointment"):
            try:
                # Combine date and time
                selected_datetime = datetime.combine(appt_date, appt_time)
                
                new_appt = {
                    "Doctor": doc_name,
                    "DateTime": selected_datetime,
                    "Notes": notes,
                    "User": st.session_state.user["first_name"]
                }
                db.collection("appointments").add(new_appt)
                st.success("Appointment added!")
            except Exception as e:
                st.error(f"Error saving appointment: {str(e)}")
            st.rerun()

    # Display and manage appointments
    st.subheader("Upcoming Appointments")
    
    try:
        appointments = db.collection("appointments") \
            .where("User", "==", st.session_state.user["first_name"]) \
            .order_by("DateTime") \
            .stream()

        appointment_list = []
        doc_ids = []
        for doc in appointments:
            data = doc.to_dict()
            # Convert Firestore timestamp to datetime
            data["DateTime"] = data["DateTime"].strftime("%Y-%m-%d %H:%M")
            appointment_list.append(data)
            doc_ids.append(doc.id)
            
        # Display table with delete options
        df = pd.DataFrame(appointment_list)
        if not df.empty:
            df["Delete"] = False  # Add checkbox column
            
            # Display editable dataframe
            edited_df = st.data_editor(
                df,
                column_config={
                    "Delete": st.column_config.CheckboxColumn(
                        "Delete?",
                        help="Select appointments to delete",
                        default=False,
                    )
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Delete selected appointments
            if st.button("Delete Selected Appointments"):
                if st.checkbox("Confirm deletion"):
                    selected_indices = edited_df[edited_df["Delete"]].index
                    for idx in selected_indices:
                        db.collection("appointments").document(doc_ids[idx]).delete()
                    st.success("Selected appointments deleted!")
                    st.rerun()
            
            # Delete all appointments button
            if st.button("⚠️ Delete ALL Appointments"):
                if st.checkbox("Confirm deletion"):
                    for doc_id in doc_ids:
                        db.collection("appointments").document(doc_id).delete()
                    st.success("All appointments deleted!")
                    st.rerun()
        else:
            st.info("No upcoming appointments found")
    except Exception as e:
        st.error(f"Error loading appointments: {str(e)}")
    ## Display Appointments
    #st.subheader("Upcoming Appointments")
    #appointments = db.collection("appointments").where("User", "==", st.session_state.user).stream()
    #appointment_list = [doc.to_dict() for doc in appointments]
    #st.table(pd.DataFrame(appointment_list))

# Diet Plan Page
elif menu == "Diet Plan":
    st.title("Diabetes-Friendly Diet Guide")
    food = st.text_input("Check food nutrition")
    if food:
        nutrition = get_nutrition_info(food)
        if nutrition:
            st.write(f"🍞 Carbs: {nutrition['carbs']}g | 🥩 Protein: {nutrition['protein']}g")
        else:
            st.warning("No data found - try exact terms like 'raw potato'")
    with st.expander("📌 Key Dietary Principles"):
        st.write("""
        - Focus on consistent carbohydrate intake
        - Choose high-fiber, whole grain options
        - Include lean proteins in every meal
        - Limit saturated and trans fats
        - Stay hydrated with sugar-free beverages
        """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🍳 Sample Meal Plan")
        with st.expander("Breakfast Options"):
            st.write("""
            - Oatmeal with nuts and berries
            - Whole grain toast with avocado and egg
            - Greek yogurt with chia seeds and apple slices
            """)
        
        with st.expander("Lunch Options"):
            st.write("""
            - Grilled chicken salad with olive oil dressing
            - Quinoa bowl with roasted vegetables
            - Turkey wrap with whole wheat tortilla
            """)
    
    with col2:
        st.subheader("🍴 Dinner Ideas")
        with st.expander("Main Dishes"):
            st.write("""
            - Baked salmon with steamed broccoli
            - Stir-fried tofu with brown rice
            - Lentil soup with whole grain bread
            """)
        
        with st.expander("Snacks"):
            st.write("""
            - Raw vegetables with hummus
            - Handful of unsalted nuts
            - Cottage cheese with cucumber
            - Hard-boiled eggs
            """)
    
    st.subheader("✅ Foods to Emphasize")
    st.write("""
    - Non-starchy vegetables (leafy greens, broccoli, peppers)
    - Berries and other low-glycemic fruits
    - Fish rich in omega-3 (salmon, mackerel)
    - Nuts and seeds
    - Whole grains (quinoa, brown rice, oats)
    """)
    
    st.subheader("🚫 Foods to Limit")
    st.write("""
    - Sugary drinks and sweets
    - Refined carbohydrates (white bread, pastries)
    - Processed meats
    - High-sodium snacks
    - Fried foods
    """)
    
    st.subheader("💧 Hydration Tips")
    st.write("""
    - Aim for 8-10 glasses of water daily
    - Infuse water with lemon/cucumber for flavor
    - Limit fruit juices and sugary drinks
    - Herbal teas are a great option
    """)

elif menu == "Medication Reminders":
    st.title("Medication Reminders")
    
    # Initialize session state variables
    if 'frequency' not in st.session_state:
        st.session_state.frequency = "Daily"
    if 'selected_days' not in st.session_state:
        st.session_state.selected_days = []

    # Frequency selection outside the form to force re-render
    def update_frequency():
        st.session_state.frequency = st.session_state.frequency_selector

    frequency = st.selectbox(
        "Frequency", 
        ["Daily", "Once", "Specific Days"], 
        key="frequency_selector",
        help="Choose how often you need reminders",
        on_change=update_frequency
    )

    # Add new reminder form
    with st.form("reminder_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            med_name = st.text_input("Medicine Name", help="Enter the name of your medication")
            
        with col2:
            # Time selection with 15-minute intervals
            time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
            selected_time = st.select_slider(
                "Select Reminder Time",
                options=time_options,
                value="09:00",
                format_func=lambda x: datetime.strptime(x, "%H:%M").strftime("%I:%M %p")
            )
        
        # Show days selection immediately when Specific Days is chosen
        if st.session_state.frequency == "Specific Days":
            days_options = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            st.session_state.selected_days = st.multiselect(
                "Select Days",
                options=days_options,
                default=["Monday", "Wednesday", "Friday"],
                help="Select days for reminders"
            )

        submit_button = st.form_submit_button("Set Reminder")
        
        if submit_button:
            # Validation checks
            if not med_name.strip():
                st.error("Medicine name cannot be empty!")
            elif not re.match(r"^[a-zA-Z0-9\- ]+$", med_name):
                st.error("Invalid medication name - only letters, numbers and hyphens allowed")
            elif st.session_state.frequency == "Specific Days" and not st.session_state.selected_days:
                st.error("Please select at least one day")
            else:
                new_reminder = {
                    "Medicine": med_name,
                    "Time": selected_time,
                    "Frequency": st.session_state.frequency if st.session_state.frequency != "Specific Days" else ", ".join(st.session_state.selected_days),
                    "User": st.session_state.user["first_name"]
                }
                
                db.collection("reminders").add(new_reminder)
                st.success("Reminder set!")
                st.rerun()

    # Display and delete reminders
    st.subheader("Active Reminders")
    reminders = db.collection("reminders") \
        .where("User", "==", st.session_state.user["first_name"]) \
        .order_by("Time", direction=firestore.Query.ASCENDING) \
        .stream()
    
    # Create list of reminders with document IDs
    reminder_list = []
    doc_ids = []
    for doc in reminders:
        data = doc.to_dict()
        # Format time for display, safely handle missing fields
        data["Time"] = datetime.strptime(data["Time"], "%H:%M").strftime("%I:%M %p") if "Time" in data else "N/A"
        reminder_list.append(data)
        doc_ids.append(doc.id)
    
    # Display table with delete options
    if reminder_list:
        df = pd.DataFrame(reminder_list)
        df["Delete"] = False
        
        edited_df = st.data_editor(
            df,
            column_config={
                "Delete": st.column_config.CheckboxColumn(
                    "Delete?",
                    help="Select reminders to delete",
                    default=False,
                )
            },
            hide_index=True,
            use_container_width=True,
            column_order=("Medicine", "Time", "Frequency", "Delete")
        )
        col1, col2, col3 = st.columns([1,1,2])
        with col1:
            if st.button("Delete Selected"):
                selected_indices = edited_df[edited_df["Delete"]].index
                for idx in selected_indices:
                    db.collection("reminders").document(doc_ids[idx]).delete()
                st.success("Selected reminders deleted!")
                st.rerun()

        with col2:
            if st.button("✅ Mark as Taken"):
                selected_indices = edited_df[edited_df["Delete"]].index  
                for idx in selected_indices:
                    log_medication_taken(edited_df.iloc[idx]["Medicine"])
                st.success(f"Logged {len(selected_indices)} medications taken!")
                st.balloons()
                st.rerun()
        with col3:
            if st.button("⚠️ Delete ALL Reminders", type="secondary"):
               for doc_id in doc_ids:
                    db.collection("reminders").document(doc_id).delete()
               st.success("All reminders deleted!")
               st.rerun()


    else:
        st.info("No active reminders found")
    
    st.subheader("Medication History")
    try:
        # Get ALL documents first before processing
        history_docs = db.collection("med_history") \
            .where("user", "==", st.session_state.user["first_name"]) \
            .order_by("timestamp", direction=firestore.Query.DESCENDING) \
            .stream()  # <-- ADD THIS TO GET ACTUAL DOCUMENTS
        
        history_data = []
        for doc in history_docs:  # Now iterating over document snapshots
            data = doc.to_dict()
            # Convert Firestore Timestamp to formatted string
            if 'timestamp' in data:
                data["timestamp"] = data["timestamp"].strftime("%Y-%m-%d %H:%M")
            else:
                data["timestamp"] = "N/A"
            history_data.append(data)
        
        if history_data:
            st.dataframe(
                pd.DataFrame(history_data),
                column_config={"timestamp": "Time Taken", "medicine": "Medication"},
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No medication history recorded yet")
            
    except Exception as e:
        st.error(f"Error loading history: {str(e)}")