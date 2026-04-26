import json

def find_filler():
    try:
        with open('live_data_backup.json', 'r') as f:
            data = json.load(f)
            memories = data.get('memories', [])
            for m in memories:
                if m.get('type') == 'video' or 'mp4' in m.get('image_url', ''):
                    print(f"Video Found: ID={m.get('id')} Name={m.get('name')} Size={m.get('file_size')} URL={m.get('image_url')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_filler()
