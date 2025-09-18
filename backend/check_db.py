#!/usr/bin/env python3
"""
Script to check database usage directly
"""

import sqlite3
from datetime import datetime

def check_database():
    """Check database usage directly"""
    
    # Connect to database
    conn = sqlite3.connect('voice_api.db')
    cursor = conn.cursor()
    
    print("=== CHECKING DATABASE ===")
    
    # Check if daily_usage table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_usage'")
    if not cursor.fetchone():
        print("❌ daily_usage table does not exist!")
        return
    
    # Check daily_usage records
    print("\n=== DAILY USAGE RECORDS ===")
    cursor.execute('SELECT * FROM daily_usage ORDER BY usage_date DESC LIMIT 10')
    daily_records = cursor.fetchall()
    
    if daily_records:
        for record in daily_records:
            print(f"Key ID: {record[0]}, Date: {record[1]}, Count: {record[2]}, Chars: {record[3]}")
    else:
        print("❌ No daily usage records found!")
    
    # Check usage_logs
    print("\n=== USAGE LOGS ===")
    cursor.execute('SELECT api_key_id, voice_name, created_at FROM usage_logs ORDER BY created_at DESC LIMIT 10')
    usage_logs = cursor.fetchall()
    
    if usage_logs:
        for log in usage_logs:
            print(f"Key ID: {log[0]}, Voice: {log[1]}, Time: {log[2]}")
    else:
        print("❌ No usage logs found!")
    
    # Check API keys
    print("\n=== API KEYS ===")
    cursor.execute('SELECT id, api_key, daily_limit FROM api_keys WHERE is_active = 1 LIMIT 3')
    api_keys = cursor.fetchall()
    
    for key in api_keys:
        print(f"ID: {key[0]}, Key: {key[1][:20]}..., Limit: {key[2]}")
    
    # Check today's usage for specific key
    print("\n=== TODAY'S USAGE FOR KEY ID 10 ===")
    today = datetime.now().date()
    cursor.execute('''
        SELECT ak.id, ak.api_key, ak.daily_limit, 
               COALESCE(du.usage_count, 0) as daily_count,
               ak.daily_limit - COALESCE(du.usage_count, 0) as remaining
        FROM api_keys ak
        LEFT JOIN daily_usage du ON ak.id = du.api_key_id AND du.usage_date = ?
        WHERE ak.id = 10
    ''', (today,))
    
    result = cursor.fetchone()
    if result:
        print(f"Key ID: {result[0]}, Key: {result[1][:20]}..., Limit: {result[2]}, Used: {result[3]}, Remaining: {result[4]}")
    else:
        print("❌ Key ID 10 not found!")
    
    conn.close()

if __name__ == "__main__":
    check_database()