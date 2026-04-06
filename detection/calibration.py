# detection/calibration.py
# Tool to help seller select the exact screen region
# where TikTok shows the pinned comment
# Run this ONCE to set up the capture zone

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from detection.capture import capture_full_screen, get_screen_size


class CalibrationTool:
    """
    A simple GUI tool that lets the seller draw a rectangle
    over the pinned comment area on their screen.
    """
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Fad Fashiown - Capture Zone Calibration")
        
        # Screenshot of full screen
        self.screenshot = None
        self.tk_image = None
        
        # Rectangle drawing state
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.selected_zone = None
        
        # Scale factor (screenshot may be scaled to fit screen)
        self.scale_x = 1.0
        self.scale_y = 1.0
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the calibration window"""
        screen_info = get_screen_size()
        
        # Instructions label
        instructions = tk.Label(
            self.root,
            text="📌 Draw a rectangle around the PINNED COMMENT area on TikTok\n"
                 "Click and drag to select. Release to confirm.",
            font=("Arial", 13),
            bg="#1a1a2e",
            fg="white",
            pady=10
        )
        instructions.pack(fill=tk.X)
        
        # Take screenshot
        print("📸 Taking screenshot of your screen...")
        self.screenshot = capture_full_screen()
        
        # Scale screenshot to fit window (max 1200px wide)
        max_width = 1200
        orig_width, orig_height = self.screenshot.size
        
        if orig_width > max_width:
            self.scale_x = max_width / orig_width
            self.scale_y = self.scale_x
            new_height = int(orig_height * self.scale_y)
            display_img = self.screenshot.resize(
                (max_width, new_height),
                Image.LANCZOS
            )
        else:
            display_img = self.screenshot
            
        self.tk_image = ImageTk.PhotoImage(display_img)
        
        # Canvas to display screenshot
        self.canvas = tk.Canvas(
            self.root,
            width=display_img.width,
            height=display_img.height,
            cursor="cross"
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        
        # Bind mouse events for drawing rectangle
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        
        # Bottom buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(
            btn_frame,
            text="✅ Save Zone",
            command=self.save_zone,
            bg="#00aa55",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=20, pady=8
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            btn_frame,
            text="🔄 Retake Screenshot",
            command=self.retake,
            bg="#333366",
            fg="white",
            font=("Arial", 12),
            padx=20, pady=8
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            btn_frame,
            text="❌ Cancel",
            command=self.root.quit,
            bg="#aa2200",
            fg="white",
            font=("Arial", 12),
            padx=20, pady=8
        ).pack(side=tk.RIGHT, padx=10)
        
        # Zone info label
        self.zone_label = tk.Label(
            self.root,
            text="No zone selected yet",
            font=("Arial", 11),
            bg="#1a1a2e",
            fg="#888888"
        )
        self.zone_label.pack(pady=5)
    
    def on_mouse_press(self, event):
        """Start drawing rectangle"""
        self.start_x = event.x
        self.start_y = event.y
        
        # Remove old rectangle if any
        if self.rect:
            self.canvas.delete(self.rect)
    
    def on_mouse_drag(self, event):
        """Update rectangle while dragging"""
        if self.rect:
            self.canvas.delete(self.rect)
        
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            event.x, event.y,
            outline="#e94560",
            width=3
        )
    
    def on_mouse_release(self, event):
        """Finalize rectangle selection"""
        if self.start_x is None:
            return
        
        end_x = event.x
        end_y = event.y
        
        # Convert canvas coordinates back to real screen coordinates
        real_left = int(min(self.start_x, end_x) / self.scale_x)
        real_top = int(min(self.start_y, end_y) / self.scale_y)
        real_width = int(abs(end_x - self.start_x) / self.scale_x)
        real_height = int(abs(end_y - self.start_y) / self.scale_y)
        
        self.selected_zone = {
            "left": real_left,
            "top": real_top,
            "width": real_width,
            "height": real_height
        }
        
        self.zone_label.config(
            text=f"Selected zone: left={real_left}, top={real_top}, "
                 f"width={real_width}, height={real_height}",
            fg="#00ff88"
        )
        
        print(f"📐 Zone selected: {self.selected_zone}")
    
    def save_zone(self):
        """Save the selected zone to config file"""
        if not self.selected_zone:
            messagebox.showerror(
                "No Zone Selected",
                "Please draw a rectangle over the pinned comment area first!"
            )
            return
        
        if self.selected_zone["width"] < 50 or self.selected_zone["height"] < 20:
            messagebox.showerror(
                "Zone Too Small",
                "The selected area is too small. Please draw a larger rectangle."
            )
            return
        
        # Save to a JSON file that app.py will read
        zone_data = {
            "capture_zone": self.selected_zone
        }
        
        with open("calibration.json", "w") as f:
            json.dump(zone_data, f, indent=2)
        
        print(f"✅ Zone saved to calibration.json: {self.selected_zone}")
        
        messagebox.showinfo(
            "Zone Saved!",
            f"✅ Capture zone saved!\n\n"
            f"Left: {self.selected_zone['left']}\n"
            f"Top: {self.selected_zone['top']}\n"
            f"Width: {self.selected_zone['width']}\n"
            f"Height: {self.selected_zone['height']}\n\n"
            f"Restart the system to apply."
        )
        
        self.root.quit()
    
    def retake(self):
        """Retake the screenshot"""
        self.screenshot = capture_full_screen()
        self.tk_image = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
    
    def run(self):
        """Start the calibration tool"""
        self.root.configure(bg="#1a1a2e")
        self.root.mainloop()


def load_calibration():
    """
    Load saved calibration zone from file.
    Returns None if no calibration has been done.
    """
    if os.path.exists("calibration.json"):
        with open("calibration.json", "r") as f:
            data = json.load(f)
            return data.get("capture_zone")
    return None


def run_calibration():
    """Entry point to run the calibration tool"""
    print("""
╔══════════════════════════════════════════════╗
║     FAD FASHIOWN - CAPTURE ZONE SETUP        ║
║                                              ║
║  Instructions:                               ║
║  1. Open TikTok Live on your browser         ║
║  2. Make sure a pinned comment is visible    ║
║  3. Draw a box around the pinned comment     ║
║  4. Click Save Zone                          ║
╚══════════════════════════════════════════════╝
    """)
    
    tool = CalibrationTool()
    tool.run()


if __name__ == "__main__":
    run_calibration()