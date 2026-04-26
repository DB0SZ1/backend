import requests

API_KEY = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'

def list_all(parent_id, label):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{parent_id}' in parents and trashed = false",
        'key': API_KEY,
        'fields': "files(id, name, size, mimeType)"
    }
    r = requests.get(url, params=params)
    print(f"\n--- {label} ({parent_id}) ---")
    if r.status_code == 200:
        files = r.json().get('files', [])
        if not files:
            print("  (Empty)")
        for f in files:
            mtype = 'FOLDER' if f['mimeType'].endswith('folder') else 'FILE'
            size = f.get('size', '0')
            print(f"  {f['name']} ({f['id']}) [{mtype}] Size: {size}")
    else:
        print(f"  Error {r.status_code}: {r.text}")

def main():
    # More Fotos
    list_all('1dni9LnqDY8R-Gbr9m-nQHMhXTrmYANDK', 'More Fotos')
    
    # 60-30 photo shoot (if found earlier, let's check its parent or peer)
    # Root: 1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW
    list_all('1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW', 'Root Folder')

if __name__ == "__main__":
    main()
