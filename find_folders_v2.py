import requests

def get_file_info(file_id, api_key):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    params = {'key': api_key, 'fields': "id, name, mimeType"}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")
    return None

def list_subfolders(parent_id, api_key):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        'key': api_key,
        'fields': "files(id, name)"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('files', [])
        print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")
    return []

def main():
    api_key = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'
    root_id = '1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW'
    
    info = get_file_info(root_id, api_key)
    if info:
        print(f"Root Folder Name: {info['name']} (ID: {root_id})")
        
        folders = list_subfolders(root_id, api_key)
        for f in folders:
            print(f"  Subfolder: {f['name']} (ID: {f['id']})")
            if f['name'].lower() == 'more photos & videos':
                print(f"--- Drilling into {f['name']} ---")
                subs = list_subfolders(f['id'], api_key)
                for s in subs:
                    print(f"    - {s['name']}: {s['id']}")

if __name__ == "__main__":
    main()
