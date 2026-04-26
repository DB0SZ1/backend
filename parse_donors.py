import json
import re

# Parse PDF text to get donations
donations = []

with open('c:/Users/hi/Downloads/backend-main/pdf_text_utf8.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_parsing = False
for line in lines:
    line = line.strip()
    if "Payment DateLast Name INITIALS OF DONOR Donation" in line:
        start_parsing = True
        continue
    if not start_parsing:
        continue
        
    if "£3,989.47" in line:
        break
        
    # Match lines like "11 / 23 / 2025 Olali CTO £100.00"
    # or "10/12/2025 Omodeinde BO £20.00"
    # or "30/11/2025 15:36 Tayuta61@yahoo.comOS £20.00"
    
    # Let's use a regex to extract amount
    match = re.search(r'£([\d,]+\.\d{2})', line)
    if match:
        amount_str = match.group(1).replace(',', '')
        amount = float(amount_str)
        
        # Extract an email or name
        parts = line.split('£')[0].strip()
        # Find email if exists
        email_match = re.search(r'[\w\.-]+@[\w\.-]+', parts)
        email = email_match.group(0) if email_match else 'anonymous@example.com'
        
        # Use the whole part as donor_name just in case
        name = parts
        
        donations.append({
            'donor_name': name,
            'donor_email': email,
            'amount': amount,
            'status': 'completed',
            'stripe_payment_id': f'pdf_historic_{len(donations)}'
        })

print(f"Extracted {len(donations)} donations.")

# Load live_data_backup.json
with open('c:/Users/hi/Downloads/backend-main/backend-main/live_data_backup.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

# Update donations list
data['donations'] = donations

# Add the hardcoded charities list to the JSON so it can be read from there as well, maintaining one source of truth!
charities = [
    { 'name': 'Black Health Initiative (BHI)', 'amount': '£200.00', 'icon': 'fa-heartbeat' },
    { 'name': 'Bridge Community Church (BCC)', 'amount': '£200.00', 'icon': 'fa-church' },
    { 'name': 'Cape Christian Radio', 'amount': '£200.00', 'icon': 'fa-broadcast-tower' },
    { 'name': 'CBN (700 Club) Operation Blessing', 'amount': '£100.00', 'icon': 'fa-hands-helping' },
    { 'name': 'Christian Concern', 'amount': '£200.00', 'icon': 'fa-cross' },
    { 'name': 'College of Health Sciences Alumni, Uniport', 'amount': '₦100,000.00', 'icon': 'fa-graduation-cap' },
    { 'name': 'Eagle BizNet UK CIC & YBBA', 'amount': '£100.00', 'icon': 'fa-briefcase' },
    { 'name': 'Evangelical Alliance', 'amount': '£100.00', 'icon': 'fa-users' },
    { 'name': 'Everlasting Fathers Assembly (EFA)', 'amount': '£200.00', 'icon': 'fa-place-of-worship' },
    { 'name': 'FGC Port Harcourt OSA (UK & Class of 1980)', 'amount': '£100.00 + ₦100k', 'icon': 'fa-school' },
    { 'name': 'Support for Mankind Development Initiative', 'amount': '₦300,000.00', 'icon': 'fa-globe-africa' },
    { 'name': 'New Testament Church of God Leeds', 'amount': '£200.00', 'icon': 'fa-church' },
    { 'name': 'Nigerian Community Leeds (NCL)', 'amount': '£200.00', 'icon': 'fa-users' },
    { 'name': "Ama ibi Gose Ogoloma Women's Cooperative", 'amount': '₦500,000.00', 'icon': 'fa-female' },
    { 'name': 'Shalom Health International', 'amount': '£100.00', 'icon': 'fa-clinic-medical' },
    { 'name': "St James's Church Ogoloma Scholarships", 'amount': '₦500,000.00', 'icon': 'fa-book-reader' },
    { 'name': 'Uniport 80s Alumni Association', 'amount': '₦200,000.00', 'icon': 'fa-user-graduate' },
    { 'name': 'Wakirike Language Programme', 'amount': '₦200,000.00', 'icon': 'fa-language' },
    { 'name': 'Wakirike Students Union (National)', 'amount': '₦100,000.00', 'icon': 'fa-user-graduate' },
    { 'name': 'United Christian Broadcasters', 'amount': '£100.00', 'icon': 'fa-tv' },
    { 'name': 'Ogoloma Unity Choir Youth Skills', 'amount': '₦1,200,000.00', 'icon': 'fa-music' },
    { 'name': 'Wakirike UK & Ireland (Language App)', 'amount': '£200.00', 'icon': 'fa-mobile-alt' },
    { 'name': 'Seconds for Good (S4G)', 'amount': '₦200,000.00', 'icon': 'fa-clock' }
]

data['charities'] = charities

with open('c:/Users/hi/Downloads/backend-main/backend-main/live_data_backup.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("Updated live_data_backup.json with donations and charities!")
