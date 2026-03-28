# 🛠️ Fullventory AI | API Reference

This document defines the endpoints for the Fullventory AI predictive engine.

## 1. Authentication
- **Login:** `POST /api/login` (Payload: `{"username": "...", "password": "..."}`)
- **Logout:** `GET /api/logout` (Clears session and redirects)

## 2. Inventory & AI Engine
- **Get Inventory:** `GET /api/inventory`
  - Returns a list of all items, stock levels, and AI-calculated "Days-to-Zero" (DTZ).
- **Trigger Prediction:** `POST /api/predict`
  - Payload: `{"item_id": 101}`
  - Runs the Random Forest model to refresh forecasts for a specific item.

## 3. Autonomous Fulfillment
- **Send Purchase Order:** `POST /api/order`
  - Payload: `{"supplier_id": 1, "item_name": "...", "quantity": 50}`
  - Triggers the Resend API to email a PO to the supplier.
- **System Sync:** `GET /api/sync`
  - Refreshes data between Supabase and the local ML model.

## 4. Response Codes
- `200`: Success
- `401`: Unauthorized (Login required)
- `500`: Server/ML Engine Error