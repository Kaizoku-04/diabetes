# 🩺 Diabetes Manager

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_svg)](https://diabetes-manager.streamlit.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**Diabetes Manager** is a comprehensive, AI-powered Streamlit application designed to empower individuals with diabetes to manage their health journey effectively. By integrating advanced tracking, automated reminders, and intelligent health assistance, this app serves as a digital companion for better glucose control and lifestyle management.

---

## 🚀 Key Features

### 🔐 Secure & Personalized Access
*   **Multi-Auth System:** Seamless Google Sign-In integration alongside traditional Firebase Email/Password authentication.
*   **User Profiles:** Tailored experience with timezone-aware reminders and personalized dashboards.

### 🤖 AI Health Assistant (Gemini)
*   **Intelligent Chatbot:** Powered by Google Gemini 1.5 Pro, offering reliable answers to diabetes-related queries.
*   **Medical Safety First:** Built-in safeguards that cite ADA sources and encourage professional medical consultation.
*   **Emergency Recognition:** Instant alerts for symptoms of hypoglycemia and hyperglycemia.

### 💊 Medication & Appointment Management
*   **Smart Reminders:** Automated medication alerts using `APScheduler`, with support for Daily, Once, or Specific Day frequencies.
*   **Compliance Tracking:** "Mark as Taken" functionality with historical logging to monitor adherence.
*   **Appointment Scheduler:** Keep track of doctor visits and medical notes.

### 🥗 Dietary Guidance
*   **Nutritional Insights:** Integrated with the **USDA FoodData Central API** to provide instant carb and protein information for thousands of foods.
*   **Dietary Principles:** Quick access to core diabetes management nutritional strategies.

---

## 🛠️ Technology Stack

*   **Frontend:** [Streamlit](https://streamlit.io/) (Python-based Web Framework)
*   **Backend & Database:** [Firebase](https://firebase.google.com/) (Firestore NoSQL Database)
*   **Authentication:** Firebase Auth & Google OAuth 2.0
*   **AI Engine:** [Google Gemini AI](https://ai.google.dev/) (gemini-1.5-pro-latest)
*   **Scheduling:** [APScheduler](https://apscheduler.readthedocs.io/)
*   **Data API:** [USDA FoodData Central API](https://fdc.nal.usda.gov/)

---

## 📦 Project Structure

```text
diabetes/
├── .streamlit/             # Streamlit configuration & secrets
├── auth.py                  # OAuth and Firebase Auth logic
├── data_layer.py            # Firestore & Scheduler initialization
├── app.py                   # Main application entry point
├── pages.py                 # UI components and page rendering
├── services.py              # External API integrations (Gemini, USDA)
├── requirements.txt         # Project dependencies
└── google_credentials.json  # Google OAuth client secrets
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/your-repo/diabetes-manager.git
cd diabetes
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration (Secrets)
Create a `.streamlit/secrets.toml` file and populate it with your credentials:

```toml
[firebase]
api_key = "YOUR_FIREBASE_API_KEY"
project_id = "YOUR_PROJECT_ID"
private_key = "YOUR_PRIVATE_KEY"
# ... other firebase service account fields

[google_auth]
redirect_uri = "http://localhost:8501"

[google_gemini]
api_key = "YOUR_GEMINI_API_KEY"

[usda]
api_key = "YOUR_USDA_API_KEY"
```

Also, ensure `google_credentials.json` is present in the root directory for Google OAuth.

### 5. Run the Application
```bash
streamlit run app.py
```

---

## ⚠️ Disclaimer

**I am not a doctor.** This application is designed for educational and tracking purposes only. Always consult with a qualified healthcare professional before making any changes to your medication, diet, or treatment plan. Information provided by the AI assistant should be verified against official medical sources like the American Diabetes Association (ADA).

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
