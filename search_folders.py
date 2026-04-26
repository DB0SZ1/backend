import requests

API_KEY = 'AIzaSyDVNDujWpE-vaOu9Dk8jTZfEEq7LSvjlvE'
ROOT_ID = '1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW'

def get_subfolders(parent_id):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        'key': API_KEY,
        'fields': "files(id, name)"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('files', [])
    except:
        pass
    return []

def search_recursive(parent_id, target_names, depth=0, max_depth=4):
    if depth > max_depth:
        return
    
    folders = get_subfolders(parent_id)
    for f in folders:
        print(f"{'  ' * depth}Folder: {f['name']} (ID: {f['id']})")
        for target in target_names:
            if target.lower() in f['name'].lower():
                print(f"\n*** MATCH FOUND: {f['name']} - ID: {f['id']} ***\n")
        
        search_recursive(f['id'], target_names, depth + 1, max_depth)

def main():
    targets = ['original', 'photo shoot']
    print(f"Searching for {targets} starting from {ROOT_ID}...")
    search_recursive(ROOT_ID, targets)

if __name__ == "__main__":
    main()
