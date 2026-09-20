import os, sys
from dotenv import load_dotenv
load_dotenv()
import requests

key = os.getenv('YOUTUBE_API_KEY')

# Search for Google Photos tutorial/review videos
searches = [
    "google photos search tips tutorial",
    "google photos ask photos review",
    "google photos search not working",
    "google photos find old photos",
    "google photos video search not working",
    "google photos find videos",
]

video_ids = {}
for q in searches:
    r = requests.get(
        'https://www.googleapis.com/youtube/v3/search',
        params={'part':'snippet','q':q,'type':'video','maxResults':5,'key':key},
        timeout=15
    )
    for item in r.json().get('items', []):
        vid = item['id']['videoId']
        title = item['snippet']['title']
        video_ids[vid] = title

for vid, title in video_ids.items():
    safe = title[:70].encode('ascii', errors='replace').decode('ascii')
    print(f"{vid} - {safe}")
