import requests
import json

BASE_URL = "https://backend-production-65be.up.railway.app"

def export_all_data():
    print("Exporting data from Railway...")
    
    # Export messages
    print("Fetching messages...")
    messages = requests.get(f"{BASE_URL}/api/messages?limit=10000").json()
    with open("backup_messages.json", "w") as f:
        json.dump(messages, f, indent=2)
    print(f"✓ Saved {len(messages.get('messages', []))} messages")
    
    # Export memories
    print("Fetching memories...")
    memories = requests.get(f"{BASE_URL}/api/memories?type=all&limit=10000").json()
    with open("backup_memories.json", "w") as f:
        json.dump(memories, f, indent=2)
    print(f"✓ Saved {len(memories.get('memories', []))} memories")
    
    # Export stats
    print("Fetching stats...")
    stats = requests.get(f"{BASE_URL}/api/stats").json()
    with open("backup_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"✓ Saved stats")
    
    # Export gallery folders
    print("Fetching gallery...")
    gallery = requests.get(f"{BASE_URL}/api/gallery/folders").json()
    with open("backup_gallery.json", "w") as f:
        json.dump(gallery, f, indent=2)
    print(f"✓ Saved gallery data")
    
    print("\n✅ All data exported successfully!")
    print("Files created:")
    print("  - backup_messages.json")
    print("  - backup_memories.json")
    print("  - backup_stats.json")
    print("  - backup_gallery.json")

if __name__ == "__main__":
    export_all_data()