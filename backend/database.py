import sqlite3
import os
from datetime import datetime, timedelta
import hashlib
import secrets

class DatabaseManager:
    def __init__(self, db_path="voice_api.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # API Keys table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_name VARCHAR(100) NOT NULL,
                api_key VARCHAR(255) UNIQUE NOT NULL,
                daily_limit INTEGER DEFAULT 100,
                monthly_limit INTEGER DEFAULT 3000,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                device_id VARCHAR(255),
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Usage logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                text_length INTEGER NOT NULL,
                voice_name VARCHAR(50) NOT NULL,
                duration REAL,
                file_size INTEGER,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_key_id) REFERENCES api_keys (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Daily usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER NOT NULL,
                usage_date DATE NOT NULL,
                usage_count INTEGER DEFAULT 0,
                total_characters INTEGER DEFAULT 0,
                UNIQUE(api_key_id, usage_date),
                FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
            )
        ''')
        
        # Monthly usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monthly_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER NOT NULL,
                usage_month VARCHAR(7) NOT NULL, -- YYYY-MM format
                usage_count INTEGER DEFAULT 0,
                total_characters INTEGER DEFAULT 0,
                UNIQUE(api_key_id, usage_month),
                FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
            )
        ''')
        
        # Gemini API Keys table (for TTS service)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gemini_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name VARCHAR(100) NOT NULL,
                api_key VARCHAR(255) UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                daily_limit INTEGER DEFAULT 1000,
                monthly_limit INTEGER DEFAULT 30000,
                last_used TIMESTAMP,
                last_quota_exceeded TIMESTAMP,
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Gemini daily usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gemini_daily_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gemini_key_id INTEGER NOT NULL,
                usage_date DATE NOT NULL,
                usage_count INTEGER DEFAULT 0,
                total_characters INTEGER DEFAULT 0,
                UNIQUE(gemini_key_id, usage_date),
                FOREIGN KEY (gemini_key_id) REFERENCES gemini_keys (id)
            )
        ''')
        
        # Gemini monthly usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gemini_monthly_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gemini_key_id INTEGER NOT NULL,
                usage_month VARCHAR(7) NOT NULL, -- YYYY-MM format
                usage_count INTEGER DEFAULT 0,
                total_characters INTEGER DEFAULT 0,
                UNIQUE(gemini_key_id, usage_month),
                FOREIGN KEY (gemini_key_id) REFERENCES gemini_keys (id)
            )
        ''')
        
        # Gemini usage logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gemini_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gemini_key_id INTEGER NOT NULL,
                text_length INTEGER NOT NULL,
                voice_name VARCHAR(50) NOT NULL,
                duration REAL,
                file_size INTEGER,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gemini_key_id) REFERENCES gemini_keys (id)
            )
        ''')
        
        # Admin settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key VARCHAR(100) UNIQUE NOT NULL,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Add new columns to existing api_keys table if they don't exist
        self.add_missing_columns()
        
        # Create default admin user if not exists
        self.create_default_admin()
    
    def create_default_admin(self):
        """Create default admin user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if admin exists
        cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        if cursor.fetchone():
            conn.close()
            return
        
        # Create default admin
        admin_password = "admin123"  # Should be changed in production
        password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ("admin", "admin@voiceapi.com", password_hash, "admin"))
        
        conn.commit()
        conn.close()
        print("Default admin created: username=admin, password=admin123")
    
    def log_gemini_usage(self, gemini_key_id, text_length, voice_name, duration, file_size, ip_address, user_agent):
        """Log Gemini API usage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert usage log
            cursor.execute('''
                INSERT INTO gemini_usage_logs 
                (gemini_key_id, text_length, voice_name, duration, file_size, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (gemini_key_id, text_length, voice_name, duration, file_size, ip_address, user_agent))
            
            # Update daily usage
            today = datetime.now().date()
            cursor.execute('''
                INSERT OR REPLACE INTO gemini_daily_usage 
                (gemini_key_id, usage_date, usage_count, total_characters)
                VALUES (?, ?, 
                    COALESCE((SELECT usage_count FROM gemini_daily_usage 
                             WHERE gemini_key_id = ? AND usage_date = ?), 0) + 1,
                    COALESCE((SELECT total_characters FROM gemini_daily_usage 
                             WHERE gemini_key_id = ? AND usage_date = ?), 0) + ?)
            ''', (gemini_key_id, today, gemini_key_id, today, gemini_key_id, today, text_length))
            
            # Update monthly usage
            current_month = datetime.now().strftime('%Y-%m')
            cursor.execute('''
                INSERT OR REPLACE INTO gemini_monthly_usage 
                (gemini_key_id, usage_month, usage_count, total_characters)
                VALUES (?, ?, 
                    COALESCE((SELECT usage_count FROM gemini_monthly_usage 
                             WHERE gemini_key_id = ? AND usage_month = ?), 0) + 1,
                    COALESCE((SELECT total_characters FROM gemini_monthly_usage 
                             WHERE gemini_key_id = ? AND usage_month = ?), 0) + ?)
            ''', (gemini_key_id, current_month, gemini_key_id, current_month, gemini_key_id, current_month, text_length))
            
            # Update gemini key usage count and last used
            cursor.execute('''
                UPDATE gemini_keys 
                SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (gemini_key_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error logging Gemini usage: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_gemini_daily_usage(self, gemini_key_id, date=None):
        """Get daily usage for a Gemini key"""
        if date is None:
            date = datetime.now().date()
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT usage_count, total_characters 
            FROM gemini_daily_usage 
            WHERE gemini_key_id = ? AND usage_date = ?
        ''', (gemini_key_id, date))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'usage_count': result[0], 'total_characters': result[1]}
        return {'usage_count': 0, 'total_characters': 0}
    
    def get_gemini_monthly_usage(self, gemini_key_id, month=None):
        """Get monthly usage for a Gemini key"""
        if month is None:
            month = datetime.now().strftime('%Y-%m')
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT usage_count, total_characters 
            FROM gemini_monthly_usage 
            WHERE gemini_key_id = ? AND usage_month = ?
        ''', (gemini_key_id, month))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'usage_count': result[0], 'total_characters': result[1]}
        return {'usage_count': 0, 'total_characters': 0}
    
    def add_missing_columns(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if device_id column exists in api_keys table
            cursor.execute("PRAGMA table_info(api_keys)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'device_id' not in columns:
                cursor.execute('ALTER TABLE api_keys ADD COLUMN device_id VARCHAR(255)')
                print("Added device_id column to api_keys table")
            
            if 'last_login' not in columns:
                cursor.execute('ALTER TABLE api_keys ADD COLUMN last_login TIMESTAMP')
                print("Added last_login column to api_keys table")
            
            # Check gemini_keys table
            cursor.execute("PRAGMA table_info(gemini_keys)")
            gemini_columns = [column[1] for column in cursor.fetchall()]
            
            if 'last_quota_exceeded' not in gemini_columns:
                cursor.execute('ALTER TABLE gemini_keys ADD COLUMN last_quota_exceeded TIMESTAMP')
                print("Added last_quota_exceeded column to gemini_keys table")
            
            conn.commit()
        except Exception as e:
            print(f"Error adding columns: {e}")
        finally:
            conn.close()
    
    def generate_api_key(self):
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    def hash_password(self, password):
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password, password_hash):
        """Verify password against hash"""
        return self.hash_password(password) == password_hash
    
    def create_user(self, username, email, password, role="user"):
        """Create a new user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            password_hash = self.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', (username, email, password_hash, role))
            
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()
    
    def authenticate_user(self, username, password):
        """Authenticate user login"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, email, password_hash, role, is_active
            FROM users WHERE username = ? AND is_active = 1
        ''', (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user and self.verify_password(password, user[3]):
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[4]
            }
        return None
    
    def create_api_key(self, user_id, key_name, daily_limit=100, monthly_limit=3000, expires_days=None):
        """Create API key for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        api_key = self.generate_api_key()
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
            return api_key, key_id
        except sqlite3.IntegrityError:
            return None, None
        finally:
            conn.close()
    
    def validate_api_key(self, api_key):
        """Validate API key and check limits"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ak.id, ak.user_id, ak.daily_limit, ak.monthly_limit, ak.expires_at,
                   u.username, u.role
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            WHERE ak.api_key = ? AND ak.is_active = 1 AND u.is_active = 1
        ''', (api_key,))
        
        key_data = cursor.fetchone()
        if not key_data:
            conn.close()
            return None
        
        key_id, user_id, daily_limit, monthly_limit, expires_at, username, role = key_data
        
        # Check expiration
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
            conn.close()
            return None
        
        # Check daily limit
        today = datetime.now().date()
        cursor.execute('''
            SELECT usage_count FROM daily_usage
            WHERE api_key_id = ? AND usage_date = ?
        ''', (key_id, today))
        
        daily_usage = cursor.fetchone()
        daily_count = daily_usage[0] if daily_usage else 0
        
        if daily_count >= daily_limit:
            conn.close()
            return {'error': 'Daily limit exceeded'}
        
        # Check monthly limit
        current_month = datetime.now().strftime('%Y-%m')
        cursor.execute('''
            SELECT usage_count FROM monthly_usage
            WHERE api_key_id = ? AND usage_month = ?
        ''', (key_id, current_month))
        
        monthly_usage = cursor.fetchone()
        monthly_count = monthly_usage[0] if monthly_usage else 0
        
        if monthly_count >= monthly_limit:
            conn.close()
            return {'error': 'Monthly limit exceeded'}
        
        conn.close()
        return {
            'key_id': key_id,
            'user_id': user_id,
            'username': username,
            'role': role,
            'daily_remaining': daily_limit - daily_count,
            'monthly_remaining': monthly_limit - monthly_count
        }
    
    def log_usage(self, api_key_id, user_id, text_length, voice_name, duration=None, file_size=None, ip_address=None, user_agent=None):
        """Log API usage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert usage log
        cursor.execute('''
            INSERT INTO usage_logs (api_key_id, user_id, text_length, voice_name, duration, file_size, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (api_key_id, user_id, text_length, voice_name, duration, file_size, ip_address, user_agent))
        
        # Update daily usage
        today = datetime.now().date()
        cursor.execute('''
            INSERT OR REPLACE INTO daily_usage (api_key_id, usage_date, usage_count, total_characters)
            VALUES (?, ?, 
                COALESCE((SELECT usage_count FROM daily_usage WHERE api_key_id = ? AND usage_date = ?), 0) + 1,
                COALESCE((SELECT total_characters FROM daily_usage WHERE api_key_id = ? AND usage_date = ?), 0) + ?
            )
        ''', (api_key_id, today, api_key_id, today, api_key_id, today, text_length))
        
        # Update monthly usage
        current_month = datetime.now().strftime('%Y-%m')
        cursor.execute('''
            INSERT OR REPLACE INTO monthly_usage (api_key_id, usage_month, usage_count, total_characters)
            VALUES (?, ?, 
                COALESCE((SELECT usage_count FROM monthly_usage WHERE api_key_id = ? AND usage_month = ?), 0) + 1,
                COALESCE((SELECT total_characters FROM monthly_usage WHERE api_key_id = ? AND usage_month = ?), 0) + ?
            )
        ''', (api_key_id, current_month, api_key_id, current_month, api_key_id, current_month, text_length))
        
        conn.commit()
        conn.close()
    
    def get_user_stats(self, user_id):
        """Get user statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get API keys count
        cursor.execute('SELECT COUNT(*) FROM api_keys WHERE user_id = ?', (user_id,))
        api_keys_count = cursor.fetchone()[0]
        
        # Get total usage
        cursor.execute('''
            SELECT COUNT(*), SUM(text_length), SUM(duration)
            FROM usage_logs WHERE user_id = ?
        ''', (user_id,))
        
        total_usage = cursor.fetchone()
        
        # Get today's usage
        today = datetime.now().date()
        cursor.execute('''
            SELECT SUM(usage_count), SUM(total_characters)
            FROM daily_usage du
            JOIN api_keys ak ON du.api_key_id = ak.id
            WHERE ak.user_id = ? AND du.usage_date = ?
        ''', (user_id, today))
        
        today_usage = cursor.fetchone()
        
        conn.close()
        
        return {
            'api_keys_count': api_keys_count,
            'total_requests': total_usage[0] or 0,
            'total_characters': total_usage[1] or 0,
            'total_duration': total_usage[2] or 0,
            'today_requests': today_usage[0] or 0,
            'today_characters': today_usage[1] or 0
        }
    
    def get_admin_stats(self):
        """Get admin dashboard statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total users
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        total_users = cursor.fetchone()[0]
        
        # Total API keys
        cursor.execute('SELECT COUNT(*) FROM api_keys WHERE is_active = 1')
        total_keys = cursor.fetchone()[0]
        
        # Today's total usage
        today = datetime.now().date()
        cursor.execute('SELECT SUM(usage_count) FROM daily_usage WHERE usage_date = ?', (today,))
        today_usage = cursor.fetchone()[0] or 0
        
        # This month's usage
        current_month = datetime.now().strftime('%Y-%m')
        cursor.execute('SELECT SUM(usage_count) FROM monthly_usage WHERE usage_month = ?', (current_month,))
        month_usage = cursor.fetchone()[0] or 0
        
        # Recent users
        cursor.execute('''
            SELECT username, email, created_at FROM users 
            WHERE is_active = 1 ORDER BY created_at DESC LIMIT 5
        ''')
        recent_users = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_users': total_users,
            'total_keys': total_keys,
            'today_usage': today_usage,
            'month_usage': month_usage,
            'recent_users': recent_users
        }

    def update_device_login(self, api_key, device_id):
        """Update device_id and last_login for API key"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE api_keys 
            SET device_id = ?, last_login = CURRENT_TIMESTAMP
            WHERE api_key = ?
        ''', (device_id, api_key))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0

if __name__ == "__main__":
    # Test database initialization
    db = DatabaseManager()
    print("Database initialized successfully!")
    
    # Test creating a user
    user_id = db.create_user("testuser", "test@example.com", "password123")
    if user_id:
        print(f"Test user created with ID: {user_id}")
        
        # Test creating API key
        api_key, key_id = db.create_api_key(user_id, "Test Key", 50, 1500)
        if api_key:
            print(f"API key created: {api_key[:20]}...")
            
            # Test validation
            validation = db.validate_api_key(api_key)
            if validation:
                print(f"API key validation successful: {validation}")
            else:
                print("API key validation failed")
    else:
        print("Failed to create test user")