# detection/ocr.py
# Reads text from screenshots using Tesseract OCR
# Uses only Pillow for image processing (no opencv needed)

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import re
import config

# Track consecutive reads for confirmation
_consecutive_reads = {}


def preprocess_image(img):
    """
    Enhances the image before OCR to improve accuracy.
    Uses only Pillow - no opencv required.
    """
    # Convert to grayscale
    gray = img.convert('L')

    # Increase size 2x for better OCR accuracy
    width, height = gray.size
    scaled = gray.resize(
        (width * 2, height * 2),
        Image.LANCZOS
    )

    # Increase contrast
    enhancer = ImageEnhance.Contrast(scaled)
    contrasted = enhancer.enhance(3.0)

    # Increase sharpness
    sharpener = ImageEnhance.Sharpness(contrasted)
    sharpened = sharpener.enhance(2.0)

    # Apply threshold to make text pure black/white
    # Pixels brighter than 128 become white, darker become black
    threshold = sharpened.point(lambda x: 255 if x > 128 else 0, '1')

    # Convert back to RGB for tesseract
    result = threshold.convert('RGB')

    return result


def extract_text(img):
    """Runs OCR on the image and returns raw text."""
    # --psm 7 = single line of text
    # --oem 3 = LSTM engine
    custom_config = r'--oem 3 --psm 7'
    text = pytesseract.image_to_string(img, config=custom_config)
    return text


def clean_username(raw_text):
    """
    Cleans up OCR output to extract just the username.
    TikTok usernames: letters, numbers, dots, underscores.
    """
    if not raw_text:
        return ""

    # Remove newlines and extra spaces
    text = raw_text.strip().replace('\n', ' ').replace('\r', '')

    # Remove @ symbol (we add it back in display)
    text = text.replace('@', '')

    # Keep only valid TikTok username characters
    text = re.sub(r'[^a-zA-Z0-9._]', '', text)

    # Remove leading/trailing dots or underscores
    text = text.strip('._')

    return text.lower()


def is_valid_username(username):
    """
    Checks if extracted text looks like a real TikTok username.
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
    garbage_patterns = ['|||', '---', '===', '###']
    for pattern in garbage_patterns:
        if pattern in username:
            return False

    return True


def confirm_username(username):
    """
    Uses consecutive read confirmation to prevent false positives.
    Same username must be read N times before confirmed.
    """
    global _consecutive_reads

    if not username:
        _consecutive_reads = {}
        return False

    # Count how many times we've seen this username
    if username not in _consecutive_reads:
        _consecutive_reads = {username: 1}
    else:
        _consecutive_reads[username] += 1

    count = _consecutive_reads[username]
    print(f"👁️  OCR read '{username}' ({count}/{config.CONFIRMATION_THRESHOLD})")

    if count >= config.CONFIRMATION_THRESHOLD:
        # Reset so same username doesn't trigger again
        _consecutive_reads = {}
        return True

    return False


def detect_pinned_username(img):
    """
    Main detection function.
    Takes a screenshot image and returns confirmed username or None.
    """
    try:
        # Step 1: Preprocess image
        processed = preprocess_image(img)

        # Step 2: Extract raw text
        raw_text = extract_text(processed)

        # Step 3: Clean up the text
        username = clean_username(raw_text)

        if not username:
            return None

        # Step 4: Validate it looks like a username
        if not is_valid_username(username):
            print(f"⚠️  Invalid username rejected: '{username}'")
            return None

        # Step 5: Confirm via consecutive reads
        if confirm_username(username):
            return username

        return None

    except Exception as e:
        print(f"❌ OCR Error: {e}")
        return None