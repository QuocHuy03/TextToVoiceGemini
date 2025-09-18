#!/usr/bin/env python3
"""
Script to check daily usage in database
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def check_usage():
    """Check daily usage and API keys"""
    
    # Connect to database
    conn = sqlite3.connect('backend/voice_api.db')
    cursor = conn.cursor()
    
    print("=== DAILY USAGE ===")
    cursor.execute('SELECT * FROM daily_usage ORDER BY usage_date DESC LIMIT 10')
    daily_usage = cursor.fetchall()
    
    if daily_usage:
        for row in daily_usage:
            print(f'Key ID: {row[0]}, Date: {row[1]}, Count: {row[2]}, Chars: {row[3]}')
    else:
        print("No daily usage records found")
    
    print("\n=== API KEYS ===")
    cursor.execute('SELECT id, api_key, daily_limit FROM api_keys WHERE is_active = 1 LIMIT 5')
    api_keys = cursor.fetchall()
    
    for row in api_keys:
        print(f'ID: {row[0]}, Key: {row[1][:20]}..., Limit: {row[2]}')
    
    print("\n=== USAGE LOGS ===")
    cursor.execute('SELECT api_key_id, voice_name, created_at FROM usage_logs ORDER BY created_at DESC LIMIT 5')
    usage_logs = cursor.fetchall()
    
    if usage_logs:
        for row in usage_logs:
            print(f'Key ID: {row[0]}, Voice: {row[1]}, Time: {row[2]}')
    else:
        print("No usage logs found")
    
    # Check today's usage for a specific key
    print("\n=== TODAY'S USAGE CHECK ===")
    today = datetime.now().date()
    cursor.execute('''
        SELECT ak.id, ak.api_key, ak.daily_limit, 
               COALESCE(du.usage_count, 0) as daily_count,
               ak.daily_limit - COALESCE(du.usage_count, 0) as remaining
        FROM api_keys ak
        LEFT JOIN daily_usage du ON ak.id = du.api_key_id AND du.usage_date = ?
        WHERE ak.is_active = 1
        LIMIT 3
    ''', (today,))
    
    today_usage = cursor.fetchall()
    for row in today_usage:
        print(f'Key ID: {row[0]}, Key: {row[1][:20]}..., Limit: {row[2]}, Used: {row[3]}, Remaining: {row[4]}')
    
    conn.close()

if __name__ == "__main__":
    check_usage()