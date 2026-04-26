import requests

API_KEY = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'

def search_folders(name_query):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"name contains '{name_query}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        'key': API_KEY,
        'fields': "files(id, name)"
    }
    r = requests.get(url, params=params)
    print(f"\n--- Search results for '{name_query}' ---")
    if r.status_code == 200:
        files = r.json().get('files', [])
        if not files:
            print("  (No results)")
        for f in files:
            print(f"  {f['name']} ({f['id']})")
    else:
        print(f"  Error {r.status_code}: {r.text}")

def main():
    names = ['original', 'shoot', 'Messages', 'Passwords', 'Secrets']
    for name in names:
        search_folders(name)

if __name__ == "__main__":
    main()
