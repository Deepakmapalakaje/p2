#!/usr/bin/env python3
"""
Quick fix for logging configuration
"""

# Read the current pipeline1.py file
with open('pipeline1.py', 'r') as f:
    content = f.read()

# Replace the logging configuration
old_text = "logging.FileHandler('upstox_v3_trading.log', encoding='utf-8'),"
new_text = "logging.FileHandler('logs/upstox_v3_trading.log', encoding='utf-8'),"

content = content.replace(old_text, new_text)

# Write back the fixed content
with open('pipeline1.py', 'w') as f:
    f.write(content)

print("✅ Logging configuration fixed!")
print("Now the logger will write to 'logs/upstox_v3_trading.log'")
