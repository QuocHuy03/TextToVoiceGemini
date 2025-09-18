#!/usr/bin/env python3
"""
Script to add Gemini API keys to database
"""

import sqlite3
import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.database import DatabaseManager

def add_gemini_keys():
    """Add all Gemini API keys to database"""
    
    # Initialize database manager
    db = DatabaseManager('backend/voice_api.db')
    
    # List of Gemini API keys
    gemini_keys = [
        "AIzaSyBUjzR46uUMNBbwUWA3ccptbDXpyBvs5nQ",
        "AIzaSyD1_1hvTAaUrV9yA-2fpSOZLIAoXdTTSIo",
        "AIzaSyBY2u-70W5CgGT5z-4lh4BbxoEEslhr_cE",
        "AIzaSyC1f1EXzSGj-8IGUBc-AHj2w7wKJ5lJ73A",
        "AIzaSyDrJpb9YWYbs1XRoPvg4IE3SL2-SpYzlLE",
        "AIzaSyDGTwmsfD5rTWkawVE8xg0N_DBXcze0RwA",
        "AIzaSyBT21-_KTcdxlBuYOJNy_8dIuZ6E4978C4",
        "AIzaSyBArYKcK9YlWwKe4p4I39I6xUl_TapI8xA",
        "AIzaSyChzAosLfaZsO2soOb_rxo8FJ9bMy1buZw",
        "AIzaSyDIW3fP8eean2JX_7lAYfKWimR-IQSrBus",
        "AIzaSyB4v7SWoKb6ebzsauj-nP1C5rRMYRgVos4",
        "AIzaSyA_mejAbFIsp657aWdp7oncnDxEZB6X3kY",
        "AIzaSyASGDHm1mFT-K6R5Ptq5md3T_Uqwsb1nS4",
        "AIzaSyBX2u82WpdwQZYZ6WeDAHVIie2F5JvSmZw",
        "AIzaSyAtDBSatWtzfq5thPpGh9B6D52HaK6jC7I",
        "AIzaSyBHr08hcXVV6fJGhHmOTchOoIyVInZdszo",
        "AIzaSyDk0cA1-arQAKM8sCqSxciJ8bHEil5R_ik",
        "AIzaSyA1TnfyA2WI0G-_JwtBlofSC5nHTNpYTC4",
        "AIzaSyAyll26wzyzkEY0DcNnQH5tItJbODl2gZI",
        "AIzaSyCv0qCmxqypNi9gXl5lHSutJ19p5d9W7iA",
        "AIzaSyBvtHwYixX_eFisDMIVHZhHrJ4vAWt-EJk",
        "AIzaSyB701JRu07_wMAWBHKht4gWEwcccEF7MZU",
        "AIzaSyDve7ad4velwMZ3X6Xw-cpEZ3IDRAK4tv0",
        "AIzaSyBGw8fxrdkXgvE_DzzTcBv79rbrbwFvfTw",
        "AIzaSyBydy_4kUUhRNVJfPh1Dr4yH4MTz7w0B5M",
        "AIzaSyB9HUtRKHfkaHfHuaAxfLSPkNpi3jBOiII",
        "AIzaSyAaZ25v5qmkSgOWw2WrWkg2327m3vbJweo",
        "AIzaSyAYLTzsN9zb95b9pfkJpeQ3eIl55vP2beQ",
        "AIzaSyAy4m8l1XXfBsYWDKt8s3camXL7II5b33I",
        "AIzaSyArtsaOWyGJNAgJo1IDh0HHL0vPeoXUb9Y",
        "AIzaSyAdYbLMPi6NBPjHtxGB3ZfUkQCpzpgqN6s",
        "AIzaSyBwxw_pagBwNEWDHnR3uMX2IewMFnhbkDM",
        "AIzaSyDhXk-wNrIJWqzTrDvwACl8yaJKMTkH91c",
        "AIzaSyC3fguJYsEURM5mz_NwHYDyOVYF0P6BZdM",
        "AIzaSyCbcP9VUOQbWEMPo3gPXWTuN_3oQARj930",
        "AIzaSyDbRwr71vF4TKR1h4itvVtOGn00invuYGg",
        "AIzaSyC7DntqYUxlWurji3nId3kRgnLqX7bFjrs",
        "AIzaSyAPhiaxyaICeIAJeFLGcotkllCiaZTMzJA",
        "AIzaSyAn_pHZZAaMwFKEHCUhle6fClWDi0NGjXY",
        "AIzaSyDrJL0ufugi5XY_diysM5LaxGDQJJy-k3k",
        "AIzaSyAjsJuIm1-Mwu0Wv7KTvEFUTy41DSjE8n0",
        "AIzaSyDkVsZZXvtgmxBnXOc4JerZcVSuJ4wo0ng",
        "AIzaSyDL7jnD97pwc8BkbZI88Aruzfka_QlYYpk",
        "AIzaSyBnFUR8vuYZFHLnr1cBYR8Ic8ytbcVGIGU",
        "AIzaSyBpkHRwWK3s5GU1U1ZiWvGZy4KZBAKm_iA",
        "AIzaSyBHdPVO6xetyA5aPzhxVSCsQvjbnB9togE",
        "AIzaSyD7MqYqNRiB9fy4yD7r50chRj7VAKzmmvM",
        "AIzaSyDxSIW9hAZUvLs3sl5RXSIP_YZYrS21R24",
        "AIzaSyDl9LJHYKZsvoTc-N5SHG_vPc_k5mxoBHY",
        "AIzaSyCK1YWbxIBcfCOZjHMgEFyHcD4qudBxVkY",
        "AIzaSyC6niegv3IKui9Ec2aMEBsS9XgqqYjC74Q",
        "AIzaSyAv8pJB8DndCLMWh5B2xUITMO2Ks6-jaSU",
        "AIzaSyAgnsGQPh5skgCNr82LEPSZRHPnjSUi1Dc",
        "AIzaSyBvEer8NaS2RWDzZeAb4TEyfveKJXsXW6Y",
        "AIzaSyDfkzaXilxRq4W6-d4QrLAfwi5qSRv39Yg",
        "AIzaSyCmDV5Qr9vroKJDPTwCcLCP9t-WPZSVvE8",
        "AIzaSyAd-gZNz4nm0jzx6KdNii3-bM_z66XqhV4",
        "AIzaSyBztgLNrKMBkxl7uwcEDILjIA5KTuL06Ik",
        "AIzaSyDhWSZu3ASbV9CJWQfKRDnZjUZHSoV-6rc",
        "AIzaSyDLnEhYOeksXNpLXsisyqXqZMgIBert-7U",
        "AIzaSyDN7QQFrO-RfDEaCw9E0t3mpH7zFf84rUI",
        "AIzaSyDNsJZ5zXWtAFywk9aQ5LkiwU7XQW7bvDE",
        "AIzaSyCugB48jsHC28I0bc5iP8E8mGhSkdgCZr4",
        "AIzaSyCMm_tAsisCH3QzOqj5ir6V2kypTnepynE",
        "AIzaSyC_g17PoLTGBDtrqg7Bf6Lx1eqj37Nn20c",
        "AIzaSyA6ZIAfKwyR3Qdh0f0lgtu_aLkUu2mPeEA",
        "AIzaSyDlyU9Fi8abu8Y6MvQZieTBbdNhEbRoWZE",
        "AIzaSyDuNw7-7zjXdLh2cBo6gpt2E0GZpd5ArLw",
        "AIzaSyCYM0N1f370Xw3RBPUYZQ7BXpQ3nKWLbdA",
        "AIzaSyAKgg0LEqZ9XLcV_TYwclCbp7Ys_Mh_JUU",
        "AIzaSyDV2pirWAwxTeVGnA7SNFAL_Mfkfdvcx8I",
        "AIzaSyAo08t-qa3DwRA3arXejUwu8krzVcKnP54",
        "AIzaSyAwxgmnAx0lUin5I0DPI-TpVFMLoLj13zA",
        "AIzaSyC6niegv3IKui9Ec2aMEBsS9XgqqYjC74Q",
        "AIzaSyAPhiaxyaICeIAJeFLGcotkllCiaZTMzJA",
        "AIzaSyD7MqYqNRiB9fy4yD7r50chRj7VAKzmmvM",
        "AIzaSyCMm_tAsisCH3QzOqj5ir6V2kypTnepynE",
        "AIzaSyDfkzaXilxRq4W6-d4QrLAfwi5qSRv39Yg",
        "AIzaSyCbcP9VUOQbWEMPo3gPXWTuN_3oQARj930",
        "AIzaSyAn_pHZZAaMwFKEHCUhle6fClWDi0NGjXY",
        "AIzaSyBnFUR8vuYZFHLnr1cBYR8Ic8ytbcVGIGU",
        "AIzaSyC7DntqYUxlWurji3nId3kRgnLqX7bFjrs",
        "AIzaSyBztgLNrKMBkxl7uwcEDILjIA5KTuL06Ik",
        "AIzaSyAd-gZNz4nm0jzx6KdNii3-bM_z66XqhV4",
        "AIzaSyDl9LJHYKZsvoTc-N5SHG_vPc_k5mxoBHY",
        "AIzaSyDLnEhYOeksXNpLXsisyqXqZMgIBert-7U",
        "AIzaSyAgnsGQPh5skgCNr82LEPSZRHPnjSUi1Dc",
        "AIzaSyDxSIW9hAZUvLs3sl5RXSIP_YZYrS21R24",
        "AIzaSyDL7jnD97pwc8BkbZI88Aruzfka_QlYYpk",
        "AIzaSyA6ZIAfKwyR3Qdh0f0lgtu_aLkUu2mPeEA",
        "AIzaSyDlyU9Fi8abu8Y6MvQZieTBbdNhEbRoWZE",
        "AIzaSyAo08t-qa3DwRA3arXejUwu8krzVcKnP54",
        "AIzaSyDrJL0ufugi5XY_diysM5LaxGDQJJy-k3k",
        "AIzaSyBpkHRwWK3s5GU1U1ZiWvGZy4KZBAKm_iA",
        "AIzaSyBvEer8NaS2RWDzZeAb4TEyfveKJXsXW6Y",
        "AIzaSyDNsJZ5zXWtAFywk9aQ5LkiwU7XQW7bvDE",
        "AIzaSyCK1YWbxIBcfCOZjHMgEFyHcD4qudBxVkY",
        "AIzaSyDN7QQFrO-RfDEaCw9E0t3mpH7zFf84rUI",
        "AIzaSyDkVsZZXvtgmxBnXOc4JerZcVSuJ4wo0ng",
        "AIzaSyDV2pirWAwxTeVGnA7SNFAL_Mfkfdvcx8I",
        "AIzaSyAKgg0LEqZ9XLcV_TYwclCbp7Ys_Mh_JUU",
        "AIzaSyC_g17PoLTGBDtrqg7Bf6Lx1eqj37Nn20c",
        "AIzaSyAjsJuIm1-Mwu0Wv7KTvEFUTy41DSjE8n0",
        "AIzaSyBHdPVO6xetyA5aPzhxVSCsQvjbnB9togE",
        "AIzaSyCmDV5Qr9vroKJDPTwCcLCP9t-WPZSVvE8",
        "AIzaSyAv8pJB8DndCLMWh5B2xUITMO2Ks6-jaSU",
        "AIzaSyCugB48jsHC28I0bc5iP8E8mGhSkdgCZr4",
        "AIzaSyDuNw7-7zjXdLh2cBo6gpt2E0GZpd5ArLw",
        "AIzaSyDhWSZu3ASbV9CJWQfKRDnZjUZHSoV-6rc",
        "AIzaSyAwxgmnAx0lUin5I0DPI-TpVFMLoLj13zA",
        "AIzaSyC5z6Fa5bDaRYNM2aHaDUK2ZTtVBbQnRgc",
        "AIzaSyAmTMRVY33S8bkwjS-CNsoNICmtrBIuCZY",
        "AIzaSyCsX_bKxjfvZmEmpdJY4JiTaLKCds0OY7o",
        "AIzaSyD8p_L1qHXCRF3nuGGrPEXcLk2w9A9SLPo",
        "AIzaSyBL58LUnb3XXoGlIukLCX3vOHKvNl7lPwo",
        "AIzaSyClZbJT8vGqfgXXmcF4Jz5_gbVEGlL80E4",
        "AIzaSyBpfP9fhZ28KhI2mcllJ9DE6UQJBN-0iSs",
        "AIzaSyDA3FTAmknGsIvH0RVdA-xKNidsk6Y2G6s",
        "AIzaSyBLhejhxA3iyJpczsL_76Rkd-9mTDZeGBc",
        "AIzaSyA1TAClFvWBEf0drnonfGCRNCXPSJcOSGQ",
        "AIzaSyBAXTCnJuKsZAwvZhtiiUeBcFnR6AaI0sE",
        "AIzaSyDUz4zTAPJcBaO7anPc_BRSHAhKRACh4t8",
        "AIzaSyBqNZ3vtfVtpoCQQhoi8jLViXuFl1MIPSw",
        "AIzaSyAudmTYRGOsCHMuFXwts1hI8fyTe12t4MA",
        "AIzaSyBpppTiAtPfzQkALdqLZk2KGcQZWbBCdto",
        "AIzaSyDOmPr-gv2lOjKUtLRcvPo3wHPmbZ6_ndg",
        "AIzaSyBM3fSR7_hI2VmeGldwkC2bQcE-GNqBAa4",
        "AIzaSyCUqDVOhHuzygH2H4FSR2pyLNVsyjsBBjE",
        "AIzaSyD2BNUlw3ChlT6LxfN1tsCy2BTE7i-0Wxk",
        "AIzaSyDFO0EkmM8pviD_0L38vCQh7p34WiYxjE4",
        "AIzaSyBlU7B1hne4r9mZew0WmEKEg4F4hqxVgCM",
        "AIzaSyB1mxUy02w7cJwICiyYosCL2ZEz5HTLyic",
        "AIzaSyC8rgLVshhb_CNwsrbqmgUCu0PKn4jYQOw",
        "AIzaSyBNK02-41aLtI2iGRrWbwTYss2HIQNWVnU",
        "AIzaSyCPlomHLQGn31lZtrGBjcPrTMMW1Ti7nZY",
        "AIzaSyBaOg5-GmdR3fdHwq9lsF9jz4_TS7lZDns",
        "AIzaSyChf0F5iLxpYTqXeiiw8gW3dIKQn73sOac",
        "AIzaSyA_13kYeDcvnpEK0Zuo_sfvMYglOZf-y9E",
        "AIzaSyB-2XSKECeWIWDjBY7BDbDt38fSLziNvqw",
        "AIzaSyCLeWMGnkBndhh_PyJxebYFSKHeQuBDWok",
        "AIzaSyD9A5Ra-g2a1lLGQRTBbPaewqnQ0soHMGk",
        "AIzaSyCDJ2emeDM6EMlDJqfeFaA8OcD5I-tYlhI",
        "AIzaSyBLHy0y_egsqa_YSJh28VL8h9qcuia9UI8",
        "AIzaSyA5HztwuGqo1mZwVxrs2QH64QYo49y2Wc4",
        "AIzaSyA7753GY6V_1ZFEdG3Zh0oFUpcXP4QBtNw",
        "AIzaSyDvBIe2YeMt94t5-I74u8ZJLAxHPDd3nE4",
        "AIzaSyAHqJi0yaqOBSw_7drrSJ12AZXwP-eXJi8",
        "AIzaSyCE71dyg6U1vpOiuiQhad0DxXGkivO-u0A",
        "AIzaSyCzlTyhKfjO8mq0pDXFjHBgv8uV61YVmNE",
        "AIzaSyBXPCb8uwQjPWqUmhq8DzTKYKrSgJsYyYg",
        "AIzaSyAm3J02hqXl6XaWcWJGzoe8yRg7Rkpxswg",
        "AIzaSyDBFVmbwWmH7mFi8AYGoh26Hlok8Tu3Xss",
        "AIzaSyAE4zEuui4T5z8Wh2B1V5J2QmwmTK-RiCA",
        "AIzaSyBFm3asW0XRIJMrqA5okIQYeqJVskpg_Yw",
        "AIzaSyCSFi90LBOygHoW4gtDJ834CEvQuwPSaRI",
        "AIzaSyDhaL-XZTzUXsUalp6RMfl0TXEDylCLgG0",
        "AIzaSyBQxOXk_XurqdS8M7FZ9DiMyyR7yDxIbWM",
        "AIzaSyDjz3vNxZN2SHkFkXvU5idvSYLZBoAPo8M",
        "AIzaSyBWVhUNayvR1H1ChZYqIeWrkgMQhMXYDrw",
        "AIzaSyD5sEavucUgJa6bBZwaVmoVKNqq3mMQPZA",
        "AIzaSyDZ-Nqcfp4eNDedMxfpfkYUxYIB84Kt_W4",
        "AIzaSyCXCQitwGJSkz8X-kBGQS8z3XO6TNKHCu4",
        "AIzaSyCy1ZfgJy_gOTYufVIE_Ca0BnR_Qd9XJQY",
        "AIzaSyACEGZm2ihyO0I7WpknrVh3ebfratsWjz0",
        "AIzaSyCduUyUI54vjt2ta2RRLBrqUZPrIcy8EfU",
        "AIzaSyA5KJ-xputP-FHCRXKElsSdp9-5SQxyCTs",
        "AIzaSyBdRN7OyD2titBCL4X-55O9vbcAba5byrg",
        "AIzaSyA42UuVN0P_tqk3kfirmQ1PfhEjaSv9Lyg",
        "AIzaSyCf7WbrdS3wubhkPuqWgkLa7G4Af6Y33ng",
        "AIzaSyBPAP9htdVj-YX-UUQUcHovpOSRcuf30hI",
        "AIzaSyBLpZuQjVimQ-knADzWHj8RRq1XraPjZMQ",
        "AIzaSyDm5QzWanwKPrworu06fZ1TjnSH5eesllE",
        "AIzaSyDxk2au7bVT0cu-y1613pAgO2HkFqeiXOM",
        "AIzaSyCLsX7OxrywzQqiLEvOqA3wc4N-dtACbzQ",
        "AIzaSyDJkPaIP6wnSm7L16IzbVyTNMRTISVm3n4",
        "AIzaSyBiuG-8JIsKm0uvWv8Mj_bAYCyngWSgfQQ",
        "AIzaSyBLbeyy_RLT-MVvWy9vMeKmbJVSjlN1mRU",
        "AIzaSyDhY38M3HUHNI1DzxkAtF9QBhHTgT8GswI",
        "AIzaSyBwevPpaA7qaToWM4zrQB0052BmsMdKq9s",
        "AIzaSyCw7LsJjBgcV4HitTkDQv3bibqpns-ZbeE",
        "AIzaSyD5_0ZDRj86exG4AKkpR0-M3-Qc_Qy_Y2o",
        "AIzaSyCbLBd7iw4t1FBdp9ki5Er4mRNTsaxWCMQ",
        "AIzaSyAppct2w3roEGc5IBhs0_-gkmmJnrulu4s",
        "AIzaSyC6OA5lrtQU_QdrX6nxxK09Uy05MAEAv1E",
        "AIzaSyBsVrFSYaFWLUgvF3JaD_hIxG9gdWFMsyE",
        "AIzaSyA_IFYpzWfUdSaHiaM9-afFCKvxjRaSuNw",
        "AIzaSyB4rj1IP74fGUA4DBZeJvi3IHT_KSO1-Hg",
        "AIzaSyD7kSxIqOkQ5448xPXxkeGEqgqYVPzwBkg",
        "AIzaSyAHrf-15lzGWW3I_dmNgTKZovABW_9O1tE",
        "AIzaSyAWUMi39YwwzImUOQKpY5SW4lrMRdIHgYg",
        "AIzaSyB2Tbn-g7dc30Fttox_X2sM1kRTEskCxQ8",
        "AIzaSyD_vS1a7-ZevD2zCLsmlKK81hY9_2lqfKU",
        "AIzaSyAfAuPFGj3xemvroftnLzFxTEUyixlI8d0",
        "AIzaSyAUu3j-iOz7zRNRtyGEGY1PVF8uoClDJF4",
        "AIzaSyCP-UEFjRyJdrr_MFuBqcx6cUJ_53xLlpU",
        "AIzaSyDM1MgjwRfxYlC1YiJFHwOYoAk51nGTCJo",
        "AIzaSyAIjuHCy0zBqX2fgW1eetmLjqrloiSLzh8",
        "AIzaSyCCUuRSz4g87bBgVS3TZUHvWx3Mb3Qobcw",
        "AIzaSyBE4g3uKNIxDw5JGY-7EUdI5nXRtGYvgpU"
    ]
    
    print(f"🔄 Đang thêm {len(gemini_keys)} Gemini API keys vào database...")
    
    # Connect to database
    conn = sqlite3.connect('backend/voice_api.db')
    cursor = conn.cursor()
    
    added_count = 0
    skipped_count = 0
    
    for api_key in gemini_keys:
        try:
            # Check if key already exists
            cursor.execute('SELECT id FROM gemini_keys WHERE api_key = ?', (api_key,))
            if cursor.fetchone():
                print(f"⏭️  Key đã tồn tại: {api_key[:20]}...")
                skipped_count += 1
                continue
            
            # Insert new key
            cursor.execute('''
                INSERT INTO gemini_keys (api_key, is_active, created_at)
                VALUES (?, 1, CURRENT_TIMESTAMP)
            ''', (api_key,))
            
            print(f"✅ Đã thêm: {api_key[:20]}...")
            added_count += 1
            
        except Exception as e:
            print(f"❌ Lỗi khi thêm key {api_key[:20]}...: {e}")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Hoàn thành!")
    print(f"✅ Đã thêm: {added_count} keys")
    print(f"⏭️  Đã bỏ qua: {skipped_count} keys (đã tồn tại)")
    print(f"📊 Tổng cộng: {len(gemini_keys)} keys")

if __name__ == "__main__":
    add_gemini_keys()