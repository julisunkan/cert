import os
import json
import sqlite3
import uuid
import hashlib
import csv
import zipfile
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, send_file, redirect, url_for, abort, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
import qrcode
from io import BytesIO

app = Flask(__name__)

def cleanup_old_certificates():
    """Background task to delete certificates older than 5 minutes"""
    while True:
        try:
            now = time.time()
            output_dir = 'static/output'
            if os.path.exists(output_dir):
                for filename in os.listdir(output_dir):
                    if filename.endswith('.pdf') and filename != 'preview_live.pdf':
                        file_path = os.path.join(output_dir, filename)
                        if os.path.getmtime(file_path) < now - 300: # 5 minutes
                            try:
                                os.remove(file_path)
                            except:
                                pass
        except Exception as e:
            pass
        time.sleep(60) # Run every minute

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_certificates, daemon=True)
cleanup_thread.start()

app.config['UPLOAD_FOLDER'] = 'static'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-123')
ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY', 'change-me')

DATABASE = 'database.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Ensure DB is initialized
with app.app_context():
    def init_db():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category TEXT,
                orientation TEXT,
                background TEXT,
                config_json TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cert_id TEXT,
                serial TEXT,
                template_id INTEGER,
                recipient TEXT,
                course TEXT,
                issuer TEXT,
                file_path TEXT,
                hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if templates exist
        cursor.execute('SELECT COUNT(*) FROM templates')
        if cursor.fetchone()[0] == 0:
            categories = {
                'EDUCATION': ('#F0FDF4', 'Helvetica-Bold', '#166534', 32), # Green
                'MODERN BUSINESS': ('#FFF7ED', 'Helvetica-Bold', '#9A3412', 34), # Orange
                'VINTAGE RELIGIOUS': ('#FEF3C7', 'Times-Bold', '#78350F', 28), # Brown/Yellow
                'COMMUNITY EVENT': ('#ECFDF5', 'Courier-Bold', '#065F46', 30), # Emerald
                'AWARD OF EXCELLENCE': ('#FFFFFF', 'Helvetica-Bold', '#1E293B', 36), # Classic White/Slate
                'CREATIVE WORKSHOP': ('#FFFBEB', 'Helvetica-Bold', '#B45309', 30), # Amber
            }
            
            for category, (bg_color, font, text_color, title_size) in categories.items():
                count = 3 # 3 variations per category
                for i in range(1, count + 1):
                    name = f"{category.capitalize()} Template {i}"
                    orientation = 'landscape' if (i % 2 == 0) else 'portrait'
                    
                    if orientation == 'landscape':
                        width, height = landscape(A4)
                    else:
                        width, height = portrait(A4)
                    
                    center_x = width / 2
                    
                    config = {
                        "recipient": {"x": center_x, "y": height * 0.45, "font": font, "size": 36, "color": text_color},
                        "title": {"x": center_x, "y": height * 0.7, "font": font, "size": title_size, "color": text_color},
                        "course": {"x": center_x, "y": height * 0.35, "font": "Helvetica", "size": 24, "color": "#333333"},
                        "date": {"x": width * 0.25, "y": height * 0.15, "font": "Helvetica", "size": 14, "color": "#666666"},
                        "issuer": {"x": width * 0.75, "y": height * 0.15, "font": "Helvetica", "size": 14, "color": "#666666"},
                        "signature_pos": {"x": width * 0.7, "y": height * 0.2, "width": 100, "height": 50},
                        "logo_pos": {"x": center_x - 50, "y": height * 0.8, "width": 100, "height": 100},
                        "qr_pos": {"x": width * 0.05, "y": height * 0.05, "size": 60},
                        "serial_pos": {"x": width * 0.85, "y": height * 0.05, "font": "Helvetica", "size": 10, "color": "#999999"},
                        "watermark": {"text": "ORIGINAL CERTIFICATE", "opacity": 0.05, "angle": 45, "size": 60}
                    }
                    cursor.execute(
                        'INSERT INTO templates (name, category, orientation, background, config_json) VALUES (?, ?, ?, ?, ?)',
                        (name, category, orientation, bg_color, json.dumps(config))
                    )
        conn.commit()
        conn.close()
    
    init_db()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_pdf(cert_data, template, output_path):
    config = json.loads(template['config_json'])
    orientation = landscape(A4) if template['orientation'] == 'landscape' else portrait(A4)
    w, h = orientation
    
    c = canvas.Canvas(output_path, pagesize=orientation)
    
    # Background
    if template['background']:
        if template['background'].startswith('#'):
            c.setFillColor(HexColor(template['background']))
            c.rect(0, 0, w, h, fill=1)
        else:
            bg_path = os.path.join('static/backgrounds', template['background'])
            if os.path.exists(bg_path):
                c.drawImage(bg_path, 0, 0, width=w, height=h)
            
    # Watermark
    wm = config.get('watermark', {})
    if wm:
        c.saveState()
        c.setFont("Helvetica", wm.get('size', 60))
        c.setStrokeColorRGB(0,0,0, alpha=wm.get('opacity', 0.1))
        c.setFillColorRGB(0,0,0, alpha=wm.get('opacity', 0.1))
        c.translate(w/2, h/2)
        c.rotate(wm.get('angle', 45))
        c.drawCentredString(0, 0, wm.get('text', 'ORIGINAL'))
        c.restoreState()

    # Recipient
    rec = config['recipient']
    c.setFont(rec['font'], rec['size'])
    c.setFillColor(HexColor(rec['color']))
    c.drawCentredString(rec['x'], rec['y'], cert_data['recipient'])
    
    # Title
    tit = config['title']
    c.setFont(tit['font'], tit['size'])
    c.drawCentredString(tit['x'], tit['y'], cert_data['title'])
    
    # Course
    cou = config['course']
    c.setFont(cou['font'], cou['size'])
    c.drawCentredString(cou['x'], cou['y'], cert_data['course'])
    
    # Date & Issuer
    dat = config['date']
    c.setFont(dat['font'], dat['size'])
    c.drawCentredString(dat['x'], dat['y'], f"Date: {cert_data['date']}")
    
    iss = config['issuer']
    c.setFont(iss['font'], iss['size'])
    c.drawCentredString(iss['x'], iss['y'], f"Issuer: {cert_data['issuer']}")
    
    # Serial
    ser = config['serial_pos']
    c.setFont(ser['font'], ser['size'])
    c.drawCentredString(ser['x'], ser['y'], f"Serial: {cert_data['serial']}")
    
    # Logo
    if cert_data.get('logo_path'):
        l_pos = config['logo_pos']
        c.drawImage(cert_data['logo_path'], l_pos['x'], l_pos['y'], width=l_pos['width'], height=l_pos['height'], mask='auto')
        
    # Signature
    if cert_data.get('sig_path'):
        s_pos = config['signature_pos']
        c.drawImage(cert_data['sig_path'], s_pos['x'], s_pos['y'], width=s_pos['width'], height=s_pos['height'], mask='auto')
        
    # QR Code
    qr_url = f"{request.host_url}verify/{cert_data['cert_id']}"
    qr = qrcode.make(qr_url)
    
    qr_io = BytesIO()
    qr.save(qr_io, format='PNG')
    qr_io.seek(0)
    
    qr_pos = config['qr_pos']
    c.drawImage(ImageReader(qr_io), qr_pos['x'], qr_pos['y'], width=qr_pos['size'], height=qr_pos['size'])
    
    c.showPage()
    c.save()

@app.route('/')
def index():
    db = get_db()
    templates = db.execute('SELECT * FROM templates').fetchall()
    return render_template('index.html', templates=templates)

@app.route('/preview_realtime/<int:template_id>', methods=['POST'])
def preview_realtime(template_id):
    db = get_db()
    template = db.execute('SELECT * FROM templates WHERE id = ?', (template_id,)).fetchone()
    if not template:
        return "Template not found", 404
        
    cert_id = "preview"
    serial = "CERT-2026-PREVIEW"
    
    recipient = request.form.get('recipient', 'Recipient Name')
    course = request.form.get('course', 'Course Name')
    title = request.form.get('title', 'CERTIFICATE TITLE')
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    issuer = request.form.get('issuer', 'Issuer Name')
    
    file_path = os.path.join('static/output', "preview_live.pdf")
    
    cert_data = {
        'cert_id': cert_id,
        'serial': serial,
        'recipient': recipient,
        'course': course,
        'title': title,
        'date': date,
        'issuer': issuer,
        'logo_path': None,
        'sig_path': None
    }
    
    generate_pdf(cert_data, template, file_path)
    return send_file(file_path)

@app.route('/generate/<int:template_id>', methods=['GET', 'POST'])
def generate(template_id):
    db = get_db()
    template = db.execute('SELECT * FROM templates WHERE id = ?', (template_id,)).fetchone()
    if not template:
        abort(404)
        
    if request.method == 'POST':
        cert_id = str(uuid.uuid4())
        
        cursor = db.cursor()
        cursor.execute('SELECT COUNT(*) FROM certificates')
        count = cursor.fetchone()[0] + 1
        serial = f"CERT-{datetime.now().year}-{count:06d}"
        
        recipient = request.form['recipient']
        course = request.form['course']
        title = request.form['title']
        date = request.form['date']
        issuer = request.form['issuer']
        
        logo_path = None
        if 'logo' in request.files and request.files['logo'].filename:
            logo = request.files['logo']
            logo_path = os.path.join('static/logos', f"{cert_id}_{logo.filename}")
            logo.save(logo_path)
            
        sig_path = None
        if 'signature' in request.files and request.files['signature'].filename:
            sig = request.files['signature']
            sig_path = os.path.join('static/signatures', f"{cert_id}_{sig.filename}")
            sig.save(sig_path)
            
        data_to_hash = f"{serial}{recipient}{date}"
        cert_hash = hashlib.sha256(data_to_hash.encode()).hexdigest()
        
        file_name = f"{cert_id}.pdf"
        file_path = os.path.join('static/output', file_name)
        
        cert_data = {
            'cert_id': cert_id,
            'serial': serial,
            'recipient': recipient,
            'course': course,
            'title': title,
            'date': date,
            'issuer': issuer,
            'logo_path': logo_path,
            'sig_path': sig_path
        }
        
        generate_pdf(cert_data, template, file_path)
        
        db.execute('''
            INSERT INTO certificates (cert_id, serial, template_id, recipient, course, issuer, file_path, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (cert_id, serial, template_id, recipient, course, issuer, file_path, cert_hash))
        db.commit()
        
        return send_file(file_path, as_attachment=True)
        
    return render_template('editor.html', template=template)

@app.route('/bulk/<int:template_id>', methods=['GET', 'POST'])
def bulk(template_id):
    db = get_db()
    template = db.execute('SELECT * FROM templates WHERE id = ?', (template_id,)).fetchone()
    if not template:
        abort(404)
        
    if request.method == 'POST':
        if 'csv' not in request.files:
            return "No CSV file uploaded", 400
            
        csv_file = request.files['csv']
        title = request.form.get('title', 'CERTIFICATE OF ACHIEVEMENT')
        issuer = request.form.get('issuer', 'Organization')
        
        logo_path = None
        if 'logo' in request.files and request.files['logo'].filename:
            logo = request.files['logo']
            logo_path = os.path.join('static/logos', f"bulk_{logo.filename}")
            logo.save(logo_path)
            
        sig_path = None
        if 'signature' in request.files and request.files['signature'].filename:
            sig = request.files['signature']
            sig_path = os.path.join('static/signatures', f"bulk_{sig.filename}")
            sig.save(sig_path)
            
        stream = BytesIO(csv_file.read())
        try:
            content = stream.read().decode('utf-8')
            reader = csv.DictReader(content.splitlines())
        except Exception as e:
            return f"Error reading CSV: {str(e)}", 400
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for row in reader:
                if not row.get('name'): continue
                
                cert_id = str(uuid.uuid4())
                cursor = db.cursor()
                cursor.execute('SELECT COUNT(*) FROM certificates')
                count = cursor.fetchone()[0] + 1
                serial = f"CERT-{datetime.now().year}-{count:06d}"
                
                recipient = row['name']
                course = row.get('course', 'Completed Training')
                date = row.get('date', datetime.now().strftime('%Y-%m-%d'))
                
                data_to_hash = f"{serial}{recipient}{date}"
                cert_hash = hashlib.sha256(data_to_hash.encode()).hexdigest()
                
                file_path = os.path.join('static/output', f"{cert_id}.pdf")
                
                cert_data = {
                    'cert_id': cert_id,
                    'serial': serial,
                    'recipient': recipient,
                    'course': course,
                    'title': title,
                    'date': date,
                    'issuer': issuer,
                    'logo_path': logo_path,
                    'sig_path': sig_path
                }
                
                generate_pdf(cert_data, template, file_path)
                
                db.execute('''
                    INSERT INTO certificates (cert_id, serial, template_id, recipient, course, issuer, file_path, hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (cert_id, serial, template_id, recipient, course, issuer, file_path, cert_hash))
                
                zf.write(file_path, f"{recipient}_{serial}.pdf")
        
        db.commit()
        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name="certificates.zip")
        
    return render_template('bulk.html', template=template)

@app.route('/verify/<cert_id>')
def verify(cert_id):
    db = get_db()
    cert = db.execute('''
        SELECT c.*, t.name as template_name 
        FROM certificates c 
        JOIN templates t ON c.template_id = t.id 
        WHERE c.cert_id = ? OR c.serial = ?
    ''', (cert_id, cert_id)).fetchone()
    
    status = "Invalid"
    if cert:
        status = "Valid"
        
    return render_template('verify.html', cert=cert, status=status)

@app.route('/verify/search')
def verify_search():
    search_id = request.args.get('id')
    if not search_id:
        return redirect(url_for('index'))
    return redirect(url_for('verify', cert_id=search_id))

@app.route('/__admin__/templates')
def admin_templates():
    if request.args.get('key') != ADMIN_SECRET_KEY:
        abort(404)
    db = get_db()
    templates = db.execute('SELECT * FROM templates').fetchall()
    return render_template('admin/templates.html', templates=templates, key=ADMIN_SECRET_KEY)

@app.route('/manifest.json')
def manifest():
    return send_file('static/manifest.json', mimetype='application/manifest+json')

@app.route('/service-worker.js')
def service_worker():
    return send_file('static/service-worker.js', mimetype='application/javascript')

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000)
