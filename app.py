"""
Celebration Website Backend - POSTGRESQL VERSION
Flask + PostgreSQL + Stripe + Cloudinary
Complete with all fixes for photo/video uploads + automatic database migrations
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import stripe
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
from PIL import Image
import io
import json
import requests
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": False
    }
})

# ========================================
# CONFIGURATION
# ========================================
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
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
# DATABASE SETUP - POSTGRESQL
# ========================================
def get_db():
    """Connect to PostgreSQL using parsed DATABASE_URL"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Parse URL
    parsed = urlparse(db_url)
    if parsed.scheme not in ('postgres', 'postgresql'):
        raise ValueError(f"Invalid database URL scheme: {parsed.scheme}")

    # Extract query parameters
    query = parse_qs(parsed.query)
    sslmode = query.get('sslmode', ['prefer'])[0]

    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password,
        sslmode=sslmode,
        cursor_factory=RealDictCursor
    )
    return conn

def init_db():
    """Initialize database tables"""
    db = get_db()
    cursor = db.cursor()
    
    # Messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            relationship TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Memories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY,
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id SERIAL PRIMARY KEY,
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cancellations (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            request_type TEXT NOT NULL,
            number_of_guests INTEGER,
            reason TEXT NOT NULL,
            zoom_interest BOOLEAN DEFAULT FALSE,
            future_updates BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Gallery folders metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery_folders (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            icon TEXT DEFAULT 'fa-folder',
            gradient TEXT DEFAULT 'folder-solo',
            description TEXT,
            image_count INTEGER DEFAULT 0
        )
    ''')
    
    # Gallery images
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery_images (
            id SERIAL PRIMARY KEY,
            folder_name TEXT NOT NULL,
            image_url TEXT NOT NULL,
            cloudinary_id TEXT,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (folder_name) REFERENCES gallery_folders(name)
        )
    ''')
    
    db.commit()
    cursor.close()
    db.close()
    print("✅ Database tables initialized")

def run_migrations():
    """Run database migrations automatically on startup"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        print("🔄 Checking for database migrations...")
        
        # Check existing columns in memories table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'memories'
        """)
        existing_columns = [row['column_name'] for row in cursor.fetchall()]
        
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
                except psycopg2.Error as e:
                    print(f"⚠️ Migration warning for {column_name}: {e}")
            else:
                print(f"ℹ️ Column '{column_name}' already exists - skipping")
        
        if migration_applied:
            db.commit()
            print("✅ Database migrations completed successfully!")
        else:
            print("✅ Database schema is up to date - no migrations needed")
        
        cursor.close()
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
        'message': 'Celebration Backend API - PostgreSQL Version with Auto-Migration',
        'status': 'running',
        'version': '3.0',
        'database': 'PostgreSQL',
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
        cursor = db.cursor()
        cursor.execute('SELECT * FROM gallery_folders ORDER BY display_name')
        folders = cursor.fetchall()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'folders': folders
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
        cursor = db.cursor()
        cursor.execute(
            'SELECT * FROM gallery_images WHERE folder_name = %s ORDER BY order_index',
            (folder_name,)
        )
        images = cursor.fetchall()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'images': images
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
        cursor = db.cursor()
        
        cursor.execute(
            'SELECT * FROM messages ORDER BY created_at DESC LIMIT %s OFFSET %s',
            (limit, offset)
        )
        messages = cursor.fetchall()
        
        cursor.execute('SELECT COUNT(*) as count FROM messages')
        total_row = cursor.fetchone()
        total = total_row['count'] if total_row else 0
        
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'messages': messages,
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
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO messages (name, relationship, message) VALUES (%s, %s, %s) RETURNING id',
            (data['name'], data.get('relationship', ''), data['message'])
        )
        result = cursor.fetchone()
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Message submitted successfully',
            'id': result['id']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/messages/<int:message_id>', methods=['DELETE', 'OPTIONS'])
def delete_message(message_id):
    """Delete a specific message"""
    
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Check if message exists
        cursor.execute('SELECT * FROM messages WHERE id = %s', (message_id,))
        message = cursor.fetchone()
        
        if not message:
            cursor.close()
            db.close()
            return jsonify({'success': False, 'message': 'Message not found'}), 404
        
        # Delete the message
        cursor.execute('DELETE FROM messages WHERE id = %s', (message_id,))
        db.commit()
        cursor.close()
        db.close()
        
        print(f"✅ Message {message_id} deleted successfully")
        
        return jsonify({
            'success': True,
            'message': 'Message deleted successfully'
        }), 200
        
    except Exception as e:
        print(f"Error deleting message {message_id}:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/messages/bulk-delete', methods=['POST', 'OPTIONS'])
def bulk_delete_messages():
    """Delete multiple messages at once"""
    
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    data = request.json
    
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': 'No IDs provided'}), 400
    
    message_ids = data['ids']
    
    if not isinstance(message_ids, list) or len(message_ids) == 0:
        return jsonify({'success': False, 'message': 'Invalid IDs format'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Delete messages using ANY operator for array matching
        cursor.execute(
            'DELETE FROM messages WHERE id = ANY(%s)',
            (message_ids,)
        )
        deleted_count = cursor.rowcount
        db.commit()
        cursor.close()
        db.close()
        
        print(f"✅ Bulk deleted {deleted_count} messages")
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} messages',
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        print(f"Bulk delete messages error:", str(e))
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
        cursor = db.cursor()
        
        if memory_type == 'all':
            cursor.execute(
                'SELECT * FROM memories ORDER BY created_at DESC LIMIT %s OFFSET %s',
                (limit, offset)
            )
        else:
            cursor.execute(
                'SELECT * FROM memories WHERE type = %s ORDER BY created_at DESC LIMIT %s OFFSET %s',
                (memory_type, limit, offset)
            )
        
        memories = cursor.fetchall()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'memories': memories
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/memories/photos', methods=['POST', 'OPTIONS'])
def submit_photo_memory():
    """Upload photo memories with size validation and compression"""
    
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    if 'photos[]' not in request.files:
        return jsonify({'success': False, 'message': 'No photos provided'}), 400
    
    name = request.form.get('name')
    caption = request.form.get('caption', '')
    
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        files = request.files.getlist('photos[]')
        
        if not files or len(files) == 0:
            cursor.close()
            db.close()
            return jsonify({'success': False, 'message': 'No valid photos found'}), 400
        
        uploaded_count = 0
        total_size = 0
        errors = []
        
        for file in files:
            if not file or not file.filename:
                continue
            
            # Check file size (5MB limit)
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            
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
                file.seek(0)
                
                # Upload to Cloudinary with compression
                upload_result = upload_to_cloudinary_from_bytes(file_data, 'memories', is_video=False)
                
                if upload_result:
                    # Store in database
                    cursor.execute(
                        '''INSERT INTO memories 
                        (name, caption, image_url, cloudinary_id, type, storage_type, file_size) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                        (name, caption, upload_result['url'], upload_result['public_id'], 
                         'photo', 'cloudinary', upload_result['size'])
                    )
                    uploaded_count += 1
                    total_size += upload_result['size']
                else:
                    errors.append(f"Failed to upload {file.filename}")
                    
            except Exception as e:
                print(f"Error processing {file.filename}: {str(e)}")
                errors.append(f"Error with {file.filename}: {str(e)}")
        
        db.commit()
        cursor.close()
        db.close()
        
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
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/memories/videos', methods=['POST', 'OPTIONS'])
def submit_video_memory():
    """Upload video memories with size validation"""
    
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    if 'videos[]' not in request.files:
        return jsonify({'success': False, 'message': 'No videos provided'}), 400
    
    name = request.form.get('name')
    caption = request.form.get('caption', '')
    
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        files = request.files.getlist('videos[]')
        
        if not files or len(files) == 0:
            cursor.close()
            db.close()
            return jsonify({'success': False, 'message': 'No valid videos found'}), 400
        
        uploaded_count = 0
        errors = []
        storage_type = 'local' if USE_LOCAL_VIDEO_STORAGE else 'cloudinary'
        
        for file in files:
            if not file or not file.filename:
                continue
            
            # Check file size (50MB limit)
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
                    
                    upload_result = upload_to_cloudinary_from_bytes(file_data, 'videos', is_video=True)
                    
                    if upload_result:
                        video_url = upload_result['url']
                        public_id = upload_result['public_id']
                        file_size = upload_result['size']
                    else:
                        errors.append(f"Failed to upload {file.filename}")
                        continue
                
                if video_url:
                    cursor.execute(
                        '''INSERT INTO memories 
                        (name, caption, image_url, cloudinary_id, type, storage_type, file_size) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                        (name, caption, video_url, public_id, 'video', storage_type, file_size)
                    )
                    uploaded_count += 1
                    
            except Exception as e:
                print(f"Error processing {file.filename}: {str(e)}")
                errors.append(f"Error with {file.filename}: {str(e)}")
        
        db.commit()
        cursor.close()
        db.close()
        
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
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/memories/text', methods=['POST'])
def submit_text_memory():
    data = request.json
    
    if not data.get('name') or not data.get('message'):
        return jsonify({'success': False, 'message': 'Name and message required'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO memories (name, caption, image_url, type) VALUES (%s, %s, %s, %s)',
            (data['name'], data['message'], '', 'text')
        )
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Memory submitted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/memories/past', methods=['POST'])
def submit_past_memory():
    data = request.json
    
    if not data.get('message'):
        return jsonify({'success': False, 'message': 'Memory message required'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO memories (name, caption, image_url, type) VALUES (%s, %s, %s, %s)',
            (data.get('name') or 'Anonymous', data['message'], '', 'past')
        )
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Past memory submitted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/memories/<int:memory_id>', methods=['DELETE', 'OPTIONS'])
def delete_memory(memory_id):
    """Delete a specific memory (photo or video)"""
    
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Check if memory exists
        cursor.execute('SELECT * FROM memories WHERE id = %s', (memory_id,))
        memory = cursor.fetchone()
        
        if not memory:
            cursor.close()
            db.close()
            return jsonify({'success': False, 'message': 'Memory not found'}), 404
        
        # Delete from Cloudinary if it has a cloudinary_id
        if memory['cloudinary_id']:
            try:
                resource_type = 'video' if memory['type'] == 'video' else 'image'
                cloudinary.uploader.destroy(memory['cloudinary_id'], resource_type=resource_type)
                print(f"✅ Deleted from Cloudinary: {memory['cloudinary_id']}")
            except Exception as e:
                print(f"⚠️ Cloudinary deletion warning: {e}")
        
        # Delete from local storage if it's stored locally
        if memory['storage_type'] == 'local' and memory['image_url']:
            try:
                filename = memory['image_url'].split('/')[-1]
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"✅ Deleted local file: {filepath}")
            except Exception as e:
                print(f"⚠️ Local file deletion warning: {e}")
        
        # Delete from database
        cursor.execute('DELETE FROM memories WHERE id = %s', (memory_id,))
        db.commit()
        cursor.close()
        db.close()
        
        print(f"✅ Memory {memory_id} ({memory['type']}) deleted successfully")
        
        return jsonify({
            'success': True,
            'message': f"{memory['type'].capitalize()} deleted successfully"
        }), 200
        
    except Exception as e:
        print(f"Error deleting memory {memory_id}:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/memories/bulk-delete', methods=['POST', 'OPTIONS'])
def bulk_delete_memories():
    """Delete multiple memories at once"""
    
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    data = request.json
    
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': 'No IDs provided'}), 400
    
    memory_ids = data['ids']
    
    if not isinstance(memory_ids, list) or len(memory_ids) == 0:
        return jsonify({'success': False, 'message': 'Invalid IDs format'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        deleted_count = 0
        errors = []
        
        for memory_id in memory_ids:
            try:
                # Get memory info
                cursor.execute('SELECT * FROM memories WHERE id = %s', (memory_id,))
                memory = cursor.fetchone()
                
                if not memory:
                    errors.append(f"Memory {memory_id} not found")
                    continue
                
                # Delete from Cloudinary
                if memory['cloudinary_id']:
                    try:
                        resource_type = 'video' if memory['type'] == 'video' else 'image'
                        cloudinary.uploader.destroy(memory['cloudinary_id'], resource_type=resource_type)
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
                cursor.execute('DELETE FROM memories WHERE id = %s', (memory_id,))
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Error deleting memory {memory_id}: {str(e)}")
        
        db.commit()
        cursor.close()
        db.close()
        
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
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO donations (donor_name, donor_email, amount, charity_id, charity_name, message, stripe_payment_id, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
            (data.get('donor_name'), data.get('donor_email'), amount, data.get('charity_id'), 
             data.get('charity_name'), data.get('message'), session.id, 'pending')
        )
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'checkout_url': session.url})
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
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
            print("⚠️ WARNING: Processing webhook without signature verification!")
        
        print(f"📨 Received webhook event: {event['type']}")
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "UPDATE donations SET status = 'completed' WHERE stripe_payment_id = %s",
                (session['id'],)
            )
            affected = cursor.rowcount
            db.commit()
            cursor.close()
            db.close()
            
            if affected > 0:
                print(f"✅ Donation completed: {session['id']}")
            else:
                print(f"⚠️ No donation found with ID: {session['id']}")
            
        elif event['type'] == 'checkout.session.expired':
            session = event['data']['object']
            
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "UPDATE donations SET status = 'failed' WHERE stripe_payment_id = %s",
                (session['id'],)
            )
            db.commit()
            cursor.close()
            db.close()
            
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
        cursor = db.cursor()
        cursor.execute(
            '''INSERT INTO cancellations 
            (first_name, last_name, email, phone, request_type, number_of_guests, reason, zoom_interest, future_updates) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (data['firstName'], data['lastName'], data['email'], 
             data.get('phone') or '', data['requestType'], 
             data.get('numberOfGuests') or 0, data['reason'],
             data.get('zoomInterest') or False, data.get('futureUpdates') or False)
        )
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Cancellation request received'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================================
# STATS ENDPOINT
# ========================================
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT SUM(amount) as total FROM donations WHERE status = 'completed'"
        )
        total_row = cursor.fetchone()
        total_raised = total_row['total'] if total_row and total_row['total'] else 0
        
        cursor.execute(
            "SELECT COUNT(DISTINCT donor_email) as count FROM donations WHERE status = 'completed'"
        )
        donor_row = cursor.fetchone()
        donor_count = donor_row['count'] if donor_row else 0
        
        cursor.execute("SELECT COUNT(*) as count FROM memories WHERE type = 'photo'")
        photo_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM memories WHERE type = 'video'")
        video_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM messages")
        message_count = cursor.fetchone()['count']
        
        cursor.close()
        db.close()
        
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

# ========================================
# GOOGLE DRIVE CONFIGURATION
# ========================================
DRIVE_FOLDER_ID = '1F4qa0G07v7uTF-P95kdWRilG8k2anknm'
DRIVE_API_KEY = os.getenv('GOOGLE_DRIVE_API_KEY')

def get_drive_folder_structure(folder_id):
    """Fetch folder structure from Google Drive with error handling"""
    if not DRIVE_API_KEY:
        print("❌ GOOGLE_DRIVE_API_KEY not configured")
        return []
    
    try:
        url = 'https://www.googleapis.com/drive/v3/files'
        params = {
            'q': f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
            'key': DRIVE_API_KEY,
            'fields': 'files(id,name,createdTime)',
            'orderBy': 'name'
        }
        
        print(f"📁 Fetching Drive folders from: {folder_id}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        folders = response.json().get('files', [])
        print(f"✅ Found {len(folders)} folders")
        return folders
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"❌ Drive API Error 403: Check API key and folder permissions")
        else:
            print(f"❌ Drive API HTTP Error: {e}")
        return []
    except Exception as e:
        print(f"❌ Drive API error: {e}")
        return []

def get_drive_folder_images(folder_id):
    """Fetch image files from a Drive folder with error handling"""
    if not DRIVE_API_KEY:
        print("❌ GOOGLE_DRIVE_API_KEY not configured")
        return []
    
    try:
        url = 'https://www.googleapis.com/drive/v3/files'
        params = {
            'q': f"'{folder_id}' in parents and (mimeType contains 'image/' or name contains '.heic' or name contains '.HEIC')",
            'key': DRIVE_API_KEY,
            'fields': 'files(id,name,thumbnailLink,webContentLink,createdTime,size,mimeType)',
            'pageSize': 1000,
            'orderBy': 'createdTime'
        }
        
        print(f"🖼️  Fetching images from folder: {folder_id}")
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        files = response.json().get('files', [])
        
        # Convert to direct image URLs with thumbnail support
        for file in files:
            # Use direct view URL for images
            file['imageUrl'] = f"https://drive.google.com/uc?export=view&id={file['id']}"
            
            # Use thumbnail if available, otherwise use main image
            if file.get('thumbnailLink'):
                # Increase thumbnail size for better quality
                file['thumbnailUrl'] = file['thumbnailLink'].replace('=s220', '=s400')
            else:
                file['thumbnailUrl'] = file['imageUrl']
        
        print(f"✅ Found {len(files)} images")
        return files
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"❌ Drive API Error 403: Check API key and folder permissions")
        else:
            print(f"❌ Drive API HTTP Error: {e}")
        return []
    except Exception as e:
        print(f"❌ Drive images API error: {e}")
        return []

# ========================================
# GOOGLE DRIVE GALLERY ENDPOINTS
# ========================================
@app.route('/api/gallery/drive/folders', methods=['GET'])
def get_drive_folders():
    """Get all folders from Google Drive"""
    
    # Check if API key is configured
    if not DRIVE_API_KEY:
        return jsonify({
            'success': False,
            'message': 'Google Drive API key not configured. Please add GOOGLE_DRIVE_API_KEY to environment variables.'
        }), 500
    
    try:
        folders = get_drive_folder_structure(DRIVE_FOLDER_ID)
        
        if not folders:
            return jsonify({
                'success': True,
                'folders': [],
                'message': 'No folders found. Check folder ID and permissions.'
            })
        
        # Enhance with image counts and metadata
        enhanced_folders = []
        for folder in folders:
            images = get_drive_folder_images(folder['id'])
            
            enhanced_folder = {
                'id': folder['id'],
                'name': folder['name'],
                'imageCount': len(images),
                'gradient': 'folder-solo',
                'icon': 'fa-folder',
                'description': f"{len(images)} memories",
                'createdTime': folder.get('createdTime', '')
            }
            enhanced_folders.append(enhanced_folder)
        
        return jsonify({
            'success': True,
            'folders': enhanced_folders,
            'total': len(enhanced_folders)
        })
        
    except Exception as e:
        print(f"❌ Error in get_drive_folders: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to fetch folders: {str(e)}'
        }), 500

@app.route('/api/gallery/drive/images', methods=['GET'])
def get_drive_images():
    """Get images from a specific Drive folder"""
    folder_id = request.args.get('folderId')
    
    if not folder_id:
        return jsonify({
            'success': False,
            'message': 'Folder ID required'
        }), 400
    
    if not DRIVE_API_KEY:
        return jsonify({
            'success': False,
            'message': 'Google Drive API key not configured'
        }), 500
    
    try:
        images = get_drive_folder_images(folder_id)
        
        return jsonify({
            'success': True,
            'images': images,
            'total': len(images)
        })
        
    except Exception as e:
        print(f"❌ Error in get_drive_images: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to fetch images: {str(e)}'
        }), 500

@app.route('/api/gallery/drive/sync', methods=['POST'])
def sync_drive_gallery():
    """Cache Drive folder structure in database for faster loading (optional)"""
    
    if not DRIVE_API_KEY:
        return jsonify({
            'success': False,
            'message': 'Google Drive API key not configured'
        }), 500
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Clear existing cache
        cursor.execute('DELETE FROM gallery_images WHERE folder_name LIKE %s', ('drive_%',))
        cursor.execute('DELETE FROM gallery_folders WHERE name LIKE %s', ('drive_%',))
        
        # Fetch and cache folders
        folders = get_drive_folder_structure(DRIVE_FOLDER_ID)
        
        synced_folders = 0
        synced_images = 0
        
        for folder in folders:
            folder_key = f"drive_{folder['id']}"
            
            # Insert folder
            cursor.execute(
                '''INSERT INTO gallery_folders (name, display_name, icon, gradient, description, image_count)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (name) DO UPDATE SET
                   display_name = EXCLUDED.display_name,
                   image_count = EXCLUDED.image_count''',
                (folder_key, folder['name'], 'fa-folder', 'folder-solo', '', 0)
            )
            
            # Fetch and cache images
            images = get_drive_folder_images(folder['id'])
            
            for idx, img in enumerate(images):
                cursor.execute(
                    '''INSERT INTO gallery_images (folder_name, image_url, cloudinary_id, order_index)
                       VALUES (%s, %s, %s, %s)''',
                    (folder_key, img['imageUrl'], img['id'], idx)
                )
                synced_images += 1
            
            # Update image count
            cursor.execute(
                'UPDATE gallery_folders SET image_count = %s WHERE name = %s',
                (len(images), folder_key)
            )
            
            synced_folders += 1
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'message': f'Synced {synced_folders} folders and {synced_images} images from Google Drive',
            'folders': synced_folders,
            'images': synced_images
        })
        
    except Exception as e:
        print(f"❌ Error in sync_drive_gallery: {e}")
        return jsonify({
            'success': False,
            'message': f'Sync failed: {str(e)}'
        }), 500

# ========================================
# HEALTH CHECK
# ========================================
@app.route('/api/health', methods=['GET'])
def health_check():
    # Check database
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        cursor.close()
        db.close()
        db_status = 'healthy'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    # Check Google Drive API
    drive_status = 'not_configured'
    if DRIVE_API_KEY:
        try:
            # Test API with a simple request
            folders = get_drive_folder_structure(DRIVE_FOLDER_ID)
            if folders is not None:
                drive_status = f'healthy ({len(folders)} folders)'
            else:
                drive_status = 'error: could not fetch folders'
        except Exception as e:
            drive_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': {
            'status': db_status,
            'type': 'PostgreSQL',
            'url_configured': bool(os.getenv('DATABASE_URL'))
        },
        'storage': {
            'cloudinary': {
                'configured': bool(os.getenv('CLOUDINARY_CLOUD_NAME')),
                'status': 'enabled' if os.getenv('CLOUDINARY_CLOUD_NAME') else 'not_configured'
            },
            'local_videos': USE_LOCAL_VIDEO_STORAGE,
            'google_drive': {
                'configured': bool(DRIVE_API_KEY),
                'status': drive_status,
                'folder_id': DRIVE_FOLDER_ID
            }
        },
        'stripe': {
            'configured': bool(stripe.api_key),
            'webhook_secret': bool(STRIPE_WEBHOOK_SECRET)
        },
        'environment_variables': {
            'DATABASE_URL': bool(os.getenv('DATABASE_URL')),
            'GOOGLE_DRIVE_API_KEY': bool(DRIVE_API_KEY),
            'CLOUDINARY_CLOUD_NAME': bool(os.getenv('CLOUDINARY_CLOUD_NAME')),
            'STRIPE_SECRET_KEY': bool(stripe.api_key),
            'SECRET_KEY': bool(app.config['SECRET_KEY'])
        }
    })

# ========================================
# INITIALIZATION WITH AUTO-MIGRATION
# ========================================
# Development entry point (not used on Railway)
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

# Initialize database and run migrations when running on Railway
if os.getenv('RAILWAY_ENVIRONMENT'):
    try:
        init_db()
        run_migrations()
        print("✅ Database initialized and migrated on Railway")
    except Exception as e:
        print(f"⚠️ Database initialization error: {e}")