from flask import Flask, render_template, request, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os, io, random
import cv2
import numpy as np
from reportlab.pdfgen import canvas as pdf_canvas

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///detections.db'
app.config['SECRET_KEY'] = 'microplastics123'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
os.makedirs('static/uploads', exist_ok=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    count = db.Column(db.Integer)
    level = db.Column(db.String(20))
    date = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def detect_microplastics(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    count = len([c for c in contours if cv2.contourArea(c) > 10])
    return count

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        return render_template('login.html', error='Wrong username or password!')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    file = request.files['image']
    path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(path)
    count = detect_microplastics(path)
    level = "High" if count > 30 else "Moderate" if count > 15 else "Low"
    temperature = round(random.uniform(20.0, 35.0), 1)
    ph = round(random.uniform(6.0, 9.0), 2)
    turbidity = round(random.uniform(0.5, 10.0), 2)
    detection = Detection(filename=file.filename, count=count, level=level)
    db.session.add(detection)
    db.session.commit()
    return render_template('result.html', count=count, level=level, filename=file.filename, temperature=temperature, ph=ph, turbidity=turbidity)

@app.route('/history')
@login_required
def history():
    detections = Detection.query.order_by(Detection.date.desc()).all()
    return render_template('history.html', detections=detections)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/download/<int:count>/<level>')
@login_required
def download(count, level):
    buffer = io.BytesIO()
    p = pdf_canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(150, 800, "Microplastics Detection Report")
    p.setFont("Helvetica", 14)
    p.drawString(100, 750, f"Microplastics Found: {count}")
    p.drawString(100, 720, f"Risk Level: {level}")
    p.drawString(100, 690, "Project: Development of Sensor for Detection of Microplastics")
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="report.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    app.run(debug=True)