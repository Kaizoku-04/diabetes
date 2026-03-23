import re
from datetime import datetime

import pandas as pd
import streamlit as st
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from data_layer import log_medication_taken
from services import format_firestore_datetime, get_gemini_response, get_nutrition_info


def render_home_page():
    st.title(f"Welcome back, {st.session_state.user['first_name']}!")
    today = datetime.today().strftime("%A, %B %d")
    st.markdown(f"**Today is {today}** - Here's your daily overview:")
    col1, col2, col3 = st.columns(3)
    col1.metric("Next Appointment", "Dr. Smith\n3:00 PM")
    col2.metric("Medications Due", "2 Remaining")
    col3.metric("Blood Sugar", "120 mg/dL")


def render_chatbot_page():
    st.title("Health Assistant Chatbot")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    quick_responses = {
        "emergency": "🚨 If experiencing confusion, seizures, or loss of consciousness, seek immediate medical help!",
        "hi": "Hello! I'm your diabetes assistant. How can I help today?",
        "thanks": "You're welcome! Remember to always consult your healthcare team for personal advice.",
    }

    emergency_keywords = {
        "emergency": "🚨 Seek immediate medical help for:",
        "hypo": "Hypoglycemia symptoms: Shaking, sweating. Treat with 15g fast-acting carbs",
        "hyper": "Hyperglycemia symptoms: Thirst, fatigue. Check blood sugar, contact doctor",
    }

    if prompt := st.chat_input("Ask about diabetes"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        lower_prompt = prompt.lower()
        quick_response = next(
            (response for key, response in quick_responses.items() if key in lower_prompt),
            None,
        )
        emergency_response = next(
            (
                response
                for key, response in emergency_keywords.items()
                if key in lower_prompt
            ),
            None,
        )

        with st.spinner("Analyzing your question..."):
            if quick_response:
                response = quick_response
            elif emergency_response:
                response = emergency_response
            else:
                response = get_gemini_response(prompt)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


def render_schedule_page(db):
    st.title("Appointment Scheduler")

    with st.form("schedule_form"):
        doc_name = st.text_input("Doctor's Name")
        appt_date = st.date_input("Date")
        appt_time = st.time_input("Time")
        notes = st.text_area("Notes")

        if st.form_submit_button("Add Appointment"):
            try:
                selected_datetime = datetime.combine(appt_date, appt_time)
                db.collection("appointments").add(
                    {
                        "Doctor": doc_name,
                        "DateTime": selected_datetime,
                        "Notes": notes,
                        "User": st.session_state.user["first_name"],
                    }
                )
                st.success("Appointment added!")
            except Exception as e:
                st.error(f"Error saving appointment: {str(e)}")
            st.rerun()

    st.subheader("Upcoming Appointments")
    try:
        appointments = (
            db.collection("appointments")
            .where(filter=FieldFilter("User", "==", st.session_state.user["first_name"]))
            .order_by("DateTime")
            .stream()
        )

        appointment_list = []
        doc_ids = []
        for doc in appointments:
            data = doc.to_dict()
            data["DateTime"] = format_firestore_datetime(data["DateTime"])
            appointment_list.append(data)
            doc_ids.append(doc.id)

        df = pd.DataFrame(appointment_list)
        if df.empty:
            st.info("No upcoming appointments found")
            return

        df["Delete"] = False
        edited_df = st.data_editor(
            df,
            column_config={
                "Delete": st.column_config.CheckboxColumn(
                    "Delete?", help="Select appointments to delete", default=False
                )
            },
            hide_index=True,
            width="stretch",
        )

        if st.button("Delete Selected Appointments") and st.checkbox("Confirm deletion"):
            selected_indices = edited_df[edited_df["Delete"]].index
            for idx in selected_indices:
                db.collection("appointments").document(doc_ids[idx]).delete()
            st.success("Selected appointments deleted!")
            st.rerun()

        if st.button("⚠️ Delete ALL Appointments") and st.checkbox("Confirm deletion"):
            for doc_id in doc_ids:
                db.collection("appointments").document(doc_id).delete()
            st.success("All appointments deleted!")
            st.rerun()
    except Exception as e:
        st.error(f"Error loading appointments: {str(e)}")


def render_diet_page():
    st.title("Diabetes-Friendly Diet Guide")
    food = st.text_input("Check food nutrition")
    if food:
        nutrition = get_nutrition_info(food)
        if nutrition:
            st.write(
                f"🍞 Carbs: {nutrition['carbs']}g | 🥩 Protein: {nutrition['protein']}g"
            )
        else:
            st.warning("No data found - try exact terms like 'raw potato'")

    with st.expander("📌 Key Dietary Principles"):
        st.write(
            """
        - Focus on consistent carbohydrate intake
        - Choose high-fiber, whole grain options
        - Include lean proteins in every meal
        - Limit saturated and trans fats
        - Stay hydrated with sugar-free beverages
        """
        )


def render_medication_page(db):
    st.title("Medication Reminders")

    if "frequency" not in st.session_state:
        st.session_state.frequency = "Daily"
    if "selected_days" not in st.session_state:
        st.session_state.selected_days = []

    def update_frequency():
        st.session_state.frequency = st.session_state.frequency_selector

    st.selectbox(
        "Frequency",
        ["Daily", "Once", "Specific Days"],
        key="frequency_selector",
        help="Choose how often you need reminders",
        on_change=update_frequency,
    )

    with st.form("reminder_form"):
        col1, col2 = st.columns(2)
        with col1:
            med_name = st.text_input(
                "Medicine Name", help="Enter the name of your medication"
            )

        with col2:
            time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
            selected_time = st.select_slider(
                "Select Reminder Time",
                options=time_options,
                value="09:00",
                format_func=lambda x: datetime.strptime(x, "%H:%M").strftime("%I:%M %p"),
            )

        if st.session_state.frequency == "Specific Days":
            days_options = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            st.session_state.selected_days = st.multiselect(
                "Select Days",
                options=days_options,
                default=["Monday", "Wednesday", "Friday"],
                help="Select days for reminders",
            )

        if st.form_submit_button("Set Reminder"):
            if not med_name.strip():
                st.error("Medicine name cannot be empty!")
            elif not re.match(r"^[a-zA-Z0-9\- ]+$", med_name):
                st.error(
                    "Invalid medication name - only letters, numbers and hyphens allowed"
                )
            elif (
                st.session_state.frequency == "Specific Days"
                and not st.session_state.selected_days
            ):
                st.error("Please select at least one day")
            else:
                db.collection("reminders").add(
                    {
                        "Medicine": med_name,
                        "Time": selected_time,
                        "Frequency": (
                            st.session_state.frequency
                            if st.session_state.frequency != "Specific Days"
                            else ", ".join(st.session_state.selected_days)
                        ),
                        "User": st.session_state.user["first_name"],
                    }
                )
                st.success("Reminder set!")
                st.rerun()

    st.subheader("Active Reminders")
    reminders = (
        db.collection("reminders")
        .where(filter=FieldFilter("User", "==", st.session_state.user["first_name"]))
        .order_by("Time", direction=firestore.Query.ASCENDING)
        .stream()
    )

    reminder_list = []
    doc_ids = []
    for doc in reminders:
        data = doc.to_dict()
        data["Time"] = format_firestore_datetime(data.get("Time"))
        reminder_list.append(data)
        doc_ids.append(doc.id)

    if reminder_list:
        df = pd.DataFrame(reminder_list)
        df["Delete"] = False
        edited_df = st.data_editor(
            df,
            column_config={
                "Delete": st.column_config.CheckboxColumn(
                    "Delete?", help="Select reminders to delete", default=False
                )
            },
            hide_index=True,
            width="stretch",
            column_order=("Medicine", "Time", "Frequency", "Delete"),
        )

        col1, col2, col3 = st.columns([1, 1, 2])
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
                    log_medication_taken(db, edited_df.iloc[idx]["Medicine"])
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
        history_docs = (
            db.collection("med_history")
            .where(filter=FieldFilter("user", "==", st.session_state.user["first_name"]))
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .stream()
        )

        history_data = []
        for doc in history_docs:
            data = doc.to_dict()
            data["timestamp"] = format_firestore_datetime(data.get("timestamp"))
            history_data.append(data)

        if history_data:
            st.dataframe(
                pd.DataFrame(history_data),
                column_config={"timestamp": "Time Taken", "medicine": "Medication"},
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No medication history recorded yet")
    except Exception as e:
        st.error(f"Error loading history: {str(e)}")
