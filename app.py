"""
Celebration Website Backend
Flask + SQLite3 + Stripe + Cloudinary
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import stripe
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
CORS(app)

# ========================================
# CONFIGURATION
# ========================================
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['DATABASE'] = 'celebration.db'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Stripe Configuration
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# ========================================
# DATABASE SETUP
# ========================================
def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    
    # Messages table
    db.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            relationship TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Memories table (photos)
    db.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            caption TEXT,
            image_url TEXT NOT NULL,
            cloudinary_id TEXT,
            type TEXT DEFAULT 'photo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Donations table
    db.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_name TEXT NOT NULL,
            donor_email TEXT NOT NULL,
            amount REAL NOT NULL,
            charity_id TEXT,
            charity_name TEXT,
            message TEXT,
            stripe_payment_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Cancellations table
    db.execute('''
        CREATE TABLE IF NOT EXISTS cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            request_type TEXT NOT NULL,
            number_of_guests INTEGER,
            reason TEXT NOT NULL,
            zoom_interest BOOLEAN DEFAULT 0,
            future_updates BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Gallery folders metadata
    db.execute('''
        CREATE TABLE IF NOT EXISTS gallery_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            icon TEXT DEFAULT 'fa-folder',
            gradient TEXT DEFAULT 'folder-solo',
            description TEXT,
            image_count INTEGER DEFAULT 0
        )
    ''')
    
    # Gallery images
    db.execute('''
        CREATE TABLE IF NOT EXISTS gallery_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_name TEXT NOT NULL,
            image_url TEXT NOT NULL,
            cloudinary_id TEXT,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (folder_name) REFERENCES gallery_folders(name)
        )
    ''')
    
    db.commit()
    db.close()

# ========================================
# HELPER FUNCTIONS
# ========================================
def upload_to_cloudinary(file, folder='memories'):
    """Upload file to Cloudinary"""
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=f'celebration/{folder}',
            transformation=[
                {'width': 1200, 'height': 1200, 'crop': 'limit'},
                {'quality': 'auto:good'}
            ]
        )
        return {
            'url': result['secure_url'],
            'public_id': result['public_id']
        }
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

def send_email_notification(to_email, subject, body):
    """Send email notification (implement with your email service)"""
    # TODO: Integrate with SendGrid, Mailgun, or AWS SES
    print(f"Email notification: {subject} to {to_email}")
    pass

# ========================================
# GALLERY ENDPOINTS
# ========================================
@app.route('/api/gallery/folders', methods=['GET'])
def get_gallery_folders():
    try:
        db = get_db()
        folders = db.execute(
            'SELECT * FROM gallery_folders ORDER BY display_name'
        ).fetchall()
        
        return jsonify({
            'success': True,
            'folders': [dict(f) for f in folders]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/gallery/images', methods=['GET'])
def get_gallery_images():
    folder_name = request.args.get('folder')
    
    if not folder_name:
        return jsonify({'success': False, 'message': 'Folder name required'}), 400
    
    try:
        db = get_db()
        images = db.execute(
            'SELECT * FROM gallery_images WHERE folder_name = ? ORDER BY order_index',
            (folder_name,)
        ).fetchall()
        
        return jsonify({
            'success': True,
            'images': [dict(img) for img in images]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# MESSAGES ENDPOINTS
# ========================================
@app.route('/api/messages', methods=['GET'])
def get_messages():
    limit = request.args.get('limit', 10, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    try:
        db = get_db()
        messages = db.execute(
            'SELECT * FROM messages ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (limit, offset)
        ).fetchall()
        
        total_row = db.execute('SELECT COUNT(*) as count FROM messages').fetchone()
        total = total_row['count'] if total_row else 0
        
        return jsonify({
            'success': True,
            'messages': [dict(msg) for msg in messages],
            'total': total
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/messages', methods=['POST'])
def submit_message():
    data = request.json
    
    if not data.get('name') or not data.get('message'):
        return jsonify({'success': False, 'message': 'Name and message required'}), 400
    
    try:
        db = get_db()
        cursor = db.execute(
            'INSERT INTO messages (name, relationship, message) VALUES (?, ?, ?)',
            (data['name'], data.get('relationship', ''), data['message'])
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message submitted successfully',
            'id': cursor.lastrowid
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# MEMORIES ENDPOINTS
# ========================================
@app.route('/api/memories', methods=['GET'])
def get_memories():
    memory_type = request.args.get('type', 'all')
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    try:
        db = get_db()
        
        if memory_type == 'all':
            query = 'SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params = (limit, offset)
        else:
            query = 'SELECT * FROM memories WHERE type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params = (memory_type, limit, offset)
        
        memories = db.execute(query, params).fetchall()
        
        return jsonify({
            'success': True,
            'memories': [dict(mem) for mem in memories]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/memories/photos', methods=['POST'])
def submit_photo_memory():
    if 'photos[]' not in request.files:
        return jsonify({'success': False, 'message': 'No photos provided'}), 400
    
    name = request.form.get('name')
    caption = request.form.get('caption') or ''
    
    if not name:
        return jsonify({'success': False, 'message': 'Name required'}), 400
    
    try:
        db = get_db()
        files = request.files.getlist('photos[]')
        uploaded_count = 0
        
        for file in files:
            if file and file.filename:
                # Upload to Cloudinary
                upload_result = upload_to_cloudinary(file, 'memories')
                
                if upload_result:
                    db.execute(
                        'INSERT INTO memories (name, caption, image_url, cloudinary_id, type) VALUES (?, ?, ?, ?, ?)',
                        (name, caption, upload_result['url'], upload_result['public_id'], 'photo')
                    )
                    uploaded_count += 1
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'{uploaded_count} photo(s) uploaded successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/memories/text', methods=['POST'])
def submit_text_memory():
    data = request.json
    
    if not data.get('name') or not data.get('message'):
        return jsonify({'success': False, 'message': 'Name and message required'}), 400
    
    try:
        db = get_db()
        db.execute(
            'INSERT INTO memories (name, caption, image_url, type) VALUES (?, ?, ?, ?)',
            (data['name'], data['message'], '', 'text')
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Memory submitted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# DONATIONS ENDPOINTS (Stripe)
# ========================================
@app.route('/api/donations/create-intent', methods=['POST'])
def create_payment_intent():
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    amount = data.get('amount')
    if not amount or amount <= 0:
        return jsonify({'success': False, 'message': 'Invalid amount'}), 400
    
    try:
        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'gbp',
                    'unit_amount': int(amount * 100),  # Convert to pence
                    'product_data': {
                        'name': f"Donation to {data.get('charity_name') or 'General Fund'}",
                        'description': 'Celebrating Abiye & Modupe'
                    }
                },
                'quantity': 1
            }],
            mode='payment',
            success_url=os.getenv('SUCCESS_URL', 'https://yoursite.com/success'),
            cancel_url=os.getenv('CANCEL_URL', 'https://yoursite.com/charity'),
            metadata={
                'donor_name': data.get('donor_name') or '',
                'donor_email': data.get('donor_email') or '',
                'charity_id': data.get('charity_id') or '',
                'charity_name': data.get('charity_name') or '',
                'message': data.get('message') or ''
            }
        )
        
        # Save to database
        db = get_db()
        db.execute(
            'INSERT INTO donations (donor_name, donor_email, amount, charity_id, charity_name, message, stripe_payment_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (data.get('donor_name'), data.get('donor_email'), amount, data.get('charity_id'), data.get('charity_name'), data.get('message'), session.id)
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'checkout_url': session.url
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/donations/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        db = get_db()
        db.execute(
            'UPDATE donations SET status = ? WHERE stripe_payment_id = ?',
            ('completed', session.id)
        )
        db.commit()
        
        # Send confirmation email
        # send_email_notification(...)
    
    return jsonify({'success': True})

@app.route('/api/donations/confirm', methods=['POST'])
def confirm_donation():
    data = request.json
    payment_intent_id = data.get('payment_intent_id')
    
    if not payment_intent_id:
        return jsonify({'success': False, 'message': 'Payment ID required'}), 400
    
    try:
        db = get_db()
        db.execute(
            'UPDATE donations SET status = ? WHERE stripe_payment_id = ?',
            ('completed', payment_intent_id)
        )
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# CANCELLATION ENDPOINT
# ========================================
@app.route('/api/cancel-reservation', methods=['POST'])
def cancel_reservation():
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    required = ['firstName', 'lastName', 'email', 'requestType', 'reason']
    if not all(data.get(field) for field in required):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    try:
        db = get_db()
        db.execute(
            '''INSERT INTO cancellations 
            (first_name, last_name, email, phone, request_type, number_of_guests, reason, zoom_interest, future_updates) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                data['firstName'], data['lastName'], data['email'], 
                data.get('phone') or '', data['requestType'], 
                data.get('numberOfGuests') or 0, data['reason'],
                data.get('zoomInterest') or False, data.get('futureUpdates') or False
            )
        )
        db.commit()
        
        # Send notification email
        # send_email_notification(...)
        
        return jsonify({
            'success': True,
            'message': 'Cancellation request received'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# STATS ENDPOINT
# ========================================
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        db = get_db()
        
        total_row = db.execute(
            "SELECT SUM(amount) as total FROM donations WHERE status = 'completed'"
        ).fetchone()
        total_raised = total_row['total'] if total_row and total_row['total'] else 0
        
        donor_row = db.execute(
            "SELECT COUNT(DISTINCT donor_email) as count FROM donations WHERE status = 'completed'"
        ).fetchone()
        donor_count = donor_row['count'] if donor_row else 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_raised': total_raised,
                'donor_count': donor_count,
                'goal': 10000  # Set your goal
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# HEALTH CHECK
# ========================================
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

# ========================================
# INITIALIZATION
# ========================================
if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(debug=os.getenv('DEBUG', 'False') == 'True', host='0.0.0.0', port=port)

# For gunicorn (Railway/production)
# This ensures the app works when run with gunicorn
if os.getenv('RAILWAY_ENVIRONMENT'):
    try:
        init_db()
    except:
        pass  # Database might already exist