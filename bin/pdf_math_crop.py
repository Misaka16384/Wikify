import os
import sys
import argparse

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF is not installed. Run 'pip install pymupdf' to use this script.")
    sys.exit(1)

def extract_crop(pdf_path, search_text, output_path, expand_margin=150, page_num=None):
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return False
        
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return False
    
    target_rect = None
    target_page = None
    
    if page_num is not None:
        try:
            target_page = doc[int(page_num)]
        except Exception as e:
            print(f"Error accessing page {page_num}: {e}")
            return False
            
        if search_text:
            text_instances = target_page.search_for(search_text)
            if text_instances:
                target_rect = text_instances[0]
            else:
                print(f"Text '{search_text}' not found on page {page_num}.")
                return False
        else:
            # No search text: render the whole page. This is the fallback for
            # scanned/OCR PDFs that have no selectable text layer to search.
            target_rect = target_page.rect
    else:
        if not search_text:
            print("Error: provide --text to search for, or --page to render a full page "
                  "(scanned PDFs often have no text layer to search).")
            return False
        # Search all pages
        for i in range(len(doc)):
            page = doc[i]
            text_instances = page.search_for(search_text)
            if text_instances:
                target_page = page
                target_rect = text_instances[0]
                print(f"Found '{search_text}' on page {i} (1-indexed: {i+1})")
                break
                
    if not target_page or not target_rect:
        print(f"Text '{search_text}' not found in the document.")
        return False
        
    # Expand the bounding box
    rect = target_rect
    
    # Allow expanding the bounding box to capture surrounding math/diagram
    rect.x0 = max(0, rect.x0 - expand_margin)
    rect.y0 = max(0, rect.y0 - expand_margin)
    rect.x1 = min(target_page.rect.width, rect.x1 + expand_margin)
    rect.y1 = min(target_page.rect.height, rect.y1 + expand_margin)
    
    # Render to image
    # Increase resolution with a matrix
    zoom = 3.0  # ~216 DPI (default is 72, 3x = 216)
    mat = fitz.Matrix(zoom, zoom)
    
    try:
        # Ensure the output directory exists (e.g. <TOPIC_DIR>/scratch/), since
        # pix.save() will not create missing parent directories.
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        pix = target_page.get_pixmap(matrix=mat, clip=rect)
        pix.save(output_path)
        print(f"Successfully saved crop to {output_path}")
        return True
    except Exception as e:
        print(f"Error rendering crop: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crop a region of a PDF containing specific text. Useful for multimodal LLM agents to view complex math/diagrams.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--text", default=None, help="Text to search for. Omit to render the whole --page (useful for scanned PDFs with no text layer).")
    parser.add_argument("--out", default="crop.png", help="Output PNG path")
    parser.add_argument("--margin", type=int, default=150, help="Margin to expand around the text (pts, default: 150)")
    parser.add_argument("--page", type=int, default=None, help="0-indexed page number to search within")
    
    args = parser.parse_args()
    
    extract_crop(args.pdf_path, args.text, args.out, args.margin, args.page)
