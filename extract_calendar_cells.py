import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from PIL import Image, ImageTk
import sys
import os
import argparse
from pathlib import Path

class DraggableLine:
    def __init__(self, canvas, orientation, pos, length, tag):
        self.canvas = canvas
        self.orientation = orientation # 'h' or 'v'
        self.pos = pos
        self.id = None
        self.tag = tag
        self.draw(length)
        
    def draw(self, length):
        if self.orientation == 'v':
            self.id = self.canvas.create_line(self.pos, 0, self.pos, length, fill='red', width=2, tags=(self.tag, 'line', 'v'))
        else:
            self.id = self.canvas.create_line(0, self.pos, length, self.pos, fill='red', width=2, tags=(self.tag, 'line', 'h'))

    def move_to(self, new_pos):
        self.pos = new_pos
        if self.orientation == 'v':
            self.canvas.coords(self.id, self.pos, 0, self.pos, self.canvas.winfo_height())
        else:
            self.canvas.coords(self.id, 0, self.pos, self.canvas.winfo_width(), self.pos)

class CalendarExtractor:
    def __init__(self, root, image_path, output_dir=None):
        self.root = root
        self.root.title("Calendar Grid Adjuster")
        
        self.image_path = Path(image_path)
        try:
            self.original_image = Image.open(self.image_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open image: {e}")
            sys.exit(1)

        # Output directory setup
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.image_path.parent / self.image_path.stem
        
        # UI State
        self.rows = 5
        self.cols = 7
        self.v_lines = []
        self.h_lines = []
        self.selected_line = None
        self.start_cell_index = 0 # 0-based index of the '1st' of the month
        
        # Resizing image for display if too large
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        self.display_scale = 1.0
        display_w, display_h = self.original_image.size
        
        # Limit to 80% of screen size
        max_w = screen_width * 0.8
        max_h = screen_height * 0.8
        
        if display_w > max_w or display_h > max_h:
            scale_w = max_w / display_w
            scale_h = max_h / display_h
            self.display_scale = min(scale_w, scale_h)
            display_w = int(display_w * self.display_scale)
            display_h = int(display_h * self.display_scale)
        
        self.display_image = self.original_image.resize((display_w, display_h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(self.display_image)
        
        # Control Frame (Top)
        control_frame = tk.Frame(root)
        control_frame.pack(fill="x", pady=5)
        
        tk.Label(control_frame, text="Rows:").pack(side="left", padx=5)
        self.row_var = tk.IntVar(value=self.rows)
        tk.Entry(control_frame, textvariable=self.row_var, width=3).pack(side="left")
        
        tk.Button(control_frame, text="Reset Grid", command=self.reset_grid).pack(side="left", padx=5)
        
        tk.Label(control_frame, text="Padding (px):").pack(side="left", padx=10)
        self.padding_var = tk.IntVar(value=0)
        tk.Scale(control_frame, from_=0, to=50, orient="horizontal", variable=self.padding_var).pack(side="left")
        
        tk.Button(control_frame, text="Save & Extract", command=self.save, bg="green", fg="white").pack(side="right", padx=10)

        # Canvas
        self.canvas = tk.Canvas(root, width=display_w, height=display_h, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        
        # Initial Grid Calculation
        self.init_grid_lines(display_w, display_h)
        
        # Event Bindings
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click) # Right click (Windows/Linux/Mac usually)
        self.canvas.bind("<Button-2>", self.on_right_click) # Right click (Mac sometimes)
        self.canvas.bind("<Control-Button-1>", self.on_right_click) # Ctrl+Click (Mac)
        
        # Instructions
        instruction_label = tk.Label(root, text="Left Click+Drag: Adjust Grid Lines | Right Click (or Ctrl+Click): Set First Day of Month", bg="#eee")
        instruction_label.pack(side="bottom", fill="x")
        
        self.redraw_overlays()

    def init_grid_lines(self, w, h):
        self.canvas.delete('line')
        self.v_lines = []
        self.h_lines = []
        
        # Vertical lines (cols + 1)
        step_x = w / self.cols
        for i in range(self.cols + 1):
            pos = int(i * step_x)
            line = DraggableLine(self.canvas, 'v', pos, h, f"v_{i}")
            self.v_lines.append(line)
            
        # Horizontal lines (rows + 1)
        step_y = h / self.rows
        for i in range(self.rows + 1):
            pos = int(i * step_y)
            line = DraggableLine(self.canvas, 'h', pos, w, f"h_{i}")
            self.h_lines.append(line)

    def reset_grid(self):
        try:
            self.rows = self.row_var.get()
        except ValueError:
            return
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        self.init_grid_lines(w, h)
        self.start_cell_index = 0
        self.redraw_overlays()

    def get_sorted_lines(self):
        v_sorted = sorted(self.v_lines, key=lambda l: l.pos)
        h_sorted = sorted(self.h_lines, key=lambda l: l.pos)
        return v_sorted, h_sorted

    def on_click(self, event):
        # Check for line selection with threshold
        threshold = 10
        closest_dist = threshold
        self.selected_line = None
        
        # Check vertical lines
        for line in self.v_lines:
            dist = abs(event.x - line.pos)
            if dist < closest_dist:
                closest_dist = dist
                self.selected_line = line
        
        # Check horizontal lines (prioritize if closer)
        for line in self.h_lines:
            dist = abs(event.y - line.pos)
            if dist < closest_dist:
                closest_dist = dist
                self.selected_line = line
                
    def on_drag(self, event):
        if self.selected_line:
            # Constrain to canvas dimensions
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            
            if self.selected_line.orientation == 'v':
                new_x = max(0, min(event.x, w))
                self.selected_line.move_to(new_x)
            else:
                new_y = max(0, min(event.y, h))
                self.selected_line.move_to(new_y)
            
            self.redraw_overlays()

    def on_release(self, event):
        self.selected_line = None

    def on_right_click(self, event):
        v_sorted, h_sorted = self.get_sorted_lines()
        
        col = -1
        row = -1
        
        # Find col
        for i in range(len(v_sorted) - 1):
            if v_sorted[i].pos <= event.x < v_sorted[i+1].pos:
                col = i
                break
        
        # Find row
        for i in range(len(h_sorted) - 1):
            if h_sorted[i].pos <= event.y < h_sorted[i+1].pos:
                row = i
                break
                
        if col != -1 and row != -1:
            self.start_cell_index = row * self.cols + col
            self.redraw_overlays()
            
    def redraw_overlays(self):
        self.canvas.delete("overlay")
        v_sorted, h_sorted = self.get_sorted_lines()
        
        total_cells = self.rows * self.cols
        
        for r in range(self.rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                
                # Wrap-around numbering:
                # 1. Shift index so start_cell is 0
                # 2. Modulo total cells
                # 3. Add 1 to make it 1-based
                num = (idx - self.start_cell_index) % total_cells + 1
                
                # Ensure indices exist (in case user reduced rows but logic still iterating)
                if r+1 < len(h_sorted) and c+1 < len(v_sorted):
                    x1 = v_sorted[c].pos
                    x2 = v_sorted[c+1].pos
                    y1 = h_sorted[r].pos
                    y2 = h_sorted[r+1].pos
                    
                    # Only draw if adequate size
                    if (x2-x1) > 20 and (y2-y1) > 20:
                        center_x = (x1+x2)/2
                        center_y = (y1+y2)/2
                        
                        if num == 1:
                            # Highlight Start Cell
                            self.canvas.create_rectangle(x1+2, y1+2, x2-2, y2-2, outline="blue", width=3, tags="overlay")
                            self.canvas.create_text(center_x, center_y, text="1", font=("Arial", 16, "bold"), fill="blue", tags="overlay")
                        else:
                            # Normal numbering
                            self.canvas.create_text(center_x, center_y, text=str(num), font=("Arial", 10), fill="gray", tags="overlay")

    def save(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        else:
            # Check if directory is empty, warn if not?
            # For now, just overwrite
            pass
            
        padding = self.padding_var.get()
        scale = 1.0 / self.display_scale
        
        v_sorted, h_sorted = self.get_sorted_lines()
        
        total_cells = self.rows * self.cols
        saved_count = 0
        
        print(f"Extracting cells to {self.output_dir}...")
        
        for r in range(self.rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                
                if r+1 >= len(h_sorted) or c+1 >= len(v_sorted):
                    continue

                # Calculate Number
                num = (idx - self.start_cell_index) % total_cells + 1

                # Get coordinates in display space
                x1_d = v_sorted[c].pos
                x2_d = v_sorted[c+1].pos
                y1_d = h_sorted[r].pos
                y2_d = h_sorted[r+1].pos
                
                # Transform to original image space
                x1 = int(x1_d * scale) + padding
                x2 = int(x2_d * scale) - padding
                y1 = int(y1_d * scale) + padding
                y2 = int(y2_d * scale) - padding
                
                if x2 <= x1 or y2 <= y1:
                    print(f"Skipping cell {num} (dimensions too small after padding)")
                    continue
                
                try:
                    cell_img = self.original_image.crop((x1, y1, x2, y2))
                    filename = f"{num}.png"
                    save_path = self.output_dir / filename
                    cell_img.save(save_path)
                    saved_count += 1
                except Exception as e:
                    print(f"Error saving cell {num}: {e}")
                
        messagebox.showinfo("Success", f"Extracted {saved_count} cells to\n{self.output_dir}")
        self.root.destroy()

def main():
    parser = argparse.ArgumentParser(description="Interactive Calendar Cell Extractor")
    parser.add_argument("image_path", help="Path to the calendar image (PNG)")
    parser.add_argument("--output", "-o", help="Output directory (default: ./<image_name>/)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        print(f"File not found: {args.image_path}")
        return

    root = tk.Tk()
    app = CalendarExtractor(root, args.image_path, args.output)
    
    # Center window
    root.update_idletasks()
    
    # Bring to front (especially for macOS)
    if sys.platform == 'darwin':
        try:
             os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')
        except:
             pass

    root.mainloop()

if __name__ == "__main__":
    main()