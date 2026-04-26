import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GOOGLE_DRIVE_API_KEY')

def get_file_info(file_id):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    params = {
        'key': api_key,
        'fields': "id, name, parents"
    }
    r = requests.get(url, params=params)
    print(f"Info for {file_id}: {r.json()}")

if __name__ == "__main__":
    get_file_info('1I0ulGY8KOYu8jZrync2BHAdYV3MevyRW')
