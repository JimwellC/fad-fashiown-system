# detection/calibration.py
# Calibration tool - Mac Retina display compatible
# Lets seller draw a box around the pinned comment area

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CalibrationTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Fad Fashiown - Capture Zone Calibration")
        self.root.configure(bg="#1a1a2e")

        # Rectangle drawing state
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.selected_zone = None

        # Screenshot and display
        self.screenshot = None
        self.tk_image = None
        self.display_width = None
        self.display_height = None
        self.actual_width = None
        self.actual_height = None

        self.setup_ui()

    def take_screenshot(self):
        """Take screenshot using Mac screencapture for Retina accuracy"""
        import subprocess

        # Use Mac's built-in screencapture (handles Retina correctly)
        temp_path = "/tmp/fad_calibration.png"
        subprocess.run(
            ["screencapture", "-x", temp_path],
            check=True
        )

        img = Image.open(temp_path)
        return img

    def setup_ui(self):
        """Set up the calibration window"""

        # Instructions
        tk.Label(
            self.root,
            text="📌 STEP 1: Make sure TikTok Live is visible behind this window\n"
                 "STEP 2: Click 'Take Screenshot' button below\n"
                 "STEP 3: Draw a rectangle around the PINNED COMMENT area\n"
                 "STEP 4: Click Save Zone",
            font=("Arial", 13),
            bg="#1a1a2e",
            fg="white",
            pady=10,
            justify=tk.LEFT
        ).pack(fill=tk.X, padx=20)

        # Screenshot button at top
        tk.Button(
            self.root,
            text="📸 Take Screenshot Now",
            command=self.take_and_show,
            bg="#e94560",
            fg="white",
            font=("Arial", 14, "bold"),
            padx=20, pady=10
        ).pack(pady=10)

        # Canvas frame
        self.canvas_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Placeholder canvas
        self.canvas = tk.Canvas(
            self.canvas_frame,
            width=800,
            height=400,
            bg="#0f0f1a",
            cursor="cross"
        )
        self.canvas.pack()

        self.canvas.create_text(
            400, 200,
            text="Click 'Take Screenshot Now' to begin",
            fill="#444",
            font=("Arial", 16)
        )

        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Bottom buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(fill=tk.X, pady=10, padx=10)

        tk.Button(
            btn_frame,
            text="✅ Save Zone",
            command=self.save_zone,
            bg="#00aa55",
            fg="white",
            font=("Arial", 13, "bold"),
            padx=20, pady=8
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="❌ Cancel",
            command=self.root.quit,
            bg="#aa2200",
            fg="white",
            font=("Arial", 13),
            padx=20, pady=8
        ).pack(side=tk.RIGHT, padx=5)

        # Zone info label
        self.zone_label = tk.Label(
            self.root,
            text="No zone selected yet",
            font=("Arial", 11),
            bg="#1a1a2e",
            fg="#888888"
        )
        self.zone_label.pack(pady=5)

    def take_and_show(self):
        """Take screenshot and display it"""
        print("📸 Taking screenshot...")

        try:
            self.screenshot = self.take_screenshot()
        except Exception as e:
            print(f"❌ Screenshot error: {e}")
            # Fallback to mss
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                shot = sct.grab(monitor)
                self.screenshot = Image.frombytes(
                    'RGB', shot.size, shot.bgra, 'raw', 'BGRX'
                )

        self.actual_width, self.actual_height = self.screenshot.size
        print(f"📐 Screenshot size: {self.actual_width} x {self.actual_height}")

        # Scale to fit screen (max 1100px wide)
        max_width = 1100
        if self.actual_width > max_width:
            scale = max_width / self.actual_width
            self.display_width = max_width
            self.display_height = int(self.actual_height * scale)
        else:
            self.display_width = self.actual_width
            self.display_height = self.actual_height

        self.scale_x = self.actual_width / self.display_width
        self.scale_y = self.actual_height / self.display_height

        # Resize for display
        display_img = self.screenshot.resize(
            (self.display_width, self.display_height),
            Image.LANCZOS
        )

        self.tk_image = ImageTk.PhotoImage(display_img)

        # Update canvas size and image
        self.canvas.config(
            width=self.display_width,
            height=self.display_height
        )
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        print("✅ Screenshot displayed. Now draw a box around the pinned comment.")

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)

    def on_drag(self, event):
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            event.x, event.y,
            outline="#e94560",
            width=3
        )

    def on_release(self, event):
        if self.start_x is None or self.screenshot is None:
            return

        end_x = event.x
        end_y = event.y

        # Convert display coords back to actual screen coords
        real_left = int(min(self.start_x, end_x) * self.scale_x)
        real_top = int(min(self.start_y, end_y) * self.scale_y)
        real_width = int(abs(end_x - self.start_x) * self.scale_x)
        real_height = int(abs(end_y - self.start_y) * self.scale_y)

        self.selected_zone = {
            "left": real_left,
            "top": real_top,
            "width": real_width,
            "height": real_height
        }

        self.zone_label.config(
            text=f"✅ Zone: left={real_left}, top={real_top}, "
                 f"width={real_width}, height={real_height}",
            fg="#00ff88"
        )

        print(f"📐 Zone selected: {self.selected_zone}")

    def save_zone(self):
        """Save zone to calibration.json"""
        if not self.selected_zone:
            messagebox.showerror(
                "No Zone",
                "Please draw a rectangle first!"
            )
            return

        if self.selected_zone["width"] < 50 or self.selected_zone["height"] < 10:
            messagebox.showerror(
                "Too Small",
                "Zone is too small. Draw a larger rectangle."
            )
            return

        with open("calibration.json", "w") as f:
            json.dump({"capture_zone": self.selected_zone}, f, indent=2)

        print(f"✅ Saved: {self.selected_zone}")

        messagebox.showinfo(
            "Saved!",
            f"✅ Capture zone saved!\n\n"
            f"Left: {self.selected_zone['left']}\n"
            f"Top: {self.selected_zone['top']}\n"
            f"Width: {self.selected_zone['width']}\n"
            f"Height: {self.selected_zone['height']}\n\n"
            f"Restart the app to apply."
        )
        self.root.quit()

    def run(self):
        self.root.mainloop()


def load_calibration():
    """Load saved calibration zone"""
    if os.path.exists("calibration.json"):
        with open("calibration.json", "r") as f:
            data = json.load(f)
            return data.get("capture_zone")
    return None


def run_calibration():
    print("""
╔══════════════════════════════════════════════╗
║     FAD FASHIOWN - CAPTURE ZONE SETUP        ║
║                                              ║
║  Instructions:                               ║
║  1. Open TikTok Live on your browser         ║
║  2. Make sure a pinned comment is visible    ║
║  3. Click 'Take Screenshot Now' button       ║
║  4. Draw a box around the pinned comment     ║
║  5. Click Save Zone                          ║
╚══════════════════════════════════════════════╝
    """)
    tool = CalibrationTool()
    tool.run()


if __name__ == "__main__":
    run_calibration()