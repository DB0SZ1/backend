import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GOOGLE_DRIVE_API_KEY')

def list_drive(folder_id, depth=0):
    if depth > 2: return
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{folder_id}' in parents and trashed = false",
        'key': api_key,
        'fields': "files(id, name, mimeType)"
    }
    r = requests.get(url, params=params)
    data = r.json()
    if 'files' in data:
        for f in data['files']:
            print(f"{'  '*depth} {f['name']} ({f['id']}) [{'FOLDER' if f['mimeType'] == 'application/vnd.google-apps.folder' else 'FILE'}]")
            if f['mimeType'] == 'application/vnd.google-apps.folder':
                list_drive(f['id'], depth+1)
    else:
        print(f"Error: {data}")

if __name__ == "__main__":
    # Root of 60-30 total? Or root of official photos?
    # front-page.html says rootId: '1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW'
    list_drive('1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW')
