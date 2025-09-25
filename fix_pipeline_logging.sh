#!/bin/bash
# Fix pipeline logging configuration

cd /opt/trendvision

# Create the corrected logging setup
sudo tee /tmp/setup_logging.patch <<'EOF'
# === LOGGING SETUP (MOVED UP FOR EARLY IMPORT USAGE) ===
def setup_logging():
    log_locations = [
        "logs/upstox_v3_trading.log",
        "/tmp/upstox_v3_trading.log"
    ]

    os.makedirs("logs", exist_ok=True)

    for location in log_locations:
        try:
            file_handler = logging.FileHandler(location, encoding="utf-8")
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                handlers=[
                    file_handler,
                    logging.StreamHandler(sys.stdout)
                ]
            )
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setStream(sys.stdout)
            logger = logging.getLogger("UpstoxTradingV3")
            logger.info(f"Logging initialized: {location}")
            return logger
        except PermissionError:
            continue

    raise SystemExit("ERROR: Unable to initialize logging in any location")
EOF

# Apply the patch to pipeline1.py
python3 - <<PYEOF
from pathlib import Path
path = Path("pipeline1.py")
text = path.read_text(encoding="utf-8")
start = text.index("# === LOGGING SETUP")
end = text.index("logger = setup_logging()", start)
header = text[:start]
tail = text[end:]
replacement = Path("/tmp/setup_logging.patch").read_text()
path.write_text(header + replacement + "\nlogger = setup_logging()" + tail, encoding="utf-8")
print("✅ Logging configuration updated successfully!")
PYEOF

# Fix file permissions and create logs directory
sudo rm -f /opt/trendvision/upstox_v3_trading.log
sudo mkdir -p /opt/trendvision/logs
sudo touch /opt/trendvision/logs/upstox_v3_trading.log
sudo chown -R trendvision:trendvision /opt/trendvision/logs

echo "✅ Logs directory setup completed!"
