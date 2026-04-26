import requests
import time

API_KEY = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'
ROOT_ID = '1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW'

def get_items(parent_id, is_folder=True):
    mime_type = 'application/vnd.google-apps.folder' if is_folder else None
    q = f"'{parent_id}' in parents and trashed = false"
    if is_folder:
        q += f" and mimeType = '{mime_type}'"
    
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': q,
        'key': API_KEY,
        'fields': "files(id, name, mimeType, size, durationMillis)" if not is_folder else "files(id, name)"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json().get('files', [])
        print(f"Error {response.status_code} for {parent_id}: {response.text}")
    except Exception as e:
        print(f"Exception for {parent_id}: {str(e)}")
    return []

def recursive_search(parent_id, path="", visited=None):
    if visited is None:
        visited = set()
    if parent_id in visited:
        return
    visited.add(parent_id)

    folders = get_items(parent_id, is_folder=True)
    for folder in folders:
        name = folder['name']
        fid = folder['id']
        current_path = f"{path} / {name}"
        print(f"FOLDER: {current_path} ({fid})")
        
        # Check if it matches our targets
        if 'original' in name.lower() or 'photo shoot' in name.lower():
            print(f"!!! MATCH FOUND: {name} ID: {fid} !!!")
        
        # Look for files in this folder
        files = get_items(fid, is_folder=False)
        for f in files:
            fname = f['name']
            fsize = f.get('size', 'unknown')
            # Check for small videos or filler
            if f['mimeType'].startswith('video/') or 'mp4' in fname.lower() or 'mov' in fname.lower():
                print(f"  VIDEO: {fname} (Size: {fsize})")
                if 'filler' in fname.lower() or (fsize != 'unknown' and int(fsize) < 1000000): # < 1MB
                    print(f"  -> Potential Filler! ID: {f['id']}")

        # Recurse
        recursive_search(fid, current_path, visited)

def main():
    print(f"Starting deep recursive search from root: {ROOT_ID}")
    recursive_search(ROOT_ID)

if __name__ == "__main__":
    main()
