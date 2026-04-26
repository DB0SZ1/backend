import os
import requests
import json

def find_original_folder():
    key = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'
    url = 'https://www.googleapis.com/drive/v3/files'
    
    # Try searching for '60-30 total' specifically
    print("Searching for '60-30 total'...")
    params = {
        'q': "name = '60-30 total' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        'key': key,
        'fields': 'files(id, name)'
    }
    try:
        r = requests.get(url, params=params)
        print(f"60-30 total search result: {r.json()}")
    except Exception as e:
        print(f"Error: {e}")

    # Search for 'original' specifically
    print("Searching for 'original'...")
    params['q'] = "name = 'original' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    try:
        r = requests.get(url, params=params)
        print(f"original search result: {r.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    find_original_folder()
