#!/usr/bin/env python3
"""
Fix logging configuration in pipeline1.py
"""

import re

# Read the current pipeline1.py file
with open('pipeline1.py', 'r') as f:
    content = f.read()

# Fix the logging configuration
# Replace the log_locations list to prioritize logs directory
old_pattern = r"log_locations = \[\s*'upstox_v3_trading\.log',\s*'/tmp/upstox_v3_trading\.log',\s*'logs/upstox_v3_trading\.log'\s*\]"
new_pattern = "log_locations = [\n            'logs/upstox_v3_trading.log',\n            '/tmp/upstox_v3_trading.log'\n        ]"

content = re.sub(old_pattern, new_pattern, content, flags=re.MULTILINE | re.DOTALL)

# Write back the fixed content
with open('pipeline1.py', 'w') as f:
    f.write(content)

print("✅ Logging configuration fixed successfully!")
print("Now the logger will prioritize 'logs/upstox_v3_trading.log' first")
