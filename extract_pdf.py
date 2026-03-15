import sys
try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not installed. Please run 'py -m pip install pypdf'")
    sys.exit(1)

files = [
    "60-30 Fundraising.pdf",
    "60-30 Fundraising - Disbursement.pdf"
]

for pdf in files:
    print(f"\n{'='*50}\nReading: {pdf}\n{'='*50}")
    try:
        reader = PdfReader(pdf)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            print(f"--- Page {i+1} ---")
            print(text.strip())
    except Exception as e:
        print(f"Failed to read {pdf}: {e}")
