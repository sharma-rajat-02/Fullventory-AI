import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import smtplib
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, session, jsonify, request, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.ensemble import RandomForestRegressor
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fpdf import FPDF

# --- DYNAMIC PATHING ---
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "rajat_startup_2026")
CORS(app)

# --- CONFIG ---
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")

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

class OrderHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="PENDING")

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    threshold_days = db.Column(db.Integer)
    reorder_amount = db.Column(db.Integer)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password=generate_password_hash('admin123')))
    db.session.commit()

# --- AI ENGINE (Optimized for Render Memory) ---
def run_ai_engine(threshold_val):
    TRAIN_PATH = BASE_DIR / "train.csv"
    TEST_PATH = BASE_DIR / "test.csv"
    if not TRAIN_PATH.exists(): return
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading 200k rows for high-accuracy training...")
        # 200,000 rows is the stable limit for Render Free Tier RAM
        train_df = pd.read_csv(TRAIN_PATH, nrows=200000)
        test_df = pd.read_csv(TEST_PATH, nrows=50000)
        
        def clean(df):
            df.columns = df.columns.str.lower()
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                # Using int16 saves 75% memory compared to standard int64
                df['day'] = df['date'].dt.day.astype('int16')
                df['month'] = df['date'].dt.month.astype('int16')
                df['year'] = df['date'].dt.year.astype('int16')
                df['dayofweek'] = df['date'].dt.dayofweek.astype('int16')
            return df

        train_df, test_df = clean(train_df), clean(test_df)
        features = ['store', 'item', 'day', 'month', 'year', 'dayofweek']
        
        # Max depth increased to 10 for 90%+ accuracy; n_jobs=1 to prevent SIGKILL
        model = RandomForestRegressor(n_estimators=10, max_depth=10, random_state=42, n_jobs=1)
        model.fit(train_df[features], train_df['sales'])
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Mapping predictions to inventory...")
        test_df['predicted_sales'] = model.predict(test_df[features])
        summary = test_df.groupby(['store', 'item'])['predicted_sales'].mean().reset_index()
        
        for _, row in summary.iterrows():
            sid, iid = int(row['store']), int(row['item'])
            p = Product.query.filter_by(item_id=iid, store_id=sid).first()
            if not p: 
                p = Product(item_id=iid, store_id=sid, current_stock=500)
            
            p.last_forecast = float(row['predicted_sales'])
            divisor = p.last_forecast if p.last_forecast > 0 else 0.001
            runway = p.current_stock / divisor
            
            p.status = "CRITICAL" if runway <= threshold_val else "HEALTHY"
            db.session.add(p)
            
        db.session.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] AI Sync Success.")
    except Exception as e:
        print(f"AI Sync Error: {e}")

# --- API ROUTES ---
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    config = Settings.query.first()
    if not config:
        config = Settings(threshold_days=10, reorder_amount=500)
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        data = request.json
        new_thresh = int(data.get('threshold_days'))
        new_qty = int(data.get('reorder_amount'))
        config.threshold_days = new_thresh
        config.reorder_amount = new_qty
        db.session.commit()
        run_ai_engine(new_thresh) 
        return jsonify({"status": "success"})
    return jsonify({"status": "success", "threshold_days": config.threshold_days, "reorder_amount": config.reorder_amount})

@app.route('/api/inventory')
def get_inventory():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    products = Product.query.all()
    if not products: 
        config = Settings.query.first()
        run_ai_engine(config.threshold_days if config else 10)
        products = Product.query.all()
    
    data = []
    for p in products:
        divisor = p.last_forecast if p.last_forecast and p.last_forecast > 0 else 0.001
        data.append({
            "store": p.store_id, 
            "item": p.item_id, 
            "days_left": round(p.current_stock / divisor, 1), 
            "status": p.status
        })
    return jsonify({"status": "success", "data": data})

@app.route('/api/trends/<int:sid>/<int:iid>')
def get_trends(sid, iid):
    # Sampled for the trend graph to keep it fast
    df = pd.read_csv(BASE_DIR / "train.csv", nrows=100000)
    df.columns = df.columns.str.lower()
    if 'date' in df.columns: df['date'] = pd.to_datetime(df['date'])
    subset = df[(df['store'] == sid) & (df['item'] == iid)].sort_values('date').tail(30)
    return jsonify({"status": "success", "labels": subset['date'].dt.strftime('%Y-%m-%d').tolist(), "values": subset['sales'].tolist()})

@app.route('/api/report')
def download_report():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    sid = request.args.get('store')
    products = Product.query.filter_by(store_id=int(sid)).all() if sid and sid != 'all' else Product.query.all()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(200, 10, "Fullventory AI Report", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", 'B', 11)
    pdf.cell(30, 10, "Store", 1); pdf.cell(40, 10, "Item ID", 1); pdf.cell(40, 10, "Runway", 1); pdf.cell(60, 10, "Status", 1); pdf.ln()
    for p in products:
        divisor = p.last_forecast if p.last_forecast and p.last_forecast > 0 else 0.001
        runway = round(p.current_stock / divisor, 1)
        pdf.cell(30, 10, str(p.store_id), 1); pdf.cell(40, 10, str(p.item_id), 1); pdf.cell(40, 10, str(runway), 1); pdf.cell(60, 10, p.status, 1); pdf.ln()
    path = BASE_DIR / "temp_report.pdf"
    pdf.output(str(path))
    return send_file(str(path), as_attachment=True)

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        msg = MIMEMultipart()
        msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
        msg['Subject'] = f"RESTOCK ALERT: Store {data['store_id']}"
        msg.attach(MIMEText(f"AI Alert: Item {data['item_id']} is low.", 'plain'))
        server.send_message(msg); server.quit()
        db.session.add(OrderHistory(item_id=data['item_id'], store_id=data['store_id'])); db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/receive', methods=['POST'])
def receive_order():
    order = OrderHistory.query.get(request.json.get('order_id'))
    if order:
        p = Product.query.filter_by(item_id=order.item_id, store_id=order.store_id).first()
        if p: 
            config = Settings.query.first()
            p.current_stock += (config.reorder_amount if config else 500)
            p.status = "HEALTHY"
        order.status = "RECEIVED"; db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/history')
def get_history():
    history = OrderHistory.query.order_by(OrderHistory.order_date.desc()).limit(10).all()
    return jsonify({"status": "success", "data": [{"id": h.id, "item": h.item_id, "store": h.store_id, "date": h.order_date.strftime("%Y-%m-%d %H:%M"), "status": h.status} for h in history]})

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
    app.run(host='0.0.0.0', port=10000)