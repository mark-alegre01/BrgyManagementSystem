import fitz  # PyMuPDF
import pytesseract
import re
from PIL import Image
import io
from datetime import datetime

def clean_ocr_text(text):
    # Fix doubled characters (e.g. DDeevveelloopp → Develop)
    text = re.sub(r'(.)\1+', r'\1', text)
    # Remove random symbols and garbage characters
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\"\'\n]', ' ', text)
    # Fix multiple spaces
    text = re.sub(r' +', ' ', text)
    # Fix multiple newlines
    text = re.sub(r'\n+', '\n', text)
    # Strip each line
    text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    return text

def extract_ordinance_fields(text):
    fields = {
        'ordinance_number': '',
        'title': '',
        'date_enacted': '',
        'body_content': '',
        'signatories': '',
        'author': '',
        'category': ''
    }

    # Extract Ordinance Number
    num_match = re.search(
        r'ordinance\s+no[\.\:]?\s*([\w\-]+)', text, re.IGNORECASE
    )
    fields['ordinance_number'] = num_match.group(1).strip() if num_match else ''

    # Extract Title
    title_match = re.search(
        r'(an ordinance[^\.]+\.)', text, re.IGNORECASE
    )
    fields['title'] = title_match.group(1).strip() if title_match else ''

    # Extract Date
    date_match = re.search(
        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})', text, re.IGNORECASE
    )
    if date_match:
        try:
            date_str = date_match.group(1).replace(',', '').strip()
            # The clean_ocr_text might have lowercased or altered case slightly, but strptime %B is case-insensitive in Python 3
            dt_obj = datetime.strptime(date_str, '%B %d %Y')
            fields['date_enacted'] = dt_obj.strftime('%Y-%m-%d')
        except Exception:
            # Fallback to the raw string if parsing fails
            fields['date_enacted'] = date_match.group(1)

    # Extract Signatories
    sig_match = re.search(
        r'(attested.*?(?:secretary|head)[^\n]*)', text, re.IGNORECASE
    )
    fields['signatories'] = sig_match.group(1).strip() if sig_match else ''

    # Extract Author/Sponsor (from original functionality)
    author_match = re.search(r'(?:SPONSORED BY|AUTHORED BY|INTRODUCED BY|AUTHOR)\s*:\s*([^\n]+)', text, re.IGNORECASE)
    if author_match:
        author_text = author_match.group(1).strip()
        fields['author'] = author_text[:200]

    # Extract Category by Keywords (from original functionality)
    text_lower = text.lower()
    if any(kw in text_lower for kw in ['budget', 'fund', 'revenue', 'tax', 'appropriation']):
        fields['category'] = 'revenue'
    elif any(kw in text_lower for kw in ['peace', 'order', 'curfew', 'penalty', 'prohibiting', 'tricycle', 'traffic']):
        fields['category'] = 'peace_order'
    elif any(kw in text_lower for kw in ['health', 'sanitation', 'medical', 'hospital']):
        fields['category'] = 'health'
    elif any(kw in text_lower for kw in ['environment', 'waste', 'garbage', 'tree']):
        fields['category'] = 'environment'
    elif any(kw in text_lower for kw in ['infrastructure', 'road', 'building', 'construction']):
        fields['category'] = 'infrastructure'
    elif any(kw in text_lower for kw in ['welfare', 'senior', 'pwd', 'youth']):
        fields['category'] = 'social_welfare'
    elif any(kw in text_lower for kw in ['school', 'education', 'scholarship']):
        fields['category'] = 'education'

    # Full content is the entire cleaned text
    fields['body_content'] = text

    return fields

def parse_ordinance_pdf(pdf_path):
    """
    Parses a PDF file containing a barangay ordinance and extracts data using PyMuPDF and OCR.
    """
    try:
        # Set tesseract path for Windows
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    except Exception:
        pass
        
    try:
        doc = fitz.open(pdf_path)
        full_text = ""

        for page_num in range(len(doc)):
            page = doc[page_num]

            # First try native text extraction
            text = page.get_text()

            # If text is too short or garbled, use OCR
            if len(text.strip()) < 50 or 'DDeevveelloopp' in text or '^^' in text:
                # Render page as image
                mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR accuracy
                clip = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(clip.tobytes()))

                # Run Tesseract OCR
                text = pytesseract.image_to_string(img, lang='eng')

            full_text += text + "\n"

        # Clean the extracted text
        cleaned_text = clean_ocr_text(full_text)
        
        # Extract fields
        return extract_ordinance_fields(cleaned_text)
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        # Return empty dictionary structure on failure
        return {
            'ordinance_number': '',
            'title': '',
            'date_enacted': '',
            'body_content': '',
            'signatories': '',
            'author': '',
            'category': ''
        }
