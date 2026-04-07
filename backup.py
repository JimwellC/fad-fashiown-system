# backup.py
# Run this daily to backup your database
# Add to cron job: 0 2 * * * python3 /path/to/backup.py

import shutil
import os
from datetime import datetime

# Source database
DB_PATH = "database/fadfashiown.db"

# Backup folder
BACKUP_DIR = "database/backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Create backup with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = f"{BACKUP_DIR}/fadfashiown_{timestamp}.db"

shutil.copy2(DB_PATH, backup_path)
print(f"✅ Backup created: {backup_path}")

# Keep only last 7 backups
backups = sorted(os.listdir(BACKUP_DIR))
while len(backups) > 7:
    oldest = os.path.join(BACKUP_DIR, backups.pop(0))
    os.remove(oldest)
    print(f"🗑️ Old backup removed: {oldest}")