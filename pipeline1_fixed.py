#!/usr/bin/env python3
"""
Fixed pipeline1.py with corrected logging configuration
"""

# Just the logging setup function fix
logging_setup_fix = '''
    # Try to create file handler, but don't fail if it doesn't work
    try:
        # Try different log file locations - prioritize logs directory
        log_locations = [
            'logs/upstox_v3_trading.log',
            '/tmp/upstox_v3_trading.log'
        ]

        for log_file in log_locations:
            try:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.INFO)
                file_formatter = logging.Formatter(log_format)
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
                logger.info(f"File logging enabled: {log_file}")
                break
            except (PermissionError, OSError):
                continue
'''

print("✅ Created fixed logging configuration")
print("Now you can manually replace the logging setup in pipeline1.py with this corrected version")
