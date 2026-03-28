import os
import math
import random
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import resend 
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, session, jsonify, request, send_file, flash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.ensemble import RandomForestRegressor
from fpdf import FPDF
from sqlalchemy import create_engine

# --- INITIALIZE ENVIRONMENT ---
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- APP SETUP ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "rajat_startup_2026")
CORS(app)

# --- DATABASE CONFIGURATION ---
# 1. Prioritize Render/Environment Variable
db_url = os.getenv("DATABASE_URL")

# 2. Fallback to Supabase Pooler String for Local Development
if not db_url:
    # IMPORTANT: Replace [YOUR-PASSWORD] with your actual or encoded password
    db_url = "postgresql://postgres.juotdcttdlxyaogvqloy:[YOUR-PASSWORD]@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

# 3. FIX: Convert legacy 'postgres://' (Render) to 'postgresql://' (SQLAlchemy)
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# 4. Apply Configuration
app.config.update(
    SQLALCHEMY_DATABASE_URI=db_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_pre_ping": True,    # Checks connection health before every query
        "pool_recycle": 300,      # Prevents "Idle Timeout" from Supabase Pooler
        "pool_size": 10,          # Standard startup capacity
        "max_overflow": 20        # Allows for traffic spikes during your demo
    }
)

# 5. Initialize Database Object
db = SQLAlchemy(app)
# --- MODELS ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer, nullable=False)
    current_stock = db.Column(db.Integer, default=500)
    last_forecast = db.Column(db.Float)
    status = db.Column(db.String(20), default="HEALTHY")
    base_stock_date = db.Column(db.DateTime, default=datetime(2026, 3, 15))

class StoreSupplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)

class OrderHistory(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, default=500)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="PENDING")

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    threshold_days = db.Column(db.Integer, default=10)
    reorder_amount = db.Column(db.Integer, default=500)

# Initialize Supabase Tables
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password=generate_password_hash('admin123')))
    db.session.commit()

# --- API ROUTES ---

@app.route('/api/inventory')
def get_inventory():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    
    # ADDED: .order_by(Product.item_id.asc())
    products = Product.query.order_by(Product.item_id.asc()).all()
    
    config = Settings.query.first()
    thresh = config.threshold_days if config else 10
    current_time = datetime(2026, 3, 15) 
    data = []
    
    for p in products:
        forecast = p.last_forecast or 1.0
        days_passed = (current_time - p.base_stock_date).days
        actual_units = max(0, p.current_stock - math.floor(forecast * days_passed))
        days_left = math.floor(actual_units / forecast)
        out_date = (current_time + timedelta(days=days_left)).strftime("%b %d, %Y")
        target_inv = (forecast * thresh * 2) * 1.2
        suggested = math.ceil(max(0, target_inv - actual_units))
        
        data.append({
            "store": p.store_id, "item": p.item_id, 
            "units_left": actual_units, "days_left": days_left, 
            "out_date": out_date, "suggested_reorder": suggested,
            "status": "CRITICAL" if days_left <= thresh else "HEALTHY"
        })
    return jsonify({"status": "success", "data": data})

@app.route('/api/inventory/adjust', methods=['POST'])
def adjust_stock():
    data = request.json
    p = Product.query.filter_by(store_id=data['store'], item_id=data['item']).first()
    if p:
        p.current_stock = int(data['new_qty'])
        p.base_stock_date = datetime(2026, 3, 15)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route('/api/trends/<int:sid>/<int:iid>')
def get_trends(sid, iid):
    # Search BigData efficiently
    try:
        df = pd.read_csv(BASE_DIR / "train.csv", nrows=200000, usecols=['date', 'store', 'item', 'sales'])
        df.columns = df.columns.str.lower()
        subset = df[(df['store'] == sid) & (df['item'] == iid)].tail(15)
        if subset.empty: return jsonify({"status": "error", "message": "No history found"})
        return jsonify({
            "status": "success", 
            "labels": pd.to_datetime(subset['date']).dt.strftime('%m/%d').tolist(), 
            "values": subset['sales'].tolist()
        })
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/report')
def download_report():
    sid = request.args.get('store')
    products = Product.query.filter_by(store_id=int(sid)).all() if sid and sid != 'all' else Product.query.all()
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(200, 10, "Fullventory AI Report", ln=True, align='C'); pdf.ln(10)
    pdf.set_font("Arial", 'B', 10); pdf.cell(30, 10, "Store", 1); pdf.cell(30, 10, "Item", 1); pdf.cell(40, 10, "Stock", 1); pdf.cell(40, 10, "Status", 1); pdf.ln()
    for p in products:
        pdf.cell(30, 10, str(p.store_id), 1); pdf.cell(30, 10, str(p.item_id), 1); pdf.cell(40, 10, str(p.current_stock), 1); pdf.cell(40, 10, p.status, 1); pdf.ln()
    path = BASE_DIR / "report.pdf"; pdf.output(str(path))
    return send_file(str(path), as_attachment=True)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    config = Settings.query.first() or Settings()
    if request.method == 'POST':
        data = request.json
        config.threshold_days, config.reorder_amount = int(data['threshold_days']), int(data['reorder_amount'])
        db.session.add(config); db.session.commit()
        run_ai_engine(config.threshold_days)
        return jsonify({"status": "success"})
    return jsonify({"status": "success", "threshold_days": config.threshold_days, "reorder_amount": config.reorder_amount})

def run_ai_engine(thresh):
    TRAIN_PATH = BASE_DIR / "train.csv"
    if not TRAIN_PATH.exists(): return
    
    # 1. Faster Scan: Reduced to 100k rows for snappy demo performance
    df = pd.read_csv(TRAIN_PATH, nrows=100000, skiprows=lambda i: i > 0 and i % 5 != 0)
    df.columns = df.columns.str.lower()
    df['date'] = pd.to_datetime(df['date'])
    df['day'] = df['date'].dt.day; df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year; df['dayofweek'] = df['date'].dt.dayofweek
    
    # 2. Train Model
    model = RandomForestRegressor(n_estimators=10, max_depth=8, random_state=42)
    model.fit(df[['store', 'item', 'day', 'month', 'year', 'dayofweek']], df['sales'])
    
    summary = df.groupby(['store', 'item'])['sales'].mean().reset_index()
    
    # 3. BATCH PROCESSING LOGIC
    # We collect all updates first and commit them ONCE at the end
    try:
        for _, row in summary.iterrows():
            sid, iid = int(row['store']), int(row['item'])
            
            # Use a slightly faster query for the pooler
            p = db.session.query(Product).filter_by(item_id=iid, store_id=sid).first()
            
            if not p:
                p = Product(item_id=iid, store_id=sid, current_stock=random.randint(400, 900))
                db.session.add(p)

            p.last_forecast = float(row['sales'])
            p.base_stock_date = datetime(2026, 3, 15)

        # THE MAGIC STEP: One single trip to Supabase for all items
        db.session.commit()
        print(f"🚀 Batch Sync Complete: Updated {len(summary)} items.")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Batch Sync Failed: {e}")

# --- OTHER ROUTES (Order, Receive, Suppliers, Auth) ---
@app.route('/api/order', methods=['POST'])
def place_order():
    if 'user_id' not in session: 
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    # 1. Force reload variables inside the function to avoid NameErrors
    domain = os.getenv("MY_DOMAIN", "fullventoryai.me")
    api_key = os.getenv("RESEND_API_KEY")
    admin_email = os.getenv("RECEIVER_EMAIL")
    
    data = request.json
    sid = data.get('store_id')
    iid = data.get('item_id')
    qty = data.get('quantity')

    try:
        # 2. Re-verify API Key assignment
        resend.api_key = api_key
        
        # 3. Lookup Supplier
        supplier = StoreSupplier.query.filter_by(store_id=sid).first()
        target_email = supplier.email if supplier else admin_email

        print(f"📧 DEBUG: Sending to {target_email} using domain {domain}")

        # 4. Send Email
        params = {
            "from": f"Fullventory AI <orders@{domain}>",
            "to": [target_email],
            "subject": f"📦 Restock Order: Item #{iid}",
            "html": f"<strong>Order for Store {sid}:</strong> Item #{iid} - Qty: {qty}"
        }
        
        email_response = resend.Emails.send(params)
        print(f"✅ Resend Success: {email_response}")

        # 5. Log to Supabase
        new_order = OrderHistory(item_id=iid, store_id=sid, quantity=qty, status='PENDING')
        db.session.add(new_order)
        db.session.commit()
        
        return jsonify({"status": "success"})

    except Exception as e:
        # This will tell us EXACTLY what is wrong in the console
        print(f"❌ EMAIL CRITICAL ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/receive', methods=['POST'])
def receive_order():
    order = OrderHistory.query.get(request.json.get('order_id'))
    if order:
        p = Product.query.filter_by(item_id=order.item_id, store_id=order.store_id).first()
        if p: 
            p.current_stock += order.quantity
            p.base_stock_date = datetime(2026, 3, 15)
        order.status = "RECEIVED"; db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/suppliers', methods=['GET', 'POST'])
def handle_suppliers():
    if request.method == 'POST':
        data = request.json
        s = StoreSupplier.query.filter_by(store_id=data['store_id']).first() or StoreSupplier(store_id=data['store_id'])
        s.email = data['email']; db.session.add(s); db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "success", "data": [{"store_id": s.store_id, "email": s.email} for s in StoreSupplier.query.all()]})

@app.route('/api/history')
def get_history():
    # Fetching latest 10 orders from Supabase
    history = OrderHistory.query.order_by(OrderHistory.order_date.desc()).limit(10).all()
    return jsonify({
        "status": "success", 
        "data": [
            {
                "id": h.id, 
                "store": h.store_id,  # Added this line
                "item": h.item_id, 
                "qty": h.quantity, 
                "date": h.order_date.strftime("%m-%d %H:%M"), 
                "status": h.status
            } for h in history
        ]
    })

@app.route('/')
def landing():
    return render_template('landing.html') # Public Landing Page
@app.route('/login')
def login_page():
    return render_template('login.html') # The Login screen
@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('index.html') # The Internal Tool we built
    return redirect(url_for('login_page'))
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json; user = User.query.filter_by(username=data.get('username')).first()
    if user and check_password_hash(user.password, data.get('password')):
        session['user_id'] = user.id; return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401
@app.route('/api/logout')
def logout(): session.pop('user_id', None); return redirect(url_for('landing'))
resend.api_key = os.getenv('RESEND_API_KEY')
@app.route('/ping')
def ping():
    return "PONG", 200
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    # If the user is SUBMITTING the form
    if request.method == 'POST':
        fname = request.form.get('first_name')
        lname = request.form.get('last_name')
        client_company = request.form.get('company')
        client_email = request.form.get('visitor_email')
        subject_type = request.form.get('inquiry_type')
        details = request.form.get('business_details')

        try:
            # Send the structured email using Resend
            resend.Emails.send({
                "from": "Fullventory AI <onboarding@resend.dev>", 
                "to": "fullventoryai@gmail.com",
                "reply_to": client_email,
                "subject": f"🚨 Inquiry from {client_company}: {subject_type} - {fname} {lname}",
                "html": f"""
                    <div style="font-family: sans-serif; max-width: 600px; border: 1px solid #eee; padding: 20px; border-radius: 15px;">
                        <h2 style="color: #3b82f6; margin-top: 0;">New Inquiry Received</h2>
                        <p style="font-size: 14px; color: #666;">You have a new lead from the Fullventory AI landing page.</p>
                        <div style="background: #f9f9f9; padding: 15px; border-radius: 10px; margin: 20px 0;">
                            <p><strong>Client Name:</strong> {fname} {lname}</p>
                            <p><strong>Work Email:</strong> {client_email}</p>
                            <p><strong>Inquiry Type:</strong> {subject_type}</p>
                        </div>
                        <p><strong>Business Details:</strong></p>
                        <div style="padding: 15px; border-left: 4px solid #3b82f6; background: #f0f7ff;">
                            {details}
                        </div>
                    </div>
                """
            })
            flash("Message Transmitted Successfully! We will reach out shortly.", "success")
        except Exception as e:
            flash(f"System Error: {str(e)}", "error")
            
        return redirect(url_for('contact'))

    # If the user is just VISITING the page
    return render_template('contact.html')
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)