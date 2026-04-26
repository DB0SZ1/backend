import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GOOGLE_DRIVE_API_KEY')

def get_children(folder_id, name_filter=None):
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
            if name_filter and name_filter.lower() in f['name'].lower():
                print(f"MATCH: {f['name']} ({f['id']})")
            if f['mimeType'] == 'application/vnd.google-apps.folder':
                get_children(f['id'], name_filter)
    else:
        print(f"Error listing {folder_id}: {data}")

if __name__ == "__main__":
    # Start from root
    get_children('1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW', 'original')
