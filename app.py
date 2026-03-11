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

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "rajat_startup_2026")
CORS(app)

# --- CONFIG ---
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
BASE_DIR = Path(os.getenv("BASE_DIRECTORY", r"C:/Users/Dell/Python/Inventory Stock Startup"))

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR.as_posix()}/inventory.db"
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
    threshold_days = db.Column(db.Integer, default=10)
    reorder_amount = db.Column(db.Integer, default=500)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password=generate_password_hash('admin123')))
    if not Settings.query.first():
        db.session.add(Settings(threshold_days=10, reorder_amount=500))
    db.session.commit()

# --- AI ENGINE ---
def run_ai_engine():
    TRAIN_PATH, TEST_PATH = BASE_DIR / "train.csv", BASE_DIR / "test.csv"
    if not TRAIN_PATH.exists(): return
    config = Settings.query.first()
    threshold = config.threshold_days if config else 10
    train_df, test_df = pd.read_csv(TRAIN_PATH), pd.read_csv(TEST_PATH)
    def clean(df):
        df.columns = df.columns.str.lower()
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df['day'], df['month'], df['year'] = df['date'].dt.day, df['date'].dt.month, df['date'].dt.year
            df['dayofweek'] = df['date'].dt.dayofweek
        return df
    train_df, test_df = clean(train_df), clean(test_df)
    features = ['store', 'item', 'day', 'month', 'year', 'dayofweek']
    model = RandomForestRegressor(n_estimators=10, max_depth=5, random_state=42)
    model.fit(train_df[features], train_df['sales'])
    test_df['predicted_sales'] = model.predict(test_df[features])
    summary = test_df.groupby(['store', 'item'])['predicted_sales'].mean().reset_index()
    for _, row in summary.iterrows():
        p = Product.query.filter_by(item_id=int(row['item']), store_id=int(row['store'])).first()
        if not p: p = Product(item_id=int(row['item']), store_id=int(row['store']), current_stock=500)
        p.last_forecast = row['predicted_sales']
        runway = (p.current_stock or 500) / (row['predicted_sales'] or 0.1)
        p.status = "CRITICAL" if runway <= threshold else "HEALTHY"
        db.session.add(p)
    db.session.commit()

# --- ROUTES ---
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    config = Settings.query.first()
    if request.method == 'POST':
        data = request.json
        config.threshold_days = int(data.get('threshold_days', 10))
        config.reorder_amount = int(data.get('reorder_amount', 500))
        db.session.commit()
        run_ai_engine()
        return jsonify({"status": "success", "message": "AI Synced!"})
    return jsonify({"status": "success", "threshold_days": config.threshold_days, "reorder_amount": config.reorder_amount})

@app.route('/api/report')
def download_report():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    sid = request.args.get('store')
    if sid and sid != 'all':
        products = Product.query.filter_by(store_id=int(sid)).all()
        title = f"Inventory Report: Store {sid}"
    else:
        products = Product.query.all()
        title = "Global Inventory Report (All Stores)"
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(200, 10, title, ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.cell(200, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", 'B', 12)
    pdf.cell(30, 10, "Store", 1); pdf.cell(40, 10, "Item ID", 1); pdf.cell(40, 10, "Runway (Days)", 1); pdf.cell(60, 10, "Health Status", 1); pdf.ln()
    pdf.set_font("Arial", '', 11)
    for p in products:
        runway = round((p.current_stock or 500) / (p.last_forecast or 0.1), 1)
        pdf.cell(30, 10, str(p.store_id), 1); pdf.cell(40, 10, str(p.item_id), 1); pdf.cell(40, 10, str(runway), 1); pdf.cell(60, 10, p.status, 1); pdf.ln()
    path = BASE_DIR / "report.pdf"; pdf.output(str(path))
    return send_file(str(path), as_attachment=True)

@app.route('/api/trends/<int:sid>/<int:iid>')
def get_trends(sid, iid):
    df = pd.read_csv(BASE_DIR / "train.csv")
    df.columns = df.columns.str.lower(); df['date'] = pd.to_datetime(df['date'])
    subset = df[(df['store'] == sid) & (df['item'] == iid)].sort_values('date').tail(30)
    return jsonify({"status": "success", "labels": subset['date'].dt.strftime('%Y-%m-%d').tolist(), "values": subset['sales'].tolist()})

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    products = Product.query.all()
    if not products: run_ai_engine(); products = Product.query.all()
    return jsonify({"status": "success", "data": [{"store": p.store_id, "item": p.item_id, "days_left": round((p.current_stock or 500) / (p.last_forecast or 0.1), 1), "status": p.status} for p in products]})

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = SENDER_EMAIL, RECEIVER_EMAIL, f"ORDER: Store {data['store_id']} | Item #{data['item_id']}"
        msg.attach(MIMEText(f"AI Restock triggered for Store {data['store_id']}.", 'plain'))
        server.send_message(msg); server.quit()
        db.session.add(OrderHistory(item_id=data['item_id'], store_id=data['store_id'])); db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/receive', methods=['POST'])
def receive_order():
    config = Settings.query.first()
    order = OrderHistory.query.get(request.json.get('order_id'))
    product = Product.query.filter_by(item_id=order.item_id, store_id=order.store_id).first()
    if product:
        product.current_stock += (config.reorder_amount if config else 500)
        runway = product.current_stock / (product.last_forecast or 0.1)
        product.status = "HEALTHY" if runway > (config.threshold_days if config else 10) else "CRITICAL"
        order.status = "RECEIVED"; db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/history', methods=['GET'])
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

if __name__ == '__main__': app.run(host='127.0.0.1', port=8080, debug=True)