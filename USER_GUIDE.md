# 📦 Fullventory AI | User Guide

Welcome to the **Fullventory AI** Command Center. This guide will help you set up your inventory, understand AI predictions, and automate your supply chain.

---

## 🚀 1. Getting Started
1. **Initialize Session:** Log in at `/login` using your Administrator ID.
2. **Dashboard Overview:** Your main screen displays a "Bento-Grid" layout showing:
   - **Global Inventory Health:** Real-time stock counts.
   - **AI Forecasts:** Predicted dates when items will run out.
   - **Recent Activity:** Logs of automated purchase orders.

---

## 🧠 2. Understanding AI Predictions
Fullventory AI uses a **Temporal Random Forest** engine to calculate your stock "runway."
- **Days-to-Zero (DTZ):** This is the most important metric. It tells you exactly how many days of stock you have left based on sales trends.
- **Status Indicators:**
  - 🟢 **Healthy:** Plenty of stock based on current demand.
  - 🟡 **Warning:** Stockout predicted within 10 days.
  - 🔴 **Critical:** Stockout predicted within 3 days. Action required.

---

## ⚡ 3. Autonomous Fulfillment
The system is designed to "close the loop" between data and action.
- **Auto-Drafting:** When an item hits the "Warning" threshold, the AI prepares a professional Purchase Order (PO).
- **One-Click Ordering:** Click the **"Order Now"** button next to a critical item. This triggers the **Resend API** to instantly email your pre-assigned supplier with the required quantity.

---

## 🛠️ 4. Managing Your Inventory
- **Add Items:** Use the "Sync" feature to pull new products from your connected database.
- **Update Stock:** Manual audits can be performed to overwrite AI counts if physical stock differs.
- **Supplier Settings:** Ensure each SKU has an assigned supplier email in the **Settings** tab for the autonomous loop to function.

---

## 🆘 Support
If the AI Engine reports a "Sync Error," please contact your Technical Administrator or check the **API Reference** for connectivity issues.

---
*"Fullventory AI: Ensuring your best-sellers never leave the shelf."*