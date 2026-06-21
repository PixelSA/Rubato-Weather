from flask import Flask, render_template, request, jsonify
import requests
import random
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# ⚠️ PASTE YOUR SPOTIFY CREDENTIALS HERE
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

def get_spotify_token():
    """Requests a temporary access token from Spotify using Client Credentials"""
    auth_url = "https://accounts.spotify.com/api/token"
    auth_response = requests.post(auth_url, {
        'grant_type': 'client_credentials',
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    })
    
    # Convert response to JSON and extract the token string
    auth_response_data = auth_response.json()
    return auth_response_data.get('access_token')

def search_spotify_track(keyword, token):
    if not token:
        return None
        
    search_url = "https://api.spotify.com/v1/search"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # Example: "lofi rainy day genre:chill" or "summer pop genre:pop"
    genre_mapping = "genre:chill" if "rain" in keyword or "cloud" in keyword else "genre:pop"
    full_query = f"{keyword} {genre_mapping}"
    
    params = {
        "q": full_query,
        "type": "track",
        "limit": 5
    }
    
    response = requests.get(search_url, headers=headers, params=params).json()
    
    try:
        tracks = response.get('tracks', {}).get('items', [])
        if not tracks:
            return None
            
        track = random.choice(tracks)
        return {
            "song_title": track.get('name'),
            "artist": track.get('artists', [{}])[0].get('name'),
            "album_art": track.get('album', {}).get('images', [{}])[0].get('url'),
            "spotify_url": track.get('external_urls', {}).get('spotify'),
            "preview_url": track.get('preview_url', '')
        }
    except Exception as e:
        print(f"Search failed: {e}")
        return None

def get_weather_playlist_keyword(weather_text, is_day):
    """Maps WeatherAPI text and time of day to a music search query"""
    weather_text = weather_text.lower()
    
    if "rain" in weather_text or "drizzle" in weather_text or "mist" in weather_text:
        if is_day == 0: return "midnight jazz lofi"
        return "lofi rainy day acoustic"
    elif "thunder" in weather_text or "storm" in weather_text:
        return "atmospheric dark post rock"
    elif "snow" in weather_text or "sleet" in weather_text:
        return "winter lofi chill"
    elif "sunny" in weather_text or "clear" in weather_text:
        if is_day == 0: return "synthwave night drive"
        return "upbeat summer hits"
    elif "cloud" in weather_text or "overcast" in weather_text:
        return "indie chill folk"
    
    return "chill atmospheric beats"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get-weather-music')
def get_weather_music():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        return jsonify({"error": "Missing coordinates"}), 400

    try:
        # 1. Fetch current weather from WeatherAPI
        weather_url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={lat},{lon}&aqi=no"
        weather_response = requests.get(weather_url).json()
        
        weather_condition = weather_response['current']['condition']['text']
        is_day = weather_response['current']['is_day'] 
        
        # 2. Get your matching search string
        search_keyword = get_weather_playlist_keyword(weather_condition, is_day)
        
        # 3. Connect to Spotify and pull live track data
        spotify_token = get_spotify_token()
        music_data = search_spotify_track(search_keyword, spotify_token)
        print(f"DEBUG: Weather='{weather_condition}', Day={is_day}, Search='{search_keyword}', MusicData={music_data}")
        
        if not music_data:
            # Fallback structure if Spotify search returns empty results
            music_data = {
                "song_title": "Ambient Skies", "artist": "The Weather Beats Ensemble",
                "album_art": "", "preview_url": "", "spotify_url": "#"
            }

        # 4. Return the complete package to React
        return jsonify({
            "weather": weather_condition,
            "is_day": is_day,
            "song_title": music_data["song_title"],
            "artist": music_data["artist"],
            "album_art": music_data["album_art"],
            "preview_url": music_data["preview_url"],
            "spotify_url": music_data["spotify_url"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)