"""
Celebration Website Backend - Optimized for Free Cloudinary Tier
Flask + SQLite3 + Stripe + Cloudinary
Features:
- Aggressive image compression
- Video size limits (50MB for free tier)
- Optional fallback to local storage for videos
- Automatic format conversion
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import stripe
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
from PIL import Image
import io
import json

app = Flask(__name__)
CORS(app)

# ========================================
# CONFIGURATION
# ========================================
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['DATABASE'] = 'celebration.db'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max request size
app.config['UPLOAD_FOLDER'] = 'uploads/videos'  # Fallback local storage for videos

# Cloudinary Free Tier Limits
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB (will be compressed further)
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB for Cloudinary free tier
USE_LOCAL_VIDEO_STORAGE = os.getenv('USE_LOCAL_VIDEO_STORAGE', 'false').lower() == 'true'

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    
    # Memories table (photos, videos, text, past)
    db.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            caption TEXT,
            image_url TEXT NOT NULL,
            cloudinary_id TEXT,
            type TEXT DEFAULT 'photo',
            storage_type TEXT DEFAULT 'cloudinary',
            file_size INTEGER,
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
def compress_image(file_data, max_width=1200, quality=75):
    """
    Aggressively compress image to save Cloudinary storage
    Returns: BytesIO object with compressed image
    """
    try:
        # Open image
        img = Image.open(io.BytesIO(file_data))
        
        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Resize if too large
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        
        # Save with compression
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        return output
    except Exception as e:
        print(f"Image compression error: {e}")
        return None

def upload_to_cloudinary(file_data, folder='memories', is_video=False):
    """
    Upload file to Cloudinary with optimization
    Returns: dict with url and public_id
    """
    try:
        if is_video:
            # Video upload - use lower quality for free tier
            result = cloudinary.uploader.upload(
                file_data,
                folder=f'celebration/{folder}',
                resource_type='video',
                transformation=[
                    {'quality': 'auto:low', 'fetch_format': 'auto'}
                ],
                eager=[
                    {'width': 640, 'height': 480, 'crop': 'limit', 'quality': 'auto:low'}
                ]
            )
        else:
            # Image upload - aggressive compression
            compressed = compress_image(file_data.read())
            if not compressed:
                return None
            
            result = cloudinary.uploader.upload(
                compressed,
                folder=f'celebration/{folder}',
                resource_type='image',
                transformation=[
                    {'quality': 'auto:low', 'fetch_format': 'auto'}
                ]
            )
        
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'size': result.get('bytes', 0)
        }
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

def save_video_locally(file, filename):
    """
    Save video to local storage as fallback
    Returns: URL path for the video
    """
    try:
        # Secure filename
        filename = secure_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save file
        file.save(filepath)
        
        # Return URL (adjust based on your deployment)
        return f'/uploads/videos/{filename}'
    except Exception as e:
        print(f"Local storage error: {e}")
        return None

@app.route('/uploads/videos/<filename>')
def serve_video(filename):
    """Serve locally stored videos"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========================================
# CORE ENDPOINTS
# ========================================
@app.route('/')
def index():
    return jsonify({
        'message': 'Celebration Backend API - Optimized',
        'status': 'running',
        'storage': {
            'cloudinary': 'enabled',
            'local_video_fallback': USE_LOCAL_VIDEO_STORAGE
        },
        'endpoints': {
            'health': '/api/health',
            'messages': '/api/messages',
            'gallery': '/api/gallery/folders',
            'donations': '/api/donations/create-intent',
            'stats': '/api/stats',
            'memories': '/api/memories',
            'videos': '/api/memories/videos',
            'past_memories': '/api/memories/past'
        }
    })

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
        total_size = 0
        
        for file in files:
            if file and file.filename:
                # Upload to Cloudinary with compression
                upload_result = upload_to_cloudinary(file, 'memories', is_video=False)
                
                if upload_result:
                    db.execute(
                        'INSERT INTO memories (name, caption, image_url, cloudinary_id, type, storage_type, file_size) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (name, caption, upload_result['url'], upload_result['public_id'], 'photo', 'cloudinary', upload_result['size'])
                    )
                    uploaded_count += 1
                    total_size += upload_result['size']
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'{uploaded_count} photo(s) uploaded successfully',
            'total_size': total_size
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/memories/videos', methods=['POST'])
def submit_video_memory():
    if 'videos[]' not in request.files:
        return jsonify({'success': False, 'message': 'No videos provided'}), 400
    
    name = request.form.get('name')
    caption = request.form.get('caption') or ''
    
    if not name:
        return jsonify({'success': False, 'message': 'Name required'}), 400
    
    try:
        db = get_db()
        files = request.files.getlist('videos[]')
        uploaded_count = 0
        storage_type = 'local' if USE_LOCAL_VIDEO_STORAGE else 'cloudinary'
        
        for file in files:
            if file and file.filename:
                # Check file size
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_VIDEO_SIZE:
                    continue  # Skip files over 50MB
                
                video_url = None
                public_id = None
                
                if USE_LOCAL_VIDEO_STORAGE:
                    # Save locally
                    video_url = save_video_locally(file, f"{datetime.now().timestamp()}_{file.filename}")
                    storage_type = 'local'
                else:
                    # Upload to Cloudinary
                    upload_result = upload_to_cloudinary(file, 'videos', is_video=True)
                    if upload_result:
                        video_url = upload_result['url']
                        public_id = upload_result['public_id']
                        file_size = upload_result['size']
                
                if video_url:
                    db.execute(
                        'INSERT INTO memories (name, caption, image_url, cloudinary_id, type, storage_type, file_size) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (name, caption, video_url, public_id, 'video', storage_type, file_size)
                    )
                    uploaded_count += 1
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'{uploaded_count} video(s) uploaded successfully',
            'storage': storage_type
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

@app.route('/api/memories/past', methods=['POST'])
def submit_past_memory():
    data = request.json
    
    if not data.get('message'):
        return jsonify({'success': False, 'message': 'Memory message required'}), 400
    
    try:
        db = get_db()
        db.execute(
            'INSERT INTO memories (name, caption, image_url, type) VALUES (?, ?, ?, ?)',
            (data.get('name') or 'Anonymous', data['message'], '', 'past')
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Past memory submitted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# DONATIONS ENDPOINTS
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
        # Get the origin from request headers to build redirect URLs
        origin = request.headers.get('Origin') or request.headers.get('Referer', '').rstrip('/')
        if not origin:
            origin = 'https://yoursite.com'  # Fallback
        
        # Build success and cancel URLs dynamically
        success_url = f"{origin}/charity?donation=success"
        cancel_url = f"{origin}/charity?donation=cancelled"
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'gbp',
                    'unit_amount': int(amount * 100),
                    'product_data': {
                        'name': f"Donation to {data.get('charity_name') or 'General Fund'}",
                        'description': 'Celebrating Abiye & Modupe'
                    }
                },
                'quantity': 1
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'donor_name': data.get('donor_name') or '',
                'donor_email': data.get('donor_email') or '',
                'charity_id': data.get('charity_id') or '',
                'charity_name': data.get('charity_name') or '',
                'message': data.get('message') or ''
            }
        )
        
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

# (Continue with remaining endpoints - webhook, cancellation, stats, health check)
# ... [Rest of the endpoints remain the same as original]

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
        
        return jsonify({
            'success': True,
            'message': 'Cancellation request received'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

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
        
        photo_count = db.execute("SELECT COUNT(*) as count FROM memories WHERE type = 'photo'").fetchone()['count']
        video_count = db.execute("SELECT COUNT(*) as count FROM memories WHERE type = 'video'").fetchone()['count']
        message_count = db.execute("SELECT COUNT(*) as count FROM messages").fetchone()['count']
        
        return jsonify({
            'success': True,
            'stats': {
                'total_raised': total_raised,
                'donor_count': donor_count,
                'goal': 10000,
                'photo_count': photo_count,
                'video_count': video_count,
                'message_count': message_count
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'storage': {
            'cloudinary': 'enabled',
            'local_videos': USE_LOCAL_VIDEO_STORAGE
        }
    })

# ========================================
# INITIALIZATION
# ========================================
if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(debug=os.getenv('DEBUG', 'False') == 'True', host='0.0.0.0', port=port)

if os.getenv('RAILWAY_ENVIRONMENT'):
    try:
        init_db()
    except:
        pass