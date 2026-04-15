#!/bin/bash
# Haptic Vision - Raspberry Pi Setup Script
# Usage: cd ~/haptic-vision && chmod +x setup.sh && ./setup.sh

set -e

echo "=== Haptic Vision Setup ==="
echo ""

# 1. System packages
echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-libcamera \
    python3-picamera2 \
    i2c-tools \
    libopencv-dev

# 2. Verify I2C is enabled
echo ""
echo "[2/5] Checking I2C configuration..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
    echo "WARNING: I2C does not appear to be enabled in config.txt"
    echo "Add these lines to config.txt under [all]:"
    echo "  dtparam=i2c_arm=on"
    echo "  dtparam=i2c_arm_baudrate=400000"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
fi

# Ensure i2c-dev module loads at boot
if ! grep -q "i2c-dev" /etc/modules 2>/dev/null; then
    echo "i2c-dev" | sudo tee -a /etc/modules
fi
sudo modprobe i2c-dev 2>/dev/null || true

# 3. Python virtual environment
echo ""
echo "[3/5] Creating Python virtual environment..."
python3 -m venv --system-site-packages venv
source venv/bin/activate

# --system-site-packages gives access to system-installed picamera2
# and libcamera bindings which cannot be installed via pip.

# 4. Python dependencies
echo ""
echo "[4/5] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. I2C scan
echo ""
echo "[5/5] Scanning I2C bus..."
i2cdetect -y 1 || echo "I2C scan failed - check wiring and config.txt"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Test commands:"
echo "  source venv/bin/activate"
echo "  python tools/i2c_scan.py      # verify PCA9685 boards"
echo "  python tools/calibrate.py     # test individual motors"
echo "  python tools/grid_test.py     # pattern tests"
echo "  python tools/benchmark.py     # latency measurement"
echo "  python main.py                # run the pipeline"
echo "  python main.py -v             # run with debug logging"
echo ""
echo "To install as a systemd service:"
echo "  sudo cp haptic-vision.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable haptic-vision"
echo "  sudo systemctl start haptic-vision"
