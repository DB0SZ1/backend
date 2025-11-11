"""
Celebration Website Backend - FIXED VERSION with AUTO-MIGRATION
Flask + SQLite3 + Stripe + Cloudinary
Complete with all fixes for photo/video uploads + automatic database migrations
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
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": False
    }
})

# ========================================
# CONFIGURATION
# ========================================
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['DATABASE'] = 'celebration.db'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max request size
app.config['UPLOAD_FOLDER'] = 'uploads/videos'

# File size limits
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB for Cloudinary free tier
USE_LOCAL_VIDEO_STORAGE = os.getenv('USE_LOCAL_VIDEO_STORAGE', 'false').lower() == 'true'

# Create upload folder
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
    
    # Memories table
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

def run_migrations():
    """Run database migrations automatically on startup"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        print("🔄 Checking for database migrations...")
        
        # Check existing columns in memories table
        cursor.execute("PRAGMA table_info(memories)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # Define columns that should exist
        columns_to_add = [
            ("storage_type", "TEXT DEFAULT 'cloudinary'"),
            ("file_size", "INTEGER")
        ]
        
        migration_applied = False
        
        # Add missing columns
        for column_name, column_def in columns_to_add:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE memories ADD COLUMN {column_name} {column_def}")
                    print(f"✅ Migration: Added column '{column_name}' to memories table")
                    migration_applied = True
                except sqlite3.Error as e:
                    print(f"⚠️ Migration warning for {column_name}: {e}")
            else:
                print(f"ℹ️ Column '{column_name}' already exists - skipping")
        
        if migration_applied:
            db.commit()
            print("✅ Database migrations completed successfully!")
        else:
            print("✅ Database schema is up to date - no migrations needed")
        
        db.close()
        
    except Exception as e:
        print(f"⚠️ Migration error: {e}")

# ========================================
# HELPER FUNCTIONS - FIXED
# ========================================
def compress_image(file_bytes, max_width=1200, quality=75):
    """
    Compress image from bytes data
    Returns: BytesIO object with compressed image
    """
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(file_bytes))
        
        # Convert RGBA to RGB
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

def upload_to_cloudinary_from_bytes(file_bytes, folder='memories', is_video=False):
    """
    Upload file to Cloudinary from bytes data
    Returns: dict with url, public_id, and size
    """
    try:
        if is_video:
            # Video upload - wrap bytes in BytesIO
            file_stream = io.BytesIO(file_bytes)
            result = cloudinary.uploader.upload(
                file_stream,
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
            # Image upload - compress first
            compressed = compress_image(file_bytes)
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
    """Save video to local storage as fallback"""
    try:
        filename = secure_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
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
        'message': 'Celebration Backend API - Fixed & Optimized with Auto-Migration',
        'status': 'running',
        'version': '2.1',
        'storage': {
            'cloudinary': 'enabled',
            'local_video_fallback': USE_LOCAL_VIDEO_STORAGE
        },
        'endpoints': {
            'health': '/api/health',
            'messages': '/api/messages',
            'gallery': '/api/gallery/folders',
            'donations': '/api/donations/create-intent',
            'webhook': '/api/stripe/webhook',
            'stats': '/api/stats',
            'memories': '/api/memories',
            'photos': '/api/memories/photos',
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
# MEMORIES ENDPOINTS - FIXED
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

@app.route('/api/memories/photos', methods=['POST', 'OPTIONS'])
def submit_photo_memory():
    """Upload photo memories with size validation and compression"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    # Validate files exist
    if 'photos[]' not in request.files:
        return jsonify({
            'success': False, 
            'message': 'No photos provided'
        }), 400
    
    name = request.form.get('name')
    caption = request.form.get('caption', '')
    
    if not name:
        return jsonify({
            'success': False, 
            'message': 'Name is required'
        }), 400
    
    try:
        db = get_db()
        files = request.files.getlist('photos[]')
        
        if not files or len(files) == 0:
            return jsonify({
                'success': False,
                'message': 'No valid photos found'
            }), 400
        
        uploaded_count = 0
        total_size = 0
        errors = []
        
        for file in files:
            if not file or not file.filename:
                continue
            
            # Check file size BEFORE processing (5MB limit)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > MAX_IMAGE_SIZE:
                errors.append(f"{file.filename} exceeds 5MB limit")
                continue
            
            # Validate file type
            if not file.content_type.startswith('image/'):
                errors.append(f"{file.filename} is not an image")
                continue
            
            try:
                # Read file data
                file_data = file.read()
                file.seek(0)  # Reset for potential re-read
                
                # Upload to Cloudinary with compression
                upload_result = upload_to_cloudinary_from_bytes(
                    file_data, 
                    'memories', 
                    is_video=False
                )
                
                if upload_result:
                    # Store in database
                    db.execute(
                        '''INSERT INTO memories 
                        (name, caption, image_url, cloudinary_id, type, storage_type, file_size) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (
                            name, 
                            caption, 
                            upload_result['url'], 
                            upload_result['public_id'], 
                            'photo', 
                            'cloudinary', 
                            upload_result['size']
                        )
                    )
                    uploaded_count += 1
                    total_size += upload_result['size']
                else:
                    errors.append(f"Failed to upload {file.filename}")
                    
            except Exception as e:
                print(f"Error processing {file.filename}: {str(e)}")
                errors.append(f"Error with {file.filename}: {str(e)}")
        
        db.commit()
        
        # Build response message
        if uploaded_count > 0:
            message = f'{uploaded_count} photo(s) uploaded successfully'
            if errors:
                message += f' ({len(errors)} failed)'
            
            return jsonify({
                'success': True,
                'message': message,
                'uploaded': uploaded_count,
                'total_size': total_size,
                'errors': errors if errors else None
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'No photos could be uploaded',
                'errors': errors
            }), 400
            
    except Exception as e:
        print(f"Photo upload error: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/memories/videos', methods=['POST', 'OPTIONS'])
def submit_video_memory():
    """Upload video memories with size validation"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    if 'videos[]' not in request.files:
        return jsonify({
            'success': False, 
            'message': 'No videos provided'
        }), 400
    
    name = request.form.get('name')
    caption = request.form.get('caption', '')
    
    if not name:
        return jsonify({
            'success': False, 
            'message': 'Name is required'
        }), 400
    
    try:
        db = get_db()
        files = request.files.getlist('videos[]')
        
        if not files or len(files) == 0:
            return jsonify({
                'success': False,
                'message': 'No valid videos found'
            }), 400
        
        uploaded_count = 0
        errors = []
        storage_type = 'local' if USE_LOCAL_VIDEO_STORAGE else 'cloudinary'
        
        for file in files:
            if not file or not file.filename:
                continue
            
            # Check file size (50MB limit for Cloudinary free tier)
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > MAX_VIDEO_SIZE:
                errors.append(f"{file.filename} exceeds 50MB limit")
                continue
            
            # Validate file type
            if not file.content_type.startswith('video/'):
                errors.append(f"{file.filename} is not a video")
                continue
            
            try:
                video_url = None
                public_id = None
                
                if USE_LOCAL_VIDEO_STORAGE:
                    # Save locally
                    timestamp = datetime.now().timestamp()
                    safe_filename = secure_filename(file.filename)
                    video_url = save_video_locally(file, f"{timestamp}_{safe_filename}")
                    storage_type = 'local'
                else:
                    # Upload to Cloudinary
                    file_data = file.read()
                    file.seek(0)
                    
                    upload_result = upload_to_cloudinary_from_bytes(
                        file_data, 
                        'videos', 
                        is_video=True
                    )
                    
                    if upload_result:
                        video_url = upload_result['url']
                        public_id = upload_result['public_id']
                        file_size = upload_result['size']
                    else:
                        errors.append(f"Failed to upload {file.filename}")
                        continue
                
                if video_url:
                    db.execute(
                        '''INSERT INTO memories 
                        (name, caption, image_url, cloudinary_id, type, storage_type, file_size) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (name, caption, video_url, public_id, 'video', storage_type, file_size)
                    )
                    uploaded_count += 1
                    
            except Exception as e:
                print(f"Error processing {file.filename}: {str(e)}")
                errors.append(f"Error with {file.filename}: {str(e)}")
        
        db.commit()
        
        if uploaded_count > 0:
            message = f'{uploaded_count} video(s) uploaded successfully'
            if errors:
                message += f' ({len(errors)} failed)'
            
            return jsonify({
                'success': True,
                'message': message,
                'uploaded': uploaded_count,
                'storage': storage_type,
                'errors': errors if errors else None
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'No videos could be uploaded',
                'errors': errors
            }), 400
            
    except Exception as e:
        print(f"Video upload error: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Server error: {str(e)}'
        }), 500

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
        origin = request.headers.get('Origin') or request.headers.get('Referer', '').rstrip('/')
        if not origin:
            origin = 'https://yoursite.com'
        
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
            'INSERT INTO donations (donor_name, donor_email, amount, charity_id, charity_name, message, stripe_payment_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('donor_name'), data.get('donor_email'), amount, data.get('charity_id'), data.get('charity_name'), data.get('message'), session.id, 'pending')
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'checkout_url': session.url
        })
    except Exception as e:
        print(f"Payment intent error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        else:
            event = json.loads(payload)
            print("⚠️ WARNING: Processing webhook without signature verification!")
        
        print(f"📨 Received webhook event: {event['type']}")
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            db = get_db()
            result = db.execute(
                "UPDATE donations SET status = 'completed' WHERE stripe_payment_id = ?",
                (session['id'],)
            )
            db.commit()
            
            if result.rowcount > 0:
                print(f"✅ Donation completed: {session['id']}")
            else:
                print(f"⚠️ No donation found with ID: {session['id']}")
            
        elif event['type'] == 'checkout.session.expired':
            session = event['data']['object']
            
            db = get_db()
            db.execute(
                "UPDATE donations SET status = 'failed' WHERE stripe_payment_id = ?",
                (session['id'],)
            )
            db.commit()
            
            print(f"❌ Donation expired: {session['id']}")
        
        return jsonify({'success': True}), 200
        
    except ValueError as e:
        print(f"⚠️ Webhook error - Invalid payload: {e}")
        return jsonify({'success': False, 'error': 'Invalid payload'}), 400
        
    except stripe.error.SignatureVerificationError as e:
        print(f"⚠️ Webhook error - Invalid signature: {e}")
        return jsonify({'success': False, 'error': 'Invalid signature'}), 400
        
    except Exception as e:
        print(f"⚠️ Webhook error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
        
        photo_count = db.execute("SELECT COUNT(*) as count FROM memories WHERE type = 'photo'").fetchone()['count']
        video_count = db.execute("SELECT COUNT(*) as count FROM memories WHERE type = 'video'").fetchone()['count']
        message_count = db.execute("SELECT COUNT(*) as count FROM messages").fetchone()['count']
        
        return jsonify({
            'success': True,
            'stats': {
                'total_raised': float(total_raised),
                'donor_count': donor_count,
                'goal': 10000,
                'photo_count': photo_count,
                'video_count': video_count,
                'message_count': message_count
            }
        })
    except Exception as e:
        print(f"Stats error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/messages/<int:message_id>', methods=['DELETE', 'OPTIONS'])
def delete_message(message_id):
    """Delete a specific message"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        db = get_db()
        
        # Check if message exists
        message = db.execute(
            'SELECT * FROM messages WHERE id = ?',
            (message_id,)
        ).fetchone()
        
        if not message:
            return jsonify({
                'success': False,
                'message': 'Message not found'
            }), 404
        
        # Delete the message
        db.execute('DELETE FROM messages WHERE id = ?', (message_id,))
        db.commit()
        
        print(f"✅ Message {message_id} deleted successfully")
        
        return jsonify({
            'success': True,
            'message': 'Message deleted successfully'
        }), 200
        
    except Exception as e:
        print(f"Error deleting message {message_id}:", str(e))
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/memories/<int:memory_id>', methods=['DELETE', 'OPTIONS'])
def delete_memory(memory_id):
    """Delete a specific memory (photo or video)"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        db = get_db()
        
        # Check if memory exists
        memory = db.execute(
            'SELECT * FROM memories WHERE id = ?',
            (memory_id,)
        ).fetchone()
        
        if not memory:
            return jsonify({
                'success': False,
                'message': 'Memory not found'
            }), 404
        
        # Delete from Cloudinary if it has a cloudinary_id
        if memory['cloudinary_id']:
            try:
                resource_type = 'video' if memory['type'] == 'video' else 'image'
                cloudinary.uploader.destroy(
                    memory['cloudinary_id'],
                    resource_type=resource_type
                )
                print(f"✅ Deleted from Cloudinary: {memory['cloudinary_id']}")
            except Exception as e:
                print(f"⚠️ Cloudinary deletion warning: {e}")
                # Continue with database deletion even if Cloudinary fails
        
        # Delete from local storage if it's stored locally
        if memory['storage_type'] == 'local' and memory['image_url']:
            try:
                # Extract filename from URL
                filename = memory['image_url'].split('/')[-1]
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"✅ Deleted local file: {filepath}")
            except Exception as e:
                print(f"⚠️ Local file deletion warning: {e}")
        
        # Delete from database
        db.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
        db.commit()
        
        print(f"✅ Memory {memory_id} ({memory['type']}) deleted successfully")
        
        return jsonify({
            'success': True,
            'message': f"{memory['type'].capitalize()} deleted successfully"
        }), 200
        
    except Exception as e:
        print(f"Error deleting memory {memory_id}:", str(e))
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/memories/bulk-delete', methods=['POST', 'OPTIONS'])
def bulk_delete_memories():
    """Delete multiple memories at once"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    data = request.json
    
    if not data or 'ids' not in data:
        return jsonify({
            'success': False,
            'message': 'No IDs provided'
        }), 400
    
    memory_ids = data['ids']
    
    if not isinstance(memory_ids, list) or len(memory_ids) == 0:
        return jsonify({
            'success': False,
            'message': 'Invalid IDs format'
        }), 400
    
    try:
        db = get_db()
        deleted_count = 0
        errors = []
        
        for memory_id in memory_ids:
            try:
                # Get memory info
                memory = db.execute(
                    'SELECT * FROM memories WHERE id = ?',
                    (memory_id,)
                ).fetchone()
                
                if not memory:
                    errors.append(f"Memory {memory_id} not found")
                    continue
                
                # Delete from Cloudinary
                if memory['cloudinary_id']:
                    try:
                        resource_type = 'video' if memory['type'] == 'video' else 'image'
                        cloudinary.uploader.destroy(
                            memory['cloudinary_id'],
                            resource_type=resource_type
                        )
                    except Exception as e:
                        print(f"⚠️ Cloudinary deletion warning for {memory_id}: {e}")
                
                # Delete from local storage
                if memory['storage_type'] == 'local' and memory['image_url']:
                    try:
                        filename = memory['image_url'].split('/')[-1]
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    except Exception as e:
                        print(f"⚠️ Local file deletion warning for {memory_id}: {e}")
                
                # Delete from database
                db.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Error deleting memory {memory_id}: {str(e)}")
        
        db.commit()
        
        message = f"Successfully deleted {deleted_count} of {len(memory_ids)} memories"
        if errors:
            message += f". Errors: {'; '.join(errors)}"
        
        return jsonify({
            'success': True,
            'message': message,
            'deleted_count': deleted_count,
            'errors': errors if errors else None
        }), 200
        
    except Exception as e:
        print(f"Bulk delete error:", str(e))
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/messages/bulk-delete', methods=['POST', 'OPTIONS'])
def bulk_delete_messages():
    """Delete multiple messages at once"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    data = request.json
    
    if not data or 'ids' not in data:
        return jsonify({
            'success': False,
            'message': 'No IDs provided'
        }), 400
    
    message_ids = data['ids']
    
    if not isinstance(message_ids, list) or len(message_ids) == 0:
        return jsonify({
            'success': False,
            'message': 'Invalid IDs format'
        }), 400
    
    try:
        db = get_db()
        
        # Create placeholders for SQL query
        placeholders = ','.join('?' * len(message_ids))
        
        # Delete messages
        result = db.execute(
            f'DELETE FROM messages WHERE id IN ({placeholders})',
            message_ids
        )
        db.commit()
        
        deleted_count = result.rowcount
        
        print(f"✅ Bulk deleted {deleted_count} messages")
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} messages',
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        print(f"Bulk delete messages error:", str(e))
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ========================================
# HEALTH CHECK
# ========================================
@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        db = get_db()
        db.execute('SELECT 1').fetchone()
        db_status = 'healthy'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': db_status,
        'storage': {
            'cloudinary': 'enabled',
            'local_videos': USE_LOCAL_VIDEO_STORAGE
        },
        'stripe': {
            'configured': bool(stripe.api_key),
            'webhook_secret': bool(STRIPE_WEBHOOK_SECRET)
        }
    })

# ========================================
# INITIALIZATION WITH AUTO-MIGRATION
# ========================================
if __name__ == '__main__':
    init_db()
    run_migrations()
    port = int(os.getenv('PORT', 5000))
    app.run(debug=os.getenv('DEBUG', 'False') == 'True', host='0.0.0.0', port=port)

# Initialize database and run migrations when running on Railway
if os.getenv('RAILWAY_ENVIRONMENT'):
    try:
        init_db()
        run_migrations()
        print("✅ Database initialized and migrated on Railway")
    except Exception as e:
        print(f"⚠️ Database initialization error: {e}")