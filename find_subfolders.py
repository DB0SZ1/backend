import requests

def list_subfolders(parent_id, api_key):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        'key': api_key,
        'fields': "files(id, name)"
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get('files', [])
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return []

def main():
    api_key = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'
    # Parent: More Photos & Videos
    parent_id = '1y_wNlt9cNvvYFpbwdC33kDB7_sM3ybhB'
    
    folders = list_subfolders(parent_id, api_key)
    print(f"Subfolders of '{parent_id}':")
    for f in folders:
        print(f"{f['name']}: {f['id']}")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
