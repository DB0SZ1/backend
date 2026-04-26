import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GOOGLE_DRIVE_API_KEY')

def search_folder(name):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"name contains '{name}' and mimeType = 'application/vnd.google-apps.folder'",
        'key': api_key,
        'fields': "files(id, name, parents)"
    }
    r = requests.get(url, params=params)
    data = r.json()
    if 'files' in data:
        for f in data['files']:
            print(f"Found Folder: {f['name']} ({f['id']}) Parents: {f.get('parents')}")
    else:
        print(f"Error or no files: {data}")

if __name__ == "__main__":
    search_folder('original')
    search_folder('60-30 total')
    search_folder('60-30 photo shoot')
