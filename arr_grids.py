#!/usr/bin/env python3
"""
Calendar Grid Shifter
Extracts cells from a calendar grid image, shifts them by a specified amount,
and creates a layered PDF with each cell on a separate layer.
"""

import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw
import reportlab
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import letter, A4
import numpy as np


def detect_grid_cells(image, rows=5, cols=7):
    """
    Detect individual cells in a grid layout.
    Returns list of (x, y, width, height) tuples for each cell.
    """
    width, height = image.size
    
    # Convert to numpy array for analysis
    img_array = np.array(image.convert('L'))
    
    # Calculate approximate cell dimensions
    cell_width = width // cols
    cell_height = height // rows
    
    cells = []
    for row in range(rows):
        for col in range(cols):
            x = col * cell_width
            y = row * cell_height
            cells.append((x, y, cell_width, cell_height))
    
    return cells


def extract_cells(image, rows=5, cols=7, margin_bottom=0, margin_sides=0):
    """
    Extract individual cells from the grid image.
    Returns list of PIL Images, one per cell.
    Uses precise positioning to avoid gaps and misalignment.
    """
    width, height = image.size
    
    # Account for margins
    usable_width = width - (2 * margin_sides)
    usable_height = height - margin_bottom
    
    cells = []
    for row in range(rows):
        for col in range(cols):
            # Calculate precise boundaries for this cell
            # Use fractional positioning then round to pixels
            x1 = margin_sides + int((col * usable_width) / cols)
            x2 = margin_sides + int(((col + 1) * usable_width) / cols)
            y1 = int((row * usable_height) / rows)
            y2 = int(((row + 1) * usable_height) / rows)
            
            # Extract cell
            cell_box = (x1, y1, x2, y2)
            cell = image.crop(cell_box)
            cells.append(cell)
    
    # Return average cell dimensions for reporting
    avg_width = usable_width / cols
    avg_height = usable_height / rows
    
    return cells, avg_width, avg_height


def shift_cells(cells, shift, cols=7):
    """
    Shift cells by the specified amount, wrapping around.
    Positive shift moves cells to the right/down.
    Negative shift moves cells to the left/up.
    """
    total_cells = len(cells)
    shifted = [None] * total_cells
    
    for i, cell in enumerate(cells):
        new_index = (i + shift) % total_cells
        shifted[new_index] = cell
    
    return shifted


def create_layered_pdf(cells, output_path, rows=5, cols=7, 
                      margin_bottom=50, margin_sides=20, page_size='letter',
                      original_width=None, original_height=None):
    """
    Create a PDF with each cell on a separate layer.
    """
    # Use original image dimensions if provided, otherwise use standard page size
    if original_width and original_height:
        page_width = original_width
        page_height = original_height
        pagesize = (page_width, page_height)
    else:
        # Set page size
        if page_size.lower() == 'a4':
            pagesize = A4
        else:
            pagesize = letter
        
        page_width, page_height = pagesize
    
    # Calculate cell dimensions to fit the page
    usable_width = page_width - (2 * margin_sides)
    usable_height = page_height - margin_bottom
    
    cell_width = usable_width / cols
    cell_height = usable_height / rows
    
    # Create PDF
    c = canvas.Canvas(str(output_path), pagesize=pagesize)
    
    # Add each cell as a separate layer
    for idx, cell in enumerate(cells):
        if cell is None:
            continue
            
        row = idx // cols
        col = idx % cols
        
        x = margin_sides + (col * cell_width)
        y = page_height - margin_bottom - ((row + 1) * cell_height)
        
        # Create layer name
        layer_name = f"Cell_{row + 1}_{col + 1}"
        
        # Save cell to temporary buffer
        from io import BytesIO
        buffer = BytesIO()
        cell.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Begin new layer
        c.saveState()
        c.setFont("Helvetica", 6)
        
        # Draw the cell image
        img_reader = ImageReader(buffer)
        c.drawImage(img_reader, x, y, width=cell_width, height=cell_height, 
                   mask='auto', preserveAspectRatio=True)
        
        c.restoreState()
    
    c.save()
    print(f"PDF created: {output_path}")


def create_simple_pdf(cells, output_path, rows=5, cols=7,
                     margin_bottom=50, margin_sides=20, page_size='letter'):
    """
    Create a simple PDF with all cells on one page (fallback method).
    """
    if page_size.lower() == 'a4':
        pagesize = A4
    else:
        pagesize = letter
    
    page_width, page_height = pagesize
    
    # Calculate cell dimensions
    usable_width = page_width - (2 * margin_sides)
    usable_height = page_height - margin_bottom
    
    cell_width = usable_width / cols
    cell_height = usable_height / rows
    
    c = canvas.Canvas(str(output_path), pagesize=pagesize)
    
    for idx, cell in enumerate(cells):
        if cell is None:
            continue
            
        row = idx // cols
        col = idx % cols
        
        x = margin_sides + (col * cell_width)
        y = page_height - margin_bottom - ((row + 1) * cell_height)
        
        from io import BytesIO
        buffer = BytesIO()
        cell.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_reader = ImageReader(buffer)
        c.drawImage(img_reader, x, y, width=cell_width, height=cell_height,
                   mask='auto', preserveAspectRatio=True)
    
    c.save()
    print(f"PDF created: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract and shift calendar grid cells, output to layered PDF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Shift cells forward by 3 positions
  %(prog)s input.png -s 3 -o output.pdf
  
  # Shift backward by 2, with custom grid size
  %(prog)s input.png -s -2 --rows 5 --cols 7 -o shifted.pdf
  
  # Custom margins
  %(prog)s input.png -s 5 --margin-sides 30 --margin-bottom 60 -o out.pdf
        """
    )
    
    parser.add_argument('input', type=str, help='Input calendar image file')
    parser.add_argument('-s', '--shift', type=int, required=True,
                       help='Number of cells to shift (positive=forward, negative=backward)')
    parser.add_argument('-o', '--output', type=str, default='shifted_calendar.pdf',
                       help='Output PDF file (default: shifted_calendar.pdf)')
    parser.add_argument('--rows', type=int, default=5,
                       help='Number of rows in grid (default: 5)')
    parser.add_argument('--cols', type=int, default=7,
                       help='Number of columns in grid (default: 7)')
    parser.add_argument('--margin-sides', type=int, default=20,
                       help='Side margins in pixels to preserve (default: 20)')
    parser.add_argument('--margin-bottom', type=int, default=50,
                       help='Bottom margin in pixels to preserve (default: 50)')
    parser.add_argument('--page-size', type=str, default='letter',
                       choices=['letter', 'a4'],
                       help='PDF page size (default: letter)')
    parser.add_argument('--use-standard-page', action='store_true',
                       help='Use standard page size instead of original image dimensions')
    parser.add_argument('--preview', action='store_true',
                       help='Save preview PNG instead of PDF')
    
    args = parser.parse_args()
    
    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    # Load image
    print(f"Loading image: {input_path}")
    image = Image.open(input_path)
    original_width, original_height = image.size
    print(f"Original dimensions: {original_width}x{original_height}px")
    
    # Extract cells
    print(f"Extracting {args.rows}x{args.cols} grid...")
    cells, cell_w, cell_h = extract_cells(
        image, 
        rows=args.rows, 
        cols=args.cols,
        margin_bottom=args.margin_bottom,
        margin_sides=args.margin_sides
    )
    print(f"Extracted {len(cells)} cells (each {cell_w}x{cell_h}px)")
    
    # Shift cells
    print(f"Shifting cells by {args.shift} positions...")
    shifted_cells = shift_cells(cells, args.shift, cols=args.cols)
    
    # Create output
    output_path = Path(args.output)
    
    if args.preview:
        # Create preview image
        preview_path = output_path.with_suffix('.png')
        create_preview_image(shifted_cells, preview_path, args.rows, args.cols,
                           args.margin_bottom, args.margin_sides)
    else:
        # Create PDF
        # Use original dimensions unless --use-standard-page is specified
        use_original_dims = not args.use_standard_page
        create_layered_pdf(
            shifted_cells,
            output_path,
            rows=args.rows,
            cols=args.cols,
            margin_bottom=args.margin_bottom,
            margin_sides=args.margin_sides,
            page_size=args.page_size,
            original_width=original_width if use_original_dims else None,
            original_height=original_height if use_original_dims else None
        )
    
    print("Done!")


def create_preview_image(cells, output_path, rows=5, cols=7, 
                        margin_bottom=50, margin_sides=20):
    """
    Create a preview PNG showing the rearranged grid.
    """
    if not cells or cells[0] is None:
        print("Error: No cells to preview", file=sys.stderr)
        return
    
    # Get cell dimensions from first cell
    cell_width, cell_height = cells[0].size
    
    # Create output image
    total_width = (cols * cell_width) + (2 * margin_sides)
    total_height = (rows * cell_height) + margin_bottom
    
    output = Image.new('RGB', (total_width, total_height), 'white')
    
    # Paste cells
    for idx, cell in enumerate(cells):
        if cell is None:
            continue
            
        row = idx // cols
        col = idx % cols
        
        x = margin_sides + (col * cell_width)
        y = (row * cell_height)
        
        output.paste(cell, (x, y))
    
    output.save(output_path)
    print(f"Preview image created: {output_path}")


if __name__ == '__main__':
    main()