import os
import math
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import resend 
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, session, jsonify, request, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.ensemble import RandomForestRegressor
from fpdf import FPDF

# --- SETUP ---
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "rajat_startup_2026")
CORS(app)

# --- CONFIG ---
resend.api_key = os.getenv("RESEND_API_KEY")
ADMIN_EMAIL = os.getenv("RECEIVER_EMAIL")
MY_DOMAIN = "fullventoryai.me" 

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR.joinpath('inventory.db').as_posix()}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer, nullable=False)
    current_stock = db.Column(db.Integer, default=500)
    last_forecast = db.Column(db.Float)
    status = db.Column(db.String(20), default="HEALTHY")

class StoreSupplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)

class OrderHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, default=500)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="PENDING")

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    threshold_days = db.Column(db.Integer, default=10)
    reorder_amount = db.Column(db.Integer, default=500)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password=generate_password_hash('admin123')))
    db.session.commit()

# --- AI ENGINE ---
def run_ai_engine(threshold_val):
    TRAIN_PATH = BASE_DIR / "train.csv"
    TEST_PATH = BASE_DIR / "test.csv"
    if not TRAIN_PATH.exists(): return
    try:
        train_df = pd.read_csv(TRAIN_PATH, nrows=200000)
        test_df = pd.read_csv(TEST_PATH, nrows=50000)
        def clean(df):
            df.columns = df.columns.str.lower()
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df['day'] = df['date'].dt.day.astype('int16')
                df['month'] = df['date'].dt.month.astype('int16')
                df['year'] = df['date'].dt.year.astype('int16')
                df['dayofweek'] = df['date'].dt.dayofweek.astype('int16')
            return df
        train_df, test_df = clean(train_df), clean(test_df)
        features = ['store', 'item', 'day', 'month', 'year', 'dayofweek']
        model = RandomForestRegressor(n_estimators=10, max_depth=8, random_state=42, n_jobs=1)
        model.fit(train_df[features], train_df['sales'])
        test_df['predicted_sales'] = model.predict(test_df[features])
        summary = test_df.groupby(['store', 'item'])['predicted_sales'].mean().reset_index()
        for _, row in summary.iterrows():
            sid, iid = int(row['store']), int(row['item'])
            p = Product.query.filter_by(item_id=iid, store_id=sid).first()
            if not p: p = Product(item_id=iid, store_id=sid, current_stock=500)
            p.last_forecast = float(row['predicted_sales'])
            runway = p.current_stock / (p.last_forecast if p.last_forecast > 0 else 0.01)
            p.status = "CRITICAL" if runway <= threshold_val else "HEALTHY"
            db.session.add(p)
        db.session.commit()
    except Exception as e: print(f"AI Sync Error: {e}")

# --- API ROUTES ---
@app.route('/api/inventory')
def get_inventory():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    products = Product.query.all()
    config = Settings.query.first()
    thresh = config.threshold_days if config else 10
    data = []
    for p in products:
        forecast = p.last_forecast or 0.01
        days_left = math.floor(p.current_stock / forecast)
        target = (forecast * thresh * 2) * 1.2
        suggested = math.ceil(max(0, target - p.current_stock))
        data.append({"store": p.store_id, "item": p.item_id, "days_left": days_left, "status": p.status, "suggested_reorder": suggested})
    return jsonify({"status": "success", "data": data})

@app.route('/api/suppliers', methods=['GET', 'POST'])
def handle_suppliers():
    if request.method == 'POST':
        data = request.json
        s = StoreSupplier.query.filter_by(store_id=data['store_id']).first()
        if not s: s = StoreSupplier(store_id=data['store_id'])
        s.email = data['email']
        db.session.add(s); db.session.commit()
        return jsonify({"status": "success"})
    suppliers = StoreSupplier.query.all()
    return jsonify({"status": "success", "data": [{"store_id": s.store_id, "email": s.email} for s in suppliers]})

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json
    qty = data.get('quantity', 500)
    s = StoreSupplier.query.filter_by(store_id=data['store_id']).first()
    target = s.email if s else ADMIN_EMAIL
    
    try:
        # Verified Domain Sender
        resend.Emails.send({
            "from": f"Fullventory AI <orders@{MY_DOMAIN}>",
            "to": [target],
            "cc": [ADMIN_EMAIL],
            "subject": f"📦 Order Request: Item #{data['item_id']} [Store {data['store_id']}]",
            "html": f"<h3>Purchase Order Generated</h3><p>Quantity requested: {qty} units</p>"
        })
    except Exception as e:
        print(f"!!! EMAIL FAILED: {e}")

    db.session.add(OrderHistory(item_id=data['item_id'], store_id=data['store_id'], quantity=qty, status='PENDING'))
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/receive', methods=['POST'])
def receive_order():
    order = OrderHistory.query.get(request.json.get('order_id'))
    if order:
        p = Product.query.filter_by(item_id=order.item_id, store_id=order.store_id).first()
        if p: p.current_stock += order.quantity; p.status = "HEALTHY"
        order.status = "RECEIVED"; db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/history')
def get_history():
    history = OrderHistory.query.order_by(OrderHistory.order_date.desc()).limit(10).all()
    return jsonify({"status": "success", "data": [{"id": h.id, "item": h.item_id, "qty": h.quantity, "date": h.order_date.strftime("%m-%d %H:%M"), "status": h.status} for h in history]})

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    config = Settings.query.first() or Settings()
    if request.method == 'POST':
        data = request.json
        config.threshold_days, config.reorder_amount = int(data.get('threshold_days')), int(data.get('reorder_amount'))
        db.session.add(config); db.session.commit(); run_ai_engine(config.threshold_days)
        return jsonify({"status": "success"})
    return jsonify({"status": "success", "threshold_days": config.threshold_days, "reorder_amount": config.reorder_amount})

@app.route('/api/report')
def download_report():
    sid = request.args.get('store')
    products = Product.query.filter_by(store_id=int(sid)).all() if sid and sid != 'all' else Product.query.all()
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(200, 10, "Fullventory AI Report", ln=True, align='C'); pdf.ln(10)
    pdf.set_font("Arial", 'B', 11); pdf.cell(30, 10, "Store", 1); pdf.cell(40, 10, "Item", 1); pdf.cell(40, 10, "Runway", 1); pdf.cell(60, 10, "Status", 1); pdf.ln()
    for p in products:
        forecast = p.last_forecast or 0.01
        runway = math.floor(p.current_stock / forecast)
        pdf.cell(30, 10, str(p.store_id), 1); pdf.cell(40, 10, str(p.item_id), 1); pdf.cell(40, 10, f"{runway} Days", 1); pdf.cell(60, 10, p.status, 1); pdf.ln()
    path = BASE_DIR / "report.pdf"; pdf.output(str(path))
    return send_file(str(path), as_attachment=True)

@app.route('/api/trends/<int:sid>/<int:iid>')
def get_trends(sid, iid):
    df = pd.read_csv(BASE_DIR / "train.csv", nrows=10000)
    df.columns = df.columns.str.lower()
    subset = df[(df['store'] == sid) & (df['item'] == iid)].tail(15)
    return jsonify({"status": "success", "labels": pd.to_datetime(subset['date']).dt.strftime('%m/%d').tolist(), "values": subset['sales'].tolist()})

@app.route('/')
def home(): return redirect(url_for('dashboard')) if 'user_id' in session else redirect(url_for('login_page'))
@app.route('/login')
def login_page(): return render_template('login.html')
@app.route('/dashboard')
def dashboard(): return render_template('index.html') if 'user_id' in session else redirect(url_for('login_page'))
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json; user = User.query.filter_by(username=data.get('username')).first()
    if user and check_password_hash(user.password, data.get('password')):
        session['user_id'] = user.id; return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401
@app.route('/api/logout')
def logout(): session.pop('user_id', None); return redirect(url_for('login_page'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)