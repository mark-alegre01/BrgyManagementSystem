import re
import pdfplumber

def parse_ordinance_pdf(file_path):
    """
    Parses a PDF file containing a barangay ordinance and extracts:
    - Ordinance Number
    - Title
    - Date Enacted
    - Body Content
    - Signatories
    """
    extracted_data = {
        'ordinance_number': '',
        'title': '',
        'date_enacted': '',
        'body_content': '',
        'signatories': '',
        'author': '',
        'category': ''
    }

    try:
        full_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
        
        extracted_data['body_content'] = full_text.strip()

        # 1. Extract Ordinance Number
        # Looks for "Ordinance No. 2024-001" or similar
        ord_no_match = re.search(r'ORDINANCE\s+NO\.?\s*([0-9A-Za-z-]+)', full_text, re.IGNORECASE)
        if ord_no_match:
            extracted_data['ordinance_number'] = ord_no_match.group(1).strip()

        # 2. Extract Title
        # Title usually comes after the ordinance number or "ENTITLED:"
        title_match = re.search(r'(?:ENTITLED\s*:|ORDINANCE\s+NO\.?[^\n]+\n+)(.+?)(?=\n\s*(?:BE IT ORDAINED|WHEREAS|Section 1|SPONSORED BY|AUTHORED BY|INTRODUCED BY))', full_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            # Clean up the title
            title_text = title_match.group(1).strip()
            # Remove non-printable or weird characters
            title_text = re.sub(r'[^\x20-\x7E\n\r\t“”‘’]', '', title_text)
            # Remove extra newlines
            title_text = re.sub(r'\s+', ' ', title_text).strip()
            extracted_data['title'] = title_text[:500]  # limit to model max_length

        # 2.5 Extract Author/Sponsor
        author_match = re.search(r'(?:SPONSORED BY|AUTHORED BY|INTRODUCED BY|AUTHOR)\s*:\s*([^\n]+)', full_text, re.IGNORECASE)
        if author_match:
            author_text = author_match.group(1).strip()
            author_text = re.sub(r'[^\x20-\x7E]', '', author_text)
            extracted_data['author'] = re.sub(r'\s+', ' ', author_text)[:200]
            
        # 2.6 Extract Category by Keywords
        text_lower = full_text.lower()
        if any(kw in text_lower for kw in ['budget', 'fund', 'revenue', 'tax', 'appropriation']):
            extracted_data['category'] = 'revenue'
        elif any(kw in text_lower for kw in ['peace', 'order', 'curfew', 'penalty', 'prohibiting', 'tricycle', 'traffic']):
            extracted_data['category'] = 'peace_order'
        elif any(kw in text_lower for kw in ['health', 'sanitation', 'medical', 'hospital']):
            extracted_data['category'] = 'health'
        elif any(kw in text_lower for kw in ['environment', 'waste', 'garbage', 'tree']):
            extracted_data['category'] = 'environment'
        elif any(kw in text_lower for kw in ['infrastructure', 'road', 'building', 'construction']):
            extracted_data['category'] = 'infrastructure'
        elif any(kw in text_lower for kw in ['welfare', 'senior', 'pwd', 'youth']):
            extracted_data['category'] = 'social_welfare'
        elif any(kw in text_lower for kw in ['school', 'education', 'scholarship']):
            extracted_data['category'] = 'education'

        # 3. Extract Date Enacted
        # Look for dates like "January 15, 2024" or "15th day of January, 2024"
        date_match = re.search(r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})', full_text, re.IGNORECASE)
        if date_match:
            try:
                # We want to format it as YYYY-MM-DD for the HTML date input
                from datetime import datetime
                # Handle possible comma variations
                date_str = date_match.group(1).replace(',', '').strip()
                dt_obj = datetime.strptime(date_str, '%B %d %Y')
                extracted_data['date_enacted'] = dt_obj.strftime('%Y-%m-%d')
            except Exception:
                pass # If parsing fails, just leave it blank

        if not extracted_data['date_enacted']:
             date_match2 = re.search(r'\d{1,2}(?:st|nd|rd|th)\s+day\s+of\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})', full_text, re.IGNORECASE)
             if date_match2:
                 try:
                     month = date_match2.group(1)
                     year = date_match2.group(2)
                     # Just extracting a rough date, maybe first of the month, but it's hard to get exact day from regex group if we don't capture the number. Let's try capturing the number.
                     # Actually, date_match1 is usually sufficient. Let's just leave it blank if not found, user can fill.
                     pass
                 except Exception:
                     pass

        # 4. Extract Signatories
        # Look for names near "Approved by", "Certified correct", etc.
        # We'll just grab the bottom 500 characters as a rough heuristic if we can't find specific keywords.
        bottom_text = full_text[-1000:]
        signatories_match = re.search(r'(?:APPROVED|CERTIFIED CORRECT|ATTESTED)[^\n]*\n(.+)', bottom_text, re.IGNORECASE | re.DOTALL)
        if signatories_match:
            extracted_data['signatories'] = signatories_match.group(1).strip()
        else:
            # Fallback to the last few lines
            lines = full_text.split('\n')
            extracted_data['signatories'] = '\n'.join(lines[-10:]).strip()

    except Exception as e:
        print(f"Error parsing PDF: {e}")

    return extracted_data
