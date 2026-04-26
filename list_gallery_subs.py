import requests

API_KEY = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'

def list_subs(parent_id, label):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{parent_id}' in parents and trashed = false",
        'key': API_KEY,
        'fields': "files(id, name, mimeType)"
    }
    r = requests.get(url, params=params)
    if r.status_code == 200:
        files = r.json().get('files', [])
        print(f"--- {label} ({parent_id}) ---")
        for f in files:
            print(f"  {f['name']} ({f['id']}) [{'FOLDER' if f['mimeType'].endswith('folder') else 'FILE'}]")
    else:
        print(f"Error {r.status_code} for {label}")

def main():
    # More Photos & Videos
    list_subs('1y_wNlt9cNvvYFpbwdC33kDB7_sM3ybhB', 'More Photos & Videos')

if __name__ == "__main__":
    main()
