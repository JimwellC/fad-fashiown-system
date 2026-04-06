# detection/capture.py
# Takes screenshots of a specific screen region
# This is where the TikTok pinned comment appears

import mss
import mss.tools
from PIL import Image
import io
import config

def capture_region(zone=None):
    """
    Captures a screenshot of the defined screen region.
    
    Args:
        zone: dict with left, top, width, height (uses config if None)
    
    Returns:
        PIL Image object of the captured region
    """
    if zone is None:
        zone = config.CAPTURE_ZONE

    with mss.mss() as sct:
        # Take screenshot of the specific region
        screenshot = sct.grab(zone)
        
        # Convert to PIL Image for processing
        img = Image.frombytes(
            'RGB',
            screenshot.size,
            screenshot.bgra,
            'raw',
            'BGRX'
        )
        
        return img


def capture_full_screen():
    """
    Captures the entire screen.
    Used during calibration to let seller select the zone.
    
    Returns:
        PIL Image of the full screen
    """
    with mss.mss() as sct:
        # Get the main monitor
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        
        img = Image.frombytes(
            'RGB',
            screenshot.size,
            screenshot.bgra,
            'raw',
            'BGRX'
        )
        
        return img


def get_screen_size():
    """
    Returns the size of the main monitor.
    Used for calibration positioning.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        return {
            "width": monitor["width"],
            "height": monitor["height"]
        }


def save_debug_screenshot(img, filename="debug_capture.png"):
    """
    Saves a screenshot to disk for debugging.
    Useful when OCR is not reading correctly.
    """
    img.save(filename)
    print(f"📸 Debug screenshot saved: {filename}")