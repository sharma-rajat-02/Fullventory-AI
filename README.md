# 🚀 Fullventory AI 
### *Strategic Inventory Intelligence & Autonomous Supply Chain Engine*

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Supabase](https://img.shields.io/badge/Database-Supabase-green.svg)](https://supabase.com/)
[![AI-ML](https://img.shields.io/badge/AI--ML-Scikit--Learn-orange.svg)](https://scikit-learn.org/)

**Fullventory AI** is a cloud-native, machine-learning-driven inventory management system designed for 2026 enterprise standards. It moves beyond passive tracking by using predictive analytics to forecast stockouts and automate the fulfillment cycle.

---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/rajatsharma/fullventory-ai.git](https://github.com/rajatsharma/fullventory-ai.git)
cd fullventory-ai
```
### 2. Install Dependencies
Ensure you have Python 3.13+ installed, then run:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a .env file in the root directory and add your credentials:
```bash
DATABASE_URL=postgresql://postgres.[REF]:[YOUR_PASSWORD]@[aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres](https://aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres)
SECRET_KEY=xxxxxxxxxxxxxxxx
RESEND_API_KEY=re_xxxxxxxx
MY_DOMAIN=[personal domain]
RECEIVER_EMAIL=admin@example.com
```
### 4. Run the Application
```bash
python app.py
```

### 💎 Core Value Proposition
### 🛠️ Key Features
* **Feature One:** Description here.
* **Feature Two:** Description here.
* **Feature Three:** Description here.

### 📦 Tech Stack
- **Backend:** Flask
- **Database:** Supabase
- **AI:** Scikit-Learn
Predictive Velocity: Uses Random Forest Regression to analyze historical sales patterns and predict future demand.

Autonomous Fulfillment: Triggers automated supplier communication via the Resend API when stock hits critical thresholds.

Cloud Infrastructure: Leverages Supabase (PostgreSQL) with Transaction Pooling for real-time data consistency.

🚀 Key Features
🏥 Dynamic Health Matrix
A real-time dashboard that categorizes items by "Days Left" rather than just raw quantity. Color-coded status alerts (Critical vs. Healthy) allow warehouse managers to prioritize high-velocity items.

🧠 AI Sync Engine
A specialized batch-processing engine that trains locally on extensive CSV datasets and pushes optimized forecasts to the Supabase cloud in unified transactions.

📦 Smart Fulfillment History
A comprehensive audit trail tracking Store IDs, Item IDs, and Unit counts. The system allows for manual stock reconciliation via "Mark Received" actions that sync instantly with cloud inventory.

🛠️ Tech Stack
Intelligence: Scikit-Learn (Random Forest), Pandas, NumPy.

Backend: Flask (Python 3.13), SQLAlchemy (ORM).

Database: Supabase (PostgreSQL) with PgBouncer Pooling.

Email: Resend API.

Reports: FPDF.

👨‍💻 Author
Rajat Sharma B.Tech in Computer Science (AI & ML), VIT Bhopal University Specializing in Predictive Analytics and Scalable Cloud Architectures.
