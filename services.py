from datetime import datetime

import requests
import streamlit as st
from twilio.rest import Client


def get_nutrition_info(food: str):
    try:
        response = requests.get(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={
                "api_key": st.secrets.usda.api_key,
                "query": food,
                "pageSize": 1,
            },
        )
        response.raise_for_status()
        data = response.json()

        if data["foods"]:
            nutrients = data["foods"][0]["foodNutrients"]
            return {
                "carbs": next(
                    n["value"]
                    for n in nutrients
                    if n["nutrientName"] == "Carbohydrate, by difference"
                ),
                "protein": next(
                    n["value"] for n in nutrients if n["nutrientName"] == "Protein"
                ),
            }
        return None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None


def send_sms_reminder(message: str, phone_number: str):
    try:
        account_sid = st.secrets["twilio"]["account_sid"]
        auth_token = st.secrets["twilio"]["auth_token"]
        client = Client(account_sid, auth_token)

        client.messages.create(
            body=message,
            from_=st.secrets["twilio"]["phone_number"],
            to=phone_number,
        )
        st.success("Reminder sent successfully!")
    except Exception as e:
        st.error(f"Failed to send SMS: {e}")


def get_gemini_response(prompt: str) -> str:
    try:
        import google.generativeai as genai

        genai.configure(api_key=st.secrets["google_gemini"]["api_key"])
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        chat = model.start_chat(history=[])
        response = chat.send_message(
            f"""
            [System Prompt] You are a diabetes management assistant. Important:
            - Always state \"I am not a doctor\" before medical advice
            - Cite sources from ADA (American Diabetes Association)
            - Never suggest altering medication without doctor consultation
            [User Question] {prompt}
            """
        )
        return response.text
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return "I'm having trouble connecting. Please try again later."


def format_firestore_datetime(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%H:%M").strftime("%I:%M %p")
        except ValueError:
            return value
    return "N/A"
