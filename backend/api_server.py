from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, send_file
from flask_cors import CORS
import os
import base64
import random
import time
import requests
import ffmpeg
import sqlite3
from mutagen.mp3 import MP3
from requests.exceptions import SSLError, Timeout, ProxyError, ConnectionError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import lru_cache
import jwt
from datetime import datetime, timedelta
import json
from database import DatabaseManager
import uuid
import schedule
import threading
from collections import defaultdict
import time

# Rate limiting: Track active requests per API key
active_requests = defaultdict(int)
request_lock = threading.Lock()

# Global rate limiting: Max 5 concurrent requests
MAX_CONCURRENT_REQUESTS = 5
global_semaphore = threading.Semaphore(MAX_CONCURRENT_REQUESTS)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
CORS(app)

# Initialize database
db = DatabaseManager()

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
WED_EXTENSIONS = {'mp3', 'wav', 'ogg'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# JWT Configuration
JWT_SECRET = 'jwt-secret-key-change-in-production'
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_DELTA = timedelta(hours=24)

# Performance optimizations
_session_cache = {}
_session_cache_timestamp = {}
SESSION_CACHE_TTL = 600  # Cache sessions for 10 minutes

def create_session_with_retry():
    """Create requests session with retry strategy and connection pooling"""
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    # Configure adapter with connection pooling
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=20
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def get_session(proxy_dict=None):
    """Get or create session with caching"""
    cache_key = str(proxy_dict) if proxy_dict else "default"
    current_time = time.time()
    
    # Check if cache is valid
    if (cache_key in _session_cache and 
        current_time - _session_cache_timestamp.get(cache_key, 0) < SESSION_CACHE_TTL):
        return _session_cache[cache_key]
    
    # Create new session
    session = create_session_with_retry()
    _session_cache[cache_key] = session
    _session_cache_timestamp[cache_key] = current_time
    
    return session

def get_audio_duration(file_path):
    """Get audio duration with better error handling"""
    try:
        return round(MP3(file_path).info.length, 2)
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return 0

def generate_jwt_token(user_data):
    """Generate JWT token for user"""
    payload = {
        'user_id': user_data['id'],
        'username': user_data['username'],
        'role': user_data['role'],
        'exp': datetime.utcnow() + JWT_EXPIRATION_DELTA
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        request.user = payload
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_admin(f):
    """Decorator to require admin role"""
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'user') or request.user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def log_failed_gemini_key(api_key, error_message):
    """Log failed Gemini key attempt (for debugging purposes)"""
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Update last_used timestamp even for failed attempts (for debugging)
        cursor.execute('''
            UPDATE gemini_keys 
            SET last_used = CURRENT_TIMESTAMP
            WHERE api_key = ?
        ''', (api_key,))
        
        conn.commit()
        conn.close()
        
        print(f"[FAILED] Logged failed attempt for key {api_key[:20]}: {error_message}")
        
    except Exception as e:
        print(f"[ERROR] Failed to log failed key attempt: {e}")

def gemini_tts_request(text, voice_name, api_key_list):
    def task(api_key):
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"
            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            }
            data = {
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice_name
                            }
                        }
                    }
                },
                "model": "gemini-2.5-flash-preview-tts",
            }

            session = get_session()
            response = session.post(url, headers=headers, json=data)
            
            if response.status_code == 429:
                # Quota exceeded - just raise exception without disabling key
                print(f"[QUOTA] Key {api_key[:20]} exceeded quota")
                raise Exception(f"Quota exceeded for key {api_key[:20]}")
            
            if response.status_code != 200:
                print(f"[ERROR] Key {api_key[:20]} failed with status {response.status_code}: {response.text[:200]}")
                raise Exception(f"HTTP Error {response.status_code} from Gemini: {response.text[:300]}")

            res_json = response.json()
            
            # Check if response has valid audio data
            if 'candidates' not in res_json or not res_json['candidates']:
                print(f"[ERROR] Key {api_key[:20]} returned invalid response structure")
                raise Exception("Invalid response structure from Gemini")
            
            candidate = res_json['candidates'][0]
            if 'content' not in candidate or 'parts' not in candidate['content']:
                print(f"[ERROR] Key {api_key[:20]} returned invalid content structure")
                raise Exception("Invalid content structure from Gemini")
            
            audio_data = candidate['content']['parts'][0]['inlineData']['data']
            
            if not audio_data:
                print(f"[ERROR] Key {api_key[:20]} returned empty audio data")
                raise Exception("Empty audio data from Gemini")

            uid = f"{int(time.time())}_{random.randint(1000,9999)}"
            temp_pcm = os.path.join(OUTPUT_FOLDER, f"{uid}.pcm")
            
            with open(temp_pcm, "wb") as f:
                f.write(base64.b64decode(audio_data))

            mp3_file = os.path.join(OUTPUT_FOLDER, f"{uid}.mp3")
            try:
                ffmpeg.input(temp_pcm, f='s16le', ar='24000', ac='1') \
                    .output(mp3_file, **{'y': None}) \
                    .run(overwrite_output=True, quiet=True)
                os.remove(temp_pcm)
                duration = get_audio_duration(mp3_file)
                
                # Only return success if everything worked
                print(f"[SUCCESS] Key {api_key[:20]} generated voice successfully")
                return mp3_file, duration, api_key
                
            except Exception as e:
                print(f"[ERROR] Key {api_key[:20]} failed during audio conversion: {e}")
                raise Exception(f"Convert error or duration measurement: {e}")

        except Exception as e:
            print(f"[ERROR] Key {api_key[:20]} failed: {e}")
            # Log failed attempt for debugging (but don't count as usage)
            log_failed_gemini_key(api_key, str(e))
            return None

    # Try each API key
    for i, api_key in enumerate(api_key_list):
        print(f"[VOICE] Trying key {i+1}/{len(api_key_list)}: {api_key[:20]}")
        result = task(api_key)
        if result:
            return result

    raise Exception("No available keys to create voice.")

# API Routes

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/simple')
def simple_home():
    """Simple home page for key management"""
    return render_template('simple_home.html')

@app.route('/admin')
def admin_login():
    """Admin login page"""
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    """Handle admin login"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = db.authenticate_user(username, password)
    if user and user['role'] == 'admin':
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Invalid credentials', 'error')
        return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    stats = db.get_admin_stats()
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/admin/keys')
def admin_key_management():
    """Admin key management page"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    return render_template('key_management.html')

@app.route('/admin/simple-keys')
def admin_simple_key_management():
    """Simple key management page - no user management needed"""
    return render_template('simple_key_management.html')

@app.route('/admin/gemini-keys')
def admin_gemini_keys():
    """Admin gemini keys management page"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    return render_template('gemini_keys_management.html')

@app.route('/admin/users')
def admin_users():
    """Admin users management page"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    return render_template('users_management.html')

@app.route('/admin/usage')
def admin_usage():
    """Admin usage stats page"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    return render_template('usage_stats.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.clear()
    return redirect(url_for('admin_login'))

# API Endpoints

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """API login endpoint"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = db.authenticate_user(username, password)
    if user:
        token = generate_jwt_token(user)
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
        })
    else:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """API register endpoint"""
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    user_id = db.create_user(username, email, password)
    if user_id:
        return jsonify({'success': True, 'message': 'User created successfully'})
    else:
        return jsonify({'success': False, 'error': 'Username or email already exists'}), 400

@app.route('/api/keys/create', methods=['POST'])
@require_auth
def create_api_key():
    """Create API key for user - DISABLED"""
    return jsonify({'success': False, 'error': 'API Keys feature is disabled'}), 403

@app.route('/api/keys/list', methods=['GET'])
@require_auth
def list_api_keys():
    """List user's API keys - DISABLED"""
    return jsonify({'success': False, 'error': 'API Keys feature is disabled'}), 403

@app.route('/api/voice/create', methods=['POST'])
def create_voice():
    """Create voice using Gemini TTS"""
    # Check Content-Type
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 415
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is empty'}), 400
    
    text = data.get('text')
    voice_name = data.get('voice_name', 'alloy')
    api_key = data.get('api_key')
    
    if not text or not api_key:
        return jsonify({'success': False, 'error': 'Missing text or api_key'}), 400
    
    # Global rate limiting: Check if we can process this request
    if not global_semaphore.acquire(blocking=False):
        print(f"[RATE_LIMIT] Global limit exceeded. Max {MAX_CONCURRENT_REQUESTS} concurrent requests allowed.")
        return jsonify({'success': False, 'error': 'Server busy. Please try again later.'}), 429
    
    try:
        # Validate API key
        validation = db.validate_api_key(api_key)
        if validation is None:
            print(f"[VALIDATE] Invalid API key: {api_key[:10]}...")
            return jsonify({'success': False, 'error': 'Invalid API key'}), 401
        
        if isinstance(validation, dict) and 'error' in validation:
            print(f"[VALIDATE] API key validation failed: {validation['error']}")
            return jsonify({'success': False, 'error': validation['error']}), 403
        
        print(f"[VALIDATE] API key validated successfully - Remaining: {validation.get('daily_remaining', 0)}")
        print(f"[VALIDATE] PROCEEDING WITH VOICE GENERATION")
        
        # Get available Gemini keys with IDs
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, api_key FROM gemini_keys WHERE is_active = 1')
        gemini_keys_data = cursor.fetchall()
        conn.close()
        
        if not gemini_keys_data:
            return jsonify({'success': False, 'error': 'No API keys available'}), 503
        
        # Extract just the API keys for the TTS request
        gemini_keys = [row[1] for row in gemini_keys_data]
        
        # Create voice using Gemini TTS
        print(f"[DEBUG] Starting voice creation for API key {api_key[:10]}...")
        result = gemini_tts_request(text, voice_name, gemini_keys)
        
        if result:
            print(f"[DEBUG] Voice creation SUCCESS for API key {api_key[:10]}...")
            mp3_file, duration, used_gemini_key = result
            filename = os.path.basename(mp3_file)
            
            # Verify the MP3 file actually exists and has content
            if not os.path.exists(mp3_file) or os.path.getsize(mp3_file) == 0:
                print(f"[ERROR] Generated MP3 file is invalid: {mp3_file}")
                return jsonify({'success': False, 'error': 'Failed to generate valid audio file'}), 500
            
            # Verify duration is valid
            if not duration or duration <= 0:
                print(f"[ERROR] Generated audio has invalid duration: {duration}")
                return jsonify({'success': False, 'error': 'Failed to generate valid audio duration'}), 500
            
            # Find the Gemini key ID that was used
            used_gemini_key_id = None
            for gemini_id, gemini_key in gemini_keys_data:
                if gemini_key == used_gemini_key:
                    used_gemini_key_id = gemini_id
                    break
            
            # Only log usage if we have a valid Gemini key ID
            if not used_gemini_key_id:
                print(f"[ERROR] Could not find Gemini key ID for used key: {used_gemini_key[:20]}")
                return jsonify({'success': False, 'error': 'Internal error: key tracking failed'}), 500
            
            # Log usage for API key (this will automatically increment daily/monthly usage)
            key_id = validation.get('key_id')
            user_id = validation.get('user_id')
            if key_id and user_id:
                try:
                    # Generate unique request ID to prevent duplicate processing
                    request_id = f"{key_id}_{user_id}_{int(time.time() * 1000)}_{hash(text[:50])}"
                    print(f"[DEBUG] Processing request {request_id} for key_id={key_id}, user_id={user_id}, text_length={len(text)}, voice_name={voice_name}")
                    
                    db.log_usage(key_id, user_id, len(text), voice_name, duration, 
                                os.path.getsize(mp3_file), request.remote_addr, request.headers.get('User-Agent'))
                    print(f"[DEBUG] Usage logged successfully for request {request_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to log usage for key_id={key_id}: {e}")
                    # Don't fail the request if logging fails
            
            # Log usage for Gemini key
            if used_gemini_key_id:
                try:
                    print(f"[DEBUG] Logging Gemini usage for gemini_key_id={used_gemini_key_id}, text_length={len(text)}")
                    db.log_gemini_usage(used_gemini_key_id, len(text), voice_name, duration, 
                                      os.path.getsize(mp3_file), request.remote_addr, request.headers.get('User-Agent'))
                    print(f"[DEBUG] Gemini usage logged successfully")
                except Exception as e:
                    print(f"[ERROR] Failed to log Gemini usage: {e}")
                    # Don't fail the request if logging fails
            
            return jsonify({
                'success': True,
                'filename': filename,
                'duration': duration,
                'download_url': f'/api/voice/download/{filename}'
            })
        else:
            print(f"[DEBUG] Voice creation FAILED for API key {api_key[:10]}...")
            return jsonify({'success': False, 'error': 'Failed to create voice'}), 500
            
    except Exception as e:
        print(f"[ERROR] Exception in voice creation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        # Always release the global semaphore
        global_semaphore.release()
        print(f"[RATE_LIMIT] Released semaphore. Available slots: {global_semaphore._value}")

@app.route('/api/voice/download/<filename>')
def download_voice(filename):
    """Download generated voice file"""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
@require_auth
def get_user_stats():
    """Get user statistics - DISABLED"""
    return jsonify({'success': False, 'error': 'API is disabled'}), 403

# Admin API Endpoints

@app.route('/api/admin/users', methods=['GET'])
def admin_list_users():
    """List all users (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, email, role, is_active, created_at
        FROM users ORDER BY created_at DESC
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    result = []
    for user in users:
        result.append({
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'role': user[3],
            'is_active': user[4],
            'created_at': user[5]
        })
    
    return jsonify({'success': True, 'users': result})

@app.route('/api/admin/gemini-keys', methods=['GET'])
def admin_list_gemini_keys():
    """List Gemini API keys (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, api_key, is_active, last_used, usage_count, created_at
        FROM gemini_keys ORDER BY created_at DESC
    ''')
    
    keys = cursor.fetchall()
    conn.close()
    
    result = []
    for key in keys:
        result.append({
            'id': key[0],
            'api_key': key[1],
            'is_active': key[2],
            'last_used': key[3],
            'usage_count': key[4],
            'created_at': key[5]
        })
    
    return jsonify({'success': True, 'keys': result})

@app.route('/api/admin/gemini-keys', methods=['POST'])
def admin_add_gemini_key():
    """Add Gemini API key (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json()
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({'success': False, 'error': 'API key required'}), 400
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO gemini_keys (api_key)
            VALUES (?)
        ''', (api_key,))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Gemini API key added successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'API key already exists'}), 400
    finally:
        conn.close()

# Additional endpoints for tool compatibility
@app.route('/api/voice/list', methods=['GET'])
def list_voices():
    """List available voices for TTS"""
    voices = [
        {"name": "Voice 1 - Alpha", "code": "achernar"},
        {"name": "Voice 2 - Beta", "code": "achird"},
        {"name": "Voice 3 - Gamma", "code": "algenib"},
        {"name": "Voice 4 - Delta", "code": "algieba"},
        {"name": "Voice 5 - Epsilon", "code": "alnilam"},
        {"name": "Voice 6 - Zeta", "code": "aoede"},
        {"name": "Voice 7 - Eta", "code": "autonoe"},
        {"name": "Voice 8 - Theta", "code": "callirrhoe"},
        {"name": "Voice 9 - Iota", "code": "charon"},
        {"name": "Voice 10 - Kappa", "code": "despina"},
        {"name": "Voice 11 - Lambda", "code": "enceladus"},
        {"name": "Voice 12 - Mu", "code": "erinome"},
        {"name": "Voice 13 - Nu", "code": "fenrir"},
        {"name": "Voice 14 - Xi", "code": "gacrux"},
        {"name": "Voice 15 - Omicron", "code": "iapetus"},
        {"name": "Voice 16 - Pi", "code": "kore"},
        {"name": "Voice 17 - Rho", "code": "laomedeia"},
        {"name": "Voice 18 - Sigma", "code": "leda"},
        {"name": "Voice 19 - Tau", "code": "orus"},
        {"name": "Voice 20 - Upsilon", "code": "puck"},
        {"name": "Voice 21 - Phi", "code": "pulcherrima"},
        {"name": "Voice 22 - Chi", "code": "rasalgethi"},
        {"name": "Voice 23 - Psi", "code": "sadachbia"},
        {"name": "Voice 24 - Omega", "code": "sadaltager"},
        {"name": "Voice 25 - Alpha Prime", "code": "schedar"},
        {"name": "Voice 26 - Beta Prime", "code": "sulafat"},
        {"name": "Voice 27 - Gamma Prime", "code": "umbriel"},
        {"name": "Voice 28 - Delta Prime", "code": "vindemiatrix"},
        {"name": "Voice 29 - Epsilon Prime", "code": "zephyr"},
        {"name": "Voice 30 - Zeta Prime", "code": "zubenelgenubi"},
    ]

    return jsonify({
        'success': True,
        'voices': voices,
        'message': f'Found {len(voices)} available voices'
    })

@app.route('/api/voice/auth', methods=['GET'])
def voice_auth():
    """Simple auth endpoint for tool compatibility"""
    api_key = request.args.get('key')
    device_id = request.args.get('device_id', '')
    
    if not api_key:
        return jsonify({'success': False, 'error': 'API key required'}), 400
    
    # Validate API key using existing database function
    validation = db.validate_api_key(api_key)
    
    if validation is None:
        return jsonify({'success': False, 'error': 'Invalid API key'}), 401
    
    if isinstance(validation, dict) and 'error' in validation:
        return jsonify({'success': False, 'error': validation['error']}), 403
    
    # Get key details first to check device binding
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ak.key_name, ak.expires_at, ak.daily_limit, ak.monthly_limit, 
               ak.device_id, ak.last_login, u.username
        FROM api_keys ak
        JOIN users u ON ak.user_id = u.id
        WHERE ak.api_key = ?
    ''', (api_key,))
    
    key_data = cursor.fetchone()
    conn.close()
    
    if not key_data:
        return jsonify({'success': False, 'error': 'Key not found'}), 404
    
    key_name, expires_at, daily_limit, monthly_limit, stored_device_id, last_login, username = key_data
    
    # Update device_id and last_login if provided
    if device_id:
        # Check if device_id is already bound to a different key
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT api_key FROM api_keys WHERE device_id = ? AND api_key != ?', (device_id, api_key))
        existing_key = cursor.fetchone()
        conn.close()
        
        if existing_key:
            existing_key_short = existing_key[0][:8] + "***" + existing_key[0][-8:]
            return jsonify({
                'success': False, 
                'error': f'Device này đã được bind với key khác: {existing_key_short}'
            }), 403
        
        # Check if key is already bound to a different device
        if stored_device_id and stored_device_id != device_id:
            return jsonify({
                'success': False, 
                'error': f'Key này đã tồn tại máy khác. Device hiện tại: {stored_device_id[:8]}***{stored_device_id[-8:]}'
            }), 403
        
        # Update device_id and last_login
        db.update_device_login(api_key, device_id)
        
        # Get updated device_id and last_login
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT device_id, last_login FROM api_keys WHERE api_key = ?', (api_key,))
        updated_data = cursor.fetchone()
        conn.close()
        
        if updated_data:
            stored_device_id, last_login = updated_data
    else:
        # If no device_id provided, check if key is already bound
        if stored_device_id:
            # Key is already bound, just update last_login
            db.update_device_login(api_key, stored_device_id)
            
            # Get updated last_login
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT last_login FROM api_keys WHERE api_key = ?', (api_key,))
            updated_login = cursor.fetchone()
            conn.close()
            
            if updated_login:
                last_login = updated_login[0]
        else:
            # Key not bound yet, require device_id
            return jsonify({
                'success': False, 
                'error': 'Key chưa được bind với máy. Vui lòng nhập device_id để bind lần đầu.'
            }), 400
    
    # Calculate remaining usage
    daily_remaining = validation.get('daily_remaining', 0)
    monthly_remaining = validation.get('monthly_remaining', 0)
    
    # Format expiration date
    expires_str = ""
    if expires_at:
        expires_date = datetime.fromisoformat(expires_at)
        expires_str = expires_date.strftime('%d/%m/%Y')
    
    # Format last login
    last_login_str = ""
    if last_login:
        last_login_date = datetime.fromisoformat(last_login)
        last_login_str = last_login_date.strftime('%d/%m/%Y %H:%M')
    
    return jsonify({
        'success': True,
        'message': '✅ API key validated successfully',
        'key': api_key,
        'key_name': key_name,
        'user': username,
        'expires': expires_str,
        'remaining_daily': daily_remaining,
        'daily_limit': daily_limit,
        'device_id': stored_device_id or '',
        'last_login': last_login_str
    })

@app.route('/api/version.json', methods=['GET'])
def version_info():
    """Version information endpoint"""
    return jsonify({
        'version': '1.0.0',
        'update_available': False,
        'download_url': '',
        'changelog': ''
    })

# Key Management APIs
@app.route('/api/admin/keys', methods=['GET'])
def admin_list_all_keys():
    """List all API keys for admin management"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ak.id, ak.key_name, ak.api_key, ak.daily_limit, ak.total_usage,
               ak.expires_at, ak.is_active, ak.created_at, ak.device_id, ak.last_login, u.username
        FROM api_keys ak
        JOIN users u ON ak.user_id = u.id
        ORDER BY ak.created_at DESC
    ''')
    
    keys = cursor.fetchall()
    
    # Get today's usage for each key
    today = datetime.now().date()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    result = []
    for key in keys:
        key_id = key[0]
        total_usage = key[4]  # total_usage from api_keys table
        
        # Get today's actual daily usage
        cursor.execute('''
            SELECT COALESCE(usage_count, 0) FROM daily_usage 
            WHERE api_key_id = ? AND usage_date = ?
        ''', (key_id, today))
        
        usage_result = cursor.fetchone()
        daily_usage = usage_result[0] if usage_result else 0
        
        # Ensure remaining_daily is never negative
        remaining_daily = max(0, key[3] - daily_usage)  # daily_limit - daily_usage, minimum 0
        
        # If daily_usage exceeds daily_limit, show 0 remaining but keep actual usage
        if daily_usage > key[3]:
            print(f"[WARNING] Key {key[2][:10]}... exceeded daily limit: usage={daily_usage}, limit={key[3]}")
        
        result.append({
            'id': key[0],
            'key_name': key[1],
            'api_key': key[2],
            'daily_limit': key[3],
            'daily_usage': daily_usage,  # Shows actual daily usage
            'total_usage': total_usage,  # Shows cumulative usage
            'remaining_daily': remaining_daily,  # Never negative
            'expires_at': key[5],
            'is_active': key[6],
            'created_at': key[7],
            'device_id': key[8] or '',
            'last_login': key[9] or '',
            'username': key[10]
        })
    
    conn.close()
    
    # Fix any keys that have exceeded daily limit
    try:
        fixed_count = db.fix_exceeded_daily_usage()
        if fixed_count > 0:
            print(f"[FIX] Fixed {fixed_count} keys that exceeded daily limit")
    except Exception as e:
        print(f"[ERROR] Failed to fix exceeded daily usage: {e}")
    
    return jsonify({'success': True, 'keys': result})

@app.route('/api/admin/keys', methods=['POST'])
def admin_create_key():
    """Create API key for any user (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json()
    username = data.get('username')
    key_name = data.get('key_name', 'Admin Created Key')
    daily_limit = data.get('daily_limit', 100)
    monthly_limit = data.get('monthly_limit', 3000)
    expires_days = data.get('expires_days')
    custom_key = data.get('custom_key')
    
    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Get user ID
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    user_id = user[0]
    
    # Generate or use custom key
    if custom_key:
        api_key = custom_key
    else:
        api_key = db.generate_api_key()
    
    expires_at = None
    if expires_days:
        expires_at = datetime.now() + timedelta(days=expires_days)
    
    try:
        cursor.execute('''
            INSERT INTO api_keys (user_id, key_name, api_key, daily_limit, monthly_limit, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, key_name, api_key, daily_limit, monthly_limit, expires_at))
        
        key_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'key_id': key_id,
            'api_key': api_key,
            'message': 'API key created successfully'
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'API key already exists'}), 400

@app.route('/api/admin/keys/<int:key_id>', methods=['DELETE'])
def admin_delete_key(key_id):
    """Delete API key (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'API key deleted successfully'})
    else:
        conn.close()
        return jsonify({'success': False, 'error': 'API key not found'}), 404

@app.route('/api/admin/keys/<int:key_id>/toggle', methods=['POST'])
def admin_toggle_key(key_id):
    """Toggle API key status (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE api_keys 
        SET is_active = NOT is_active 
        WHERE id = ?
    ''', (key_id,))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'API key status updated'})
    else:
        conn.close()
        return jsonify({'success': False, 'error': 'API key not found'}), 404

@app.route('/api/admin/gemini-keys/<int:key_id>', methods=['DELETE'])
def admin_delete_gemini_key(key_id):
    """Delete Gemini API key (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM gemini_keys WHERE id = ?', (key_id,))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Gemini API key deleted successfully'})
    else:
        conn.close()
        return jsonify({'success': False, 'error': 'Gemini API key not found'}), 404

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    """Delete user (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    # Prevent deleting admin users
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    if user[0] == 'admin':
        conn.close()
        return jsonify({'success': False, 'error': 'Cannot delete admin users'}), 400
    
    # Delete user and related data
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    
    if cursor.rowcount > 0:
        # Also delete related API keys and usage logs
        cursor.execute('DELETE FROM api_keys WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM usage_logs WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    else:
        conn.close()
        return jsonify({'success': False, 'error': 'User not found'}), 404

@app.route('/api/admin/usage-logs', methods=['GET'])
def admin_get_usage_logs():
    """Get usage logs (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Get usage logs with user info
    cursor.execute('''
        SELECT ul.id, ak.api_key, u.username, ul.text_length, ul.voice_name, 
               ul.duration, ul.file_size, ul.ip_address, ul.created_at
        FROM usage_logs ul
        JOIN api_keys ak ON ul.api_key_id = ak.id
        JOIN users u ON ul.user_id = u.id
        ORDER BY ul.created_at DESC
        LIMIT 1000
    ''')
    
    logs = cursor.fetchall()
    conn.close()
    
    result = []
    for log in logs:
        result.append({
            'id': log[0],
            'api_key': log[1],
            'username': log[2],
            'text_length': log[3],
            'voice_name': log[4],
            'duration': log[5],
            'file_size': log[6],
            'ip_address': log[7],
            'timestamp': log[8]
        })
    
    return jsonify({'success': True, 'logs': result})

@app.route('/api/admin/usage-logs', methods=['DELETE'])
def admin_delete_usage_logs():
    """Delete old usage logs (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json() or {}
    days_old = data.get('days_old', 30)  # Default: delete logs older than 30 days
    
    if not isinstance(days_old, int) or days_old < 1:
        return jsonify({'success': False, 'error': 'Invalid days_old parameter'}), 400
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    # Count logs to be deleted
    cursor.execute('SELECT COUNT(*) FROM usage_logs WHERE created_at < ?', (cutoff_date,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        conn.close()
        return jsonify({'success': True, 'message': 'No old usage logs found', 'deleted_count': 0})
    
    # Delete old usage logs
    cursor.execute('DELETE FROM usage_logs WHERE created_at < ?', (cutoff_date,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': f'Deleted {count} usage logs older than {days_old} days',
        'deleted_count': count
    })

@app.route('/api/admin/users/<int:user_id>/toggle', methods=['POST'])
def admin_toggle_user(user_id):
    """Toggle user status (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json() or {}
    is_active = data.get('is_active')
    
    if is_active is None:
        return jsonify({'success': False, 'error': 'is_active parameter required'}), 400
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    # Update user status
    cursor.execute('UPDATE users SET is_active = ? WHERE id = ?', (is_active, user_id))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'User status updated'})
    else:
        conn.close()
        return jsonify({'success': False, 'error': 'User not found'}), 404

@app.route('/api/admin/users', methods=['POST'])
def admin_create_user():
    """Create user (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'user')
    
    if not all([username, email, password]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    user_id = db.create_user(username, email, password, role)
    if user_id:
        return jsonify({'success': True, 'user_id': user_id, 'message': 'User created successfully'})
    else:
        return jsonify({'success': False, 'error': 'Username or email already exists'}), 400

@app.route('/api/admin/keys/<int:key_id>', methods=['PUT'])
def admin_edit_key(key_id):
    """Edit API key (admin only)"""
    # Check admin session instead of JWT token
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json()
    key_name = data.get('key_name')
    daily_limit = data.get('daily_limit')
    monthly_limit = data.get('monthly_limit')
    expires_days = data.get('expires_days')
    
    if not all([key_name, daily_limit is not None, monthly_limit is not None]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Check if key exists
    cursor.execute('SELECT id FROM api_keys WHERE id = ?', (key_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'API key not found'}), 404
    
    # Calculate expires_at
    expires_at = None
    if expires_days and expires_days > 0:
        expires_at = datetime.now() + timedelta(days=expires_days)
    
    # Update key
    cursor.execute('''
        UPDATE api_keys 
        SET key_name = ?, daily_limit = ?, monthly_limit = ?, expires_at = ?
        WHERE id = ?
    ''', (key_name, daily_limit, monthly_limit, expires_at, key_id))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'API key updated successfully'})
    else:
        conn.close()
        return jsonify({'success': False, 'error': 'API key not found'}), 404

def reset_gemini_daily_usage():
    """Reset Gemini daily usage at midnight (called by scheduler)"""
    try:
        affected_rows = db.reset_gemini_daily_usage()
        if affected_rows > 0:
            print(f"[GEMINI] Reset {affected_rows} Gemini daily usage records for new day")
        else:
            print(f"[GEMINI] No Gemini daily usage records to reset")
        
    except Exception as e:
        print(f"[ERROR] Failed to reset Gemini daily usage: {e}")

def run_scheduler():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    # Schedule daily reset of Gemini usage at midnight
    schedule.every().day.at("00:00").do(reset_gemini_daily_usage)
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Add some sample Gemini API keys for testing
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Check if any Gemini keys exist
    cursor.execute('SELECT COUNT(*) FROM gemini_keys')
    if cursor.fetchone()[0] == 0:
        print("No Gemini API keys found. Please add them via admin panel.")
    
    conn.close()
    
    print("Starting server with quota management...")
    app.run(debug=True, host='0.0.0.0', port=5000)