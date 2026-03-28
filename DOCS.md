# 📚 Fullventory AI | Full System Documentation

This document provides a deep dive into the architecture, machine learning pipeline, and deployment strategy of the Fullventory AI ecosystem.

---

## 🏗️ 1. System Architecture
Fullventory AI is built on a **Cloud-Native SaaS** model:
- **Frontend:** Responsive, glassmorphic UI built with HTML5, Tailwind CSS, and Vanilla JS for zero-latency interactions.
- **Backend:** Flask (Python) micro-framework handling routing, authentication, and API logic.
- **Database:** PostgreSQL (Supabase) for ACID-compliant inventory transactions and historical sales data.
- **AI Engine:** Scikit-learn based regressor running in a background thread for real-time forecasting.

---

## 🧠 2. The Predictive Engine (ML Pipeline)
The core of the platform is a **Temporal Random Forest Regression** model.
- **Feature Engineering:** The model tracks `Sales_Velocity`, `Days_Since_Restock`, and `Seasonal_Weight`.
- **The Metric:** It outputs **Days-to-Zero (DTZ)**, a forecast of exactly when an SKU will hit zero stock.
- **Training:** The model is retrained periodically via the `/api/sync` endpoint to adapt to changing consumer behavior.



---

## 📩 3. Autonomous Fulfillment Loop
The system utilizes the **Resend API** to automate the supply chain:
1. **Threshold Check:** Every 6 hours, the engine checks for items with a DTZ < 7 days.
2. **Trigger:** If an item is critical, the backend fetches the assigned `supplier_email`.
3. **Transmission:** A structured HTML Purchase Order is sent via Resend, including the SKU and calculated "Reorder Quantity."

---

## 🚀 4. Deployment Guide
To host this system on **Render** or a similar VPS:
1. **Environment Variables:** Set up `RESEND_API_KEY`, `SUPABASE_URL`, and `SECRET_KEY`.
2. **Dependencies:** Install via `pip install -r requirements.txt`.
3. **Persistence:** Ensure the "Self-Ping" hack is active to prevent the ML engine from idling on free-tier hosting.

---

## 🔒 5. Security Protocols
- **Session Security:** All dashboard routes are protected by `@login_required` decorators.
- **Data Integrity:** Supabase Row-Level Security (RLS) ensures store managers only see their specific inventory.
- **Secret Management:** No API keys are hardcoded; all credentials are piped via `.env` files.

---
*Created by Rajat Sharma | Fullventory AI Foundation*