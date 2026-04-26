import requests
import json
import os

BASE_URL = "https://backend-mmng.onrender.com/api"
OUTPUT_FILE = "live_data_backup.json"

def fetch_data(endpoint, limit=1000, is_post=False):
    print(f"Fetching {endpoint}...")
    try:
        if is_post:
            response = requests.post(f"{BASE_URL}/{endpoint}", json={"limit": limit}, timeout=30)
        else:
            response = requests.get(f"{BASE_URL}/{endpoint}?limit={limit}", timeout=30)
            
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            return data
        else:
            print(f"Error in response for {endpoint}: {data.get('message', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"Failed to fetch {endpoint}: {e}")
        return None

def main():
    print("Starting data extraction from live Render API...")
    
    backup_data = {
        "messages": [],
        "memories": [],
        "gallery_folders": [],
        "stats": {}
    }
    
    # 1. Fetch Messages
    messages_res = fetch_data("messages", limit=2000)
    if messages_res and 'messages' in messages_res:
        backup_data["messages"] = messages_res['messages']
        print(f"✅ Fetched {len(messages_res['messages'])} messages")
        
    # 2. Fetch Memories (Photos, Videos, Text)
    # The API structure usually returns all types if type='all'
    response = requests.get(f"{BASE_URL}/memories?type=all&limit=2000")
    if response.status_code == 200:
        memories_res = response.json()
        if memories_res.get('success'):
            backup_data["memories"] = memories_res.get('memories', [])
            print(f"✅ Fetched {len(backup_data['memories'])} memories")
    
    # 3. Fetch Gallery Folders
    folders_res = fetch_data("gallery/folders")
    if folders_res and 'folders' in folders_res:
        backup_data["gallery_folders"] = folders_res['folders']
        print(f"✅ Fetched {len(folders_res['folders'])} gallery folders")
        
        # Optionally fetch images per folder if needed
        # (Assuming the client doesn't need to rebuild gallery structure from scratch if they just rely on standard Cloudinary memories, but let's grab them anyway)
        for folder in folders_res['folders']:
            folder_name = folder['name']
            images_res = requests.get(f"{BASE_URL}/gallery/images?folder={folder_name}").json()
            if images_res.get('success'):
                folder['images'] = images_res.get('images', [])
                print(f"  - Folder '{folder_name}': {len(folder['images'])} images")

    # 4. Fetch general stats (including donations total, though we likely can't fetch private donor details via public endpoints)
    stats_res = fetch_data("stats")
    if stats_res and 'stats' in stats_res:
        backup_data["stats"] = stats_res['stats']
        print(f"✅ Fetched general stats")

    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=4, ensure_ascii=False)
        
    print(f"\n🎉 Extraction complete! Saved all data to {OUTPUT_FILE}")
    print(f"Total size: {os.path.getsize(OUTPUT_FILE) / 1024:.2f} KB")

if __name__ == "__main__":
    main()
