import streamlit as st
import pandas as pd
from datetime import datetime, time
from twilio.rest import Client
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Initialize Firebase (if not already initialized)
if not firebase_admin._apps:
    firebase_cred = {
        "type": st.secrets.firebase.type,
        "project_id": st.secrets.firebase.project_id,
        "private_key_id": st.secrets.firebase.private_key_id,
        "private_key": st.secrets.firebase.private_key.replace('\\n', '\n'),
        "client_email": st.secrets.firebase.client_email,
        "client_id": st.secrets.firebase.client_id,
        "auth_uri": st.secrets.firebase.auth_uri,
        "token_uri": st.secrets.firebase.token_uri,
        "auth_provider_x509_cert_url": st.secrets.firebase.auth_provider_x509_cert_url,
        "client_x509_cert_url": st.secrets.firebase.client_x509_cert_url
    }
    cred = credentials.Certificate("firebase_cred")  # Download from Firebase Console
    firebase_admin.initialize_app(cred)

db = firestore.client()

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

# Authentication System
if 'user' not in st.session_state:
    st.session_state.user = None

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
                    confirm_password = st.text_input("Confirm Password", type="password")
                
                submitted = st.form_submit_button("Login" if auth_mode == "Login" else "Sign Up")
                
                if submitted:
                    try:
                        if auth_mode == "Sign Up":
                            if password != confirm_password:
                                st.error("Passwords do not match!")
                            else:
                                # Create Firebase user
                                user = auth.create_user(
                                    email=email,
                                    password=password
                                )
                                st.session_state.user = email
                                st.rerun()
                                
                        else:  # Login
                            # Verify credentials (this is simplified - use Firebase client SDK for full auth)
                            user = auth.get_user_by_email(email)
                            # In production, use: auth.sign_in_with_email_and_password(email, password)
                            st.session_state.user = email
                            st.rerun()
                            
                    except auth.EmailAlreadyExistsError:
                        st.error("Email already registered!")
                    except auth.UserNotFoundError:
                        st.error("User not found!")
                    except ValueError as e:
                        st.error(f"Invalid input: {str(e)}")
                    except Exception as e:
                        st.error(f"Authentication failed: {str(e)}")
    
    st.stop()

# Main app content (only shown after login)
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Main Menu", ["Home", "Chatbot", "Schedule", "Diet Plan", "Medication Reminders"])

# Home Page
if menu == "Home":
    st.title("Welcome to Diabetes Manager")
    st.image("https://www.lanermc.org/hs-fs/hubfs/diabetes.jpeg?width=300&name=diabetes.jpeg", width=300)
    st.write("""
    Manage your diabetes with these features:
    - Chat with our health assistant
    - Schedule appointments
    - Get diet and nutrition guidance
    - Set medication reminders
    """)

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
                [System Prompt] You are a diabetes management assistant. Provide:
                - Evidence-based medical information
                - Nutrition advice for diabetics
                - Exercise recommendations
                - Blood sugar monitoring tips
                - Always remind users to consult their doctor
                - Keep responses under 300 words
                
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
        
        # Get response from Gemini or quick responses
        with st.spinner("Analyzing your question..."):
            if quick_response:
                response = quick_response
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
            new_appt = {
                "Doctor": doc_name,
                "Date": appt_date.strftime("%Y-%m-%d"),
                "Time": appt_time.strftime("%H:%M"),
                "Notes": notes,
                "User": st.session_state.user
            }
            db.collection("appointments").add(new_appt)
            st.success("Appointment added!")
            st.rerun()

    # Display and manage appointments
    st.subheader("Upcoming Appointments")
    appointments = db.collection("appointments").where("User", "==", st.session_state.user).stream()
    
    # Create list of appointments with document IDs
    appointment_list = []
    doc_ids = []
    for doc in appointments:
        appointment_list.append(doc.to_dict())
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
            selected_indices = edited_df[edited_df["Delete"]].index
            for idx in selected_indices:
                db.collection("appointments").document(doc_ids[idx]).delete()
            st.success("Selected appointments deleted!")
            st.rerun()
        
        # Delete all appointments button
        if st.button("⚠️ Delete ALL Appointments"):
            for doc_id in doc_ids:
                db.collection("appointments").document(doc_id).delete()
            st.success("All appointments deleted!")
            st.rerun()
    else:
        st.info("No upcoming appointments found")
    
    ## Display Appointments
    #st.subheader("Upcoming Appointments")
    #appointments = db.collection("appointments").where("User", "==", st.session_state.user).stream()
    #appointment_list = [doc.to_dict() for doc in appointments]
    #st.table(pd.DataFrame(appointment_list))

# Diet Plan Page
elif menu == "Diet Plan":
    st.title("Diabetes-Friendly Diet Guide")
    
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
            if st.session_state.frequency == "Specific Days" and not st.session_state.selected_days:
                st.error("Please select at least one day")
            else:
                new_reminder = {
                    "Medicine": med_name,
                    "Time": selected_time,
                    "Frequency": st.session_state.frequency if st.session_state.frequency != "Specific Days" else ", ".join(st.session_state.selected_days),
                    "User": st.session_state.user
                }
                
                db.collection("reminders").add(new_reminder)
                st.success("Reminder set!")
                st.rerun()

    # ... (rest of the display and delete code remains the same)

    # ... (rest of the code remains the same for displaying and deleting reminders)

    # Display and delete reminders
    st.subheader("Active Reminders")
    reminders = db.collection("reminders").where("User", "==", st.session_state.user).stream()
    
    # Create list of reminders with document IDs
    reminder_list = []
    doc_ids = []
    for doc in reminders:
        data = doc.to_dict()
        # Format time for display
        data["Time"] = datetime.strptime(data["Time"], "%H:%M").strftime("%I:%M %p")
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
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Delete Selected"):
                selected_indices = edited_df[edited_df["Delete"]].index
                for idx in selected_indices:
                    db.collection("reminders").document(doc_ids[idx]).delete()
                st.success("Selected reminders deleted!")
                st.rerun()
        
        with col2:
            if st.button("⚠️ Delete ALL Reminders", type="secondary"):
                for doc_id in doc_ids:
                    db.collection("reminders").document(doc_id).delete()
                st.success("All reminders deleted!")
                st.rerun()
    else:
        st.info("No active reminders found")