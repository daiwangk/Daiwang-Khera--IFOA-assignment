import fitz  # PyMuPDF

def draw_grid(pdf_path, output_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    # Draw grid lines every 50 pixels
    for x in range(0, int(page.rect.width), 50):
        page.draw_line(fitz.Point(x, 0), fitz.Point(x, page.rect.height), color=(1, 0, 0), width=0.5)
        page.insert_text(fitz.Point(x + 2, 10), str(x), color=(1,0,0), fontsize=8)
        
    for y in range(0, int(page.rect.height), 50):
        page.draw_line(fitz.Point(0, y), fitz.Point(page.rect.width, y), color=(0, 0, 1), width=0.5)
        page.insert_text(fitz.Point(2, y + 10), str(y), color=(0,0,1), fontsize=8)

    doc.save(output_path)
    print(f"Grid saved to {output_path}")

# Run this for your three templates
draw_grid("templates/Dispatch_graduate.pdf", "grid_Dispatch.pdf")
draw_grid("templates/HumanFactors.pdf", "grid_HumanFactors.pdf")
draw_grid("templates/recurrent_training_with_modules.pdf", "grid_Recurrent.pdf")
