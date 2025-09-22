#!/usr/bin/env python3
"""
Database Initialization Script for TrendVision
This script creates all required database tables and initializes the system
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database paths
TRADING_DB = "database/upstox_v3_live_trading.db"
USER_DB = "database/users.db"

def create_database_directory():
    """Create database directory if it doesn't exist"""
    os.makedirs("database", exist_ok=True)
    logger.info("✅ Database directory created/verified")

def init_user_database():
    """Initialize user database with all required tables"""
    logger.info("🔧 Initializing user database...")

    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_active INTEGER DEFAULT 1,
        login_attempts INTEGER DEFAULT 0,
        locked_until DATETIME DEFAULT NULL,
        last_login DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("✅ Users table created")

    # Create sessions table for persistent sessions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_token TEXT UNIQUE NOT NULL,
        expires_at DATETIME NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    logger.info("✅ Sessions table created")

    # Create admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'dsar'")
    if not cursor.fetchone():
        admin_password = generate_password_hash('dsar')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ('dsar', 'admin@trendvision2004.com', admin_password, 'admin')
        )
        logger.info("✅ Admin user created: dsar/dsar")

    # Create test users for development
    test_users = [
        ('testuser1', 'test1@example.com', 'password123', 'user'),
        ('testuser2', 'test2@example.com', 'password123', 'user'),
        ('trader1', 'trader1@example.com', 'password123', 'user'),
    ]

    for username, email, password, role in test_users:
        cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email))
        if not cursor.fetchone():
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, role)
            )
            logger.info(f"✅ Test user created: {username}/{password}")

    conn.commit()
    conn.close()
    logger.info("✅ User database initialization completed")

def init_trading_database():
    """Initialize trading database with all required tables"""
    logger.info("🔧 Initializing trading database...")

    conn = sqlite3.connect(TRADING_DB)
    cursor = conn.cursor()

    # Create table registry
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS table_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT UNIQUE NOT NULL,
        data_type TEXT NOT NULL,
        date_created DATE DEFAULT CURRENT_DATE,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("✅ Table registry created")

    # Create trend table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trend (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP NOT NULL,
        interval_type TEXT NOT NULL,
        instrument_key TEXT NOT NULL,
        trend_value INTEGER,
        buy_recommendation TEXT,
        entry_price REAL,
        target REAL,
        sl REAL,
        profit_loss REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("✅ Trend table created")

    # Create latest_candles table with all required columns
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS latest_candles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instrument_key TEXT NOT NULL,
        instrument_name TEXT,
        instrument_type TEXT,
        strike_price REAL,
        option_type TEXT,
        timestamp TIMESTAMP NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        atp REAL,
        vwap REAL,
        price_change REAL,
        price_change_pct REAL,
        delta INTEGER,
        delta_pct REAL,
        min_delta INTEGER,
        max_delta INTEGER,
        buy_volume INTEGER,
        sell_volume INTEGER,
        tick_count INTEGER,
        vtt_open REAL,
        vtt_close REAL,
        candle_interval TEXT,
        trend_value INTEGER,
        buy_recommendation TEXT,
        entry_price REAL,
        target REAL,
        sl REAL,
        profit_loss REAL,
        prev_close REAL,
        intraday_high REAL,
        intraday_low REAL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("✅ Latest candles table created")

    # Create options_cash_flow table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS options_cash_flow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP NOT NULL,
        interval_type TEXT NOT NULL,
        cash REAL DEFAULT 0.0,
        min_cash REAL DEFAULT 0.0,
        max_cash REAL DEFAULT 0.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("✅ Options cash flow table created")

    # Create buy_signals table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS buy_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP NOT NULL,
        signal_type TEXT NOT NULL,
        option_key TEXT NOT NULL,
        strike REAL NOT NULL,
        entry_price REAL,
        target REAL,
        sl REAL,
        status TEXT DEFAULT 'ACTIVE',
        cash_flow REAL DEFAULT 0.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("✅ Buy signals table created")

    # Create option_tracking table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS option_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        option_key TEXT NOT NULL,
        strike REAL NOT NULL,
        option_type TEXT NOT NULL,
        entry_timestamp TIMESTAMP NOT NULL,
        exit_timestamp TIMESTAMP,
        entry_price REAL,
        exit_price REAL,
        profit_loss REAL,
        status TEXT DEFAULT 'ACTIVE',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("✅ Option tracking table created")

    # Create indexes for better performance
    indexes = [
        ("idx_trend_timestamp", "trend", "timestamp"),
        ("idx_trend_interval", "trend", "interval_type"),
        ("idx_latest_candles_instrument", "latest_candles", "instrument_key"),
        ("idx_latest_candles_updated", "latest_candles", "last_updated"),
        ("idx_latest_candles_timestamp", "latest_candles", "timestamp"),
        ("idx_latest_candles_instrument_interval", "latest_candles", "instrument_key, timestamp"),
        ("idx_table_registry_date_instrument", "table_registry", "date_created"),
        ("idx_table_registry_data_type", "table_registry", "data_type"),
    ]

    for index_name, table_name, columns in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
            logger.info(f"✅ Index {index_name} created")
        except Exception as e:
            logger.warning(f"⚠️ Could not create index {index_name}: {e}")

    # Insert sample data for testing
    try:
        # Sample cash flow data
        cursor.execute("SELECT COUNT(*) FROM options_cash_flow")
        if cursor.fetchone()[0] == 0:
            sample_cash_flow = [
                (datetime.now().isoformat(), '1min', 100000.0, 50000.0, 150000.0),
                (datetime.now().isoformat(), '5min', 250000.0, 100000.0, 300000.0),
            ]
            cursor.executemany(
                "INSERT INTO options_cash_flow (timestamp, interval_type, cash, min_cash, max_cash) VALUES (?, ?, ?, ?, ?)",
                sample_cash_flow
            )
            logger.info("✅ Sample cash flow data inserted")

        # Sample trend data
        cursor.execute("SELECT COUNT(*) FROM trend")
        if cursor.fetchone()[0] == 0:
            sample_trends = [
                (datetime.now().isoformat(), '1min', 'NSE_INDEX|Nifty 50', 1, 'BUY', 25000.0, 25200.0, 24800.0, 0.0),
                (datetime.now().isoformat(), '5min', 'NSE_INDEX|Nifty 50', -1, 'SELL', 25100.0, 25300.0, 24900.0, 0.0),
            ]
            cursor.executemany(
                "INSERT INTO trend (timestamp, interval_type, instrument_key, trend_value, buy_recommendation, entry_price, target, sl, profit_loss) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                sample_trends
            )
            logger.info("✅ Sample trend data inserted")

    except Exception as e:
        logger.warning(f"⚠️ Could not insert sample data: {e}")

    conn.commit()
    conn.close()
    logger.info("✅ Trading database initialization completed")

def verify_database():
    """Verify that all tables and columns are created correctly"""
    logger.info("🔍 Verifying database setup...")

    # Check user database
    try:
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        user_tables = [row[0] for row in cursor.fetchall()]

        required_user_tables = ['users', 'sessions']
        for table in required_user_tables:
            if table in user_tables:
                logger.info(f"✅ User table '{table}' exists")
            else:
                logger.error(f"❌ User table '{table}' missing")

        # Check user count
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        logger.info(f"✅ User database has {user_count} users")

        conn.close()
    except Exception as e:
        logger.error(f"❌ User database verification failed: {e}")

    # Check trading database
    try:
        conn = sqlite3.connect(TRADING_DB)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        trading_tables = [row[0] for row in cursor.fetchall()]

        required_trading_tables = ['table_registry', 'trend', 'latest_candles', 'options_cash_flow', 'buy_signals', 'option_tracking']
        for table in required_trading_tables:
            if table in trading_tables:
                logger.info(f"✅ Trading table '{table}' exists")
            else:
                logger.error(f"❌ Trading table '{table}' missing")

        # Check table counts
        for table in required_trading_tables:
            if table in trading_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Table '{table}' has {count} records")

        conn.close()
    except Exception as e:
        logger.error(f"❌ Trading database verification failed: {e}")

    logger.info("✅ Database verification completed")

def main():
    """Main function to initialize everything"""
    logger.info("🚀 Starting TrendVision database initialization...")

    try:
        # Create database directory
        create_database_directory()

        # Initialize databases
        init_user_database()
        init_trading_database()

        # Verify setup
        verify_database()

        logger.info("🎉 Database initialization completed successfully!")
        logger.info("📊 Database Summary:")
        logger.info(f"   • User Database: {USER_DB}")
        logger.info(f"   • Trading Database: {TRADING_DB}")
        logger.info("   • All required tables created")
        logger.info("   • Sample data inserted for testing")
        logger.info("   • Ready for VM deployment")

        print("\n" + "="*60)
        print("DATABASE INITIALIZATION COMPLETE")
        print("="*60)
        print("✅ All required tables and columns have been created")
        print("✅ Sample data inserted for testing")
        print("✅ Database is ready for VM deployment")
        print("="*60)
        print("\nTo start the application:")
        print("1. Run: python3 app.py")
        print("2. Access: http://127.0.0.1:8000")
        print("3. Admin login: dsar/dsar")
        print("="*60)

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

if __name__ == "__main__":
    main()
