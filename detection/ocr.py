# detection/ocr.py
# Reads text from screenshots using Tesseract OCR
# Extracts and cleans the TikTok username from pinned comment

import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import re
import config

# Track consecutive reads for confirmation
_consecutive_reads = {}


def preprocess_image(img):
    """
    Enhances the image before OCR to improve accuracy.
    TikTok UI is dark with white/colored text - we optimize for this.
    
    Args:
        img: PIL Image
    
    Returns:
        Processed PIL Image ready for OCR
    """
    # Convert PIL to OpenCV format
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Increase contrast using CLAHE
    # (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Apply threshold to make text sharper
    # This converts image to pure black and white
    _, thresh = cv2.threshold(
        enhanced, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    
    # Scale up image 2x for better OCR accuracy
    height, width = thresh.shape
    scaled = cv2.resize(
        thresh,
        (width * 2, height * 2),
        interpolation=cv2.INTER_CUBIC
    )
    
    # Convert back to PIL Image
    result = Image.fromarray(scaled)
    
    return result


def extract_text(img):
    """
    Runs OCR on the image and returns raw text.
    
    Args:
        img: PIL Image (already preprocessed)
    
    Returns:
        Raw string of detected text
    """
    # Tesseract config for better username detection
    # --psm 7 = treat image as single line of text
    # --oem 3 = use LSTM neural net engine
    custom_config = r'--oem 3 --psm 7'
    
    text = pytesseract.image_to_string(img, config=custom_config)
    
    return text


def clean_username(raw_text):
    """
    Cleans up OCR output to extract just the username.
    TikTok usernames can contain letters, numbers, dots, underscores.
    
    Args:
        raw_text: Raw string from OCR
    
    Returns:
        Cleaned username string or empty string if invalid
    """
    if not raw_text:
        return ""
    
    # Remove newlines and extra spaces
    text = raw_text.strip().replace('\n', ' ').replace('\r', '')
    
    # Remove the @ symbol if present (we add it back in display)
    text = text.replace('@', '')
    
    # Keep only valid TikTok username characters
    # TikTok allows: letters, numbers, underscores, dots
    text = re.sub(r'[^a-zA-Z0-9._]', '', text)
    
    # Remove leading/trailing dots or underscores
    text = text.strip('._')
    
    return text.lower()


def is_valid_username(username):
    """
    Checks if the extracted text looks like a real TikTok username.
    
    Args:
        username: Cleaned username string
    
    Returns:
        True if valid, False if garbage OCR output
    """
    if not username:
        return False
    
    # Must be at least 3 characters
    if len(username) < config.MIN_USERNAME_LENGTH:
        return False
    
    # Must be no more than 24 characters (TikTok limit)
    if len(username) > 24:
        return False
    
    # Must contain at least one letter or number
    if not re.search(r'[a-zA-Z0-9]', username):
        return False
    
    # Reject common OCR garbage patterns
    garbage_patterns = ['|||', '---', '===', '...', '###']
    for pattern in garbage_patterns:
        if pattern in username:
            return False
    
    return True


def confirm_username(username):
    """
    Uses consecutive read confirmation to prevent false positives.
    The same username must be read N times before it's confirmed.
    
    Args:
        username: Cleaned username string
    
    Returns:
        True if username is confirmed (seen enough times), False otherwise
    """
    global _consecutive_reads
    
    if not username:
        _consecutive_reads = {}
        return False
    
    # Count how many times we've seen this username
    if username not in _consecutive_reads:
        # Reset all counts (new username appeared)
        _consecutive_reads = {username: 1}
    else:
        _consecutive_reads[username] += 1
    
    count = _consecutive_reads[username]
    
    print(f"👁️  OCR read '{username}' ({count}/{config.CONFIRMATION_THRESHOLD})")
    
    # Only confirm after seeing it N consecutive times
    if count >= config.CONFIRMATION_THRESHOLD:
        # Reset counter so same username 
        # doesn't trigger again unless it changes
        _consecutive_reads = {}
        return True
    
    return False


def detect_pinned_username(img):
    """
    Main detection function.
    Takes a screenshot image and returns confirmed username or None.
    
    Args:
        img: PIL Image of the capture zone
    
    Returns:
        Confirmed username string, or None if not ready yet
    """
    try:
        # Step 1: Preprocess image for better OCR
        processed = preprocess_image(img)
        
        # Step 2: Extract raw text
        raw_text = extract_text(processed)
        
        # Step 3: Clean up the text
        username = clean_username(raw_text)