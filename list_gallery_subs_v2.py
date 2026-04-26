import requests

API_KEY = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'

def list_items(parent_id, label, is_folder=True):
    mime_type = 'application/vnd.google-apps.folder' if is_folder else None
    q = f"'{parent_id}' in parents and trashed = false"
    if is_folder:
        q += f" and mimeType = '{mime_type}'"
    
    params = {
        'q': q,
        'key': API_KEY,
        'fields': "files(id, name, size, mimeType)"
    }
    r = requests.get("https://www.googleapis.com/drive/v3/files", params=params)
    if r.status_code == 200:
        files = r.json().get('files', [])
        print(f"--- {label} ({parent_id}) ---")
        for f in files:
            size_str = f.get('size', 'N/A')
            mtype = 'FOLDER' if f['mimeType'].endswith('folder') else 'FILE'
            print(f"  {f['name']} ({f['id']}) [{mtype}] Size: {size_str}")
    else:
        print(f"Error {r.status_code} for {label}")

def main():
    # More Fotos
    list_items('1dni9LnqDY8R-Gbr9m-nQHMhXTrmYANDK', 'More Fotos')
    
    # Also check More Photos & Videos for small files (potential filler)
    print("\nChecking for potential filler videos in More Photos & Videos...")
    list_items('1y_wNlt9cNvvYFpbwdC33kDB7_sM3ybhB', 'Videos check', is_folder=False)

if __name__ == "__main__":
    main()
