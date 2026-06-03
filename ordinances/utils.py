import fitz  # PyMuPDF
import pytesseract
import re
from PIL import Image
import io
from datetime import datetime

def clean_ocr_text(text):
    # Remove random symbols and garbage characters, but keep basic punctuation and slashes
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\"\'\/\n]', ' ', text)
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
    title_match = re.search(r'([\"\']\s*an ordinance.*?[\"\'])', text, re.IGNORECASE | re.DOTALL)
    if not title_match:
        title_match = re.search(r'(an ordinance.*?)(?:\n\s*\n|be it ordained|sponsored by|authored by)', text, re.IGNORECASE | re.DOTALL)
    
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'\n+', ' ', title)
        fields['title'] = re.sub(r'\s+', ' ', title)
    else:
        fields['title'] = ''

    # Extract Date
    months = r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    raw_date = None
    
    m1 = re.search(fr'({months}\s+\d{{1,2}}(?:st|nd|rd|th)?[\s\,]+\d{{4}})', text, re.IGNORECASE)
    m2 = re.search(fr'(\d{{1,2}}(?:st|nd|rd|th)?[\s\,]+{months}[\s\,]+\d{{4}})', text, re.IGNORECASE)
    m3 = re.search(fr'(\d{{1,2}}(?:st|nd|rd|th)?\s+day\s+of\s+{months}[\s\,]+\d{{4}})', text, re.IGNORECASE)
    m4 = re.search(r'(\d{4}[\-\/]\d{1,2}[\-\/]\d{1,2})', text)
    m5 = re.search(r'(\d{1,2}[\-\/]\d{1,2}[\-\/]\d{4})', text)

    if m1:
        raw_date = m1.group(1)
    elif m2:
        raw_date = m2.group(1)
    elif m3:
        raw_date = re.sub(r'day of', '', m3.group(1), flags=re.IGNORECASE).strip()
    elif m4:
        raw_date = m4.group(1)
    elif m5:
        raw_date = m5.group(1)

    if raw_date:
        cleaned_date = re.sub(r'(st|nd|rd|th)', '', raw_date, flags=re.IGNORECASE)
        cleaned_date = re.sub(r'[\s\,]+', ' ', cleaned_date).strip()
        formats = [
            '%B %d %Y', '%b %d %Y', 
            '%d %B %Y', '%d %b %Y',
            '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'
        ]
        parsed = False
        for fmt in formats:
            try:
                fields['date_enacted'] = datetime.strptime(cleaned_date, fmt).strftime('%Y-%m-%d')
                parsed = True
                break
            except ValueError:
                continue
        if not parsed:
            fields['date_enacted'] = raw_date
    else:
        fields['date_enacted'] = ''

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

                # Run Tesseract OCR with a fallback
                try:
                    text = pytesseract.image_to_string(img, lang='eng')
                except Exception as ocr_e:
                    print(f"OCR failed for page {page_num}: {ocr_e}")
                    # Keep whatever little text PyMuPDF found
                    pass

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
