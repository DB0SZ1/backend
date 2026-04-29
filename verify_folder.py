import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GOOGLE_DRIVE_API_KEY')

def list_files(folder_id):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{folder_id}' in parents and trashed = false",
        'key': api_key,
        'fields': "files(id, name, mimeType)"
    }
    r = requests.get(url, params=params)
    data = r.json()
    if 'files' in data:
        print(f"Files in {folder_id}:")
        for f in data['files']:
            print(f" - {f['name']} ({f['id']})")
    else:
        print(f"Error: {data}")

if __name__ == "__main__":
    list_files('1mM-olaqamckgcpCguQEB3jvXjPnrurYo')
