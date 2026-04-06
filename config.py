# config.py
# Central settings for the Fad Fashiown System
# Edit these values to match your setup

# --- APP SETTINGS ---
APP_NAME = "Fad Fashiown Live Selling System"
DEBUG = True
PORT = 5000

# --- SCREEN CAPTURE SETTINGS ---
# This defines the region of your screen where the
# pinned comment appears on TikTok Live
# We will calibrate this properly in Phase 2
# Format: (left, top, width, height) in pixels
CAPTURE_ZONE = {
    "left": 0,
    "top": 0,
    "width": 400,
    "height": 100
}

# How often to scan the screen (in seconds)
# 1.5 seconds is a good balance of speed vs CPU usage
SCAN_INTERVAL = 1.5

# --- OCR SETTINGS ---
# Minimum characters for a valid username detection
MIN_USERNAME_LENGTH = 3

# How many consecutive identical reads before confirming
# Prevents false positives from flickering text
CONFIRMATION_THRESHOLD = 2

# --- DATABASE SETTINGS ---
DATABASE_PATH = "database/orders.db"

# --- PRINTER SETTINGS ---
# Set this to your printer's name
# We will detect this automatically in Phase 4
PRINTER_NAME = None  # Will auto-detect if None

# Label size in millimeters
LABEL_WIDTH_MM = 50
LABEL_HEIGHT_MM = 30

# --- BUSINESS SETTINGS ---
BUSINESS_NAME = "Fad Fashiown"
CURRENCY = "₱"