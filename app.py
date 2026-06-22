from flask import Flask, render_template, request, jsonify
import requests
import random
import json
from dotenv import load_dotenv
import google.generativeai as genai
import os

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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
    
    # genre_mapping = "genre:chill" if "rain" in keyword or "cloud" in keyword else "genre:pop"
    full_query = f"{keyword}"
    
    params = {
        "q": full_query,
        "type": "track",
        "limit": 1
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

def get_gemini_music_recommendation(weather_text, is_day, temperature) -> list[str]:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        if is_day:
            time_of_day = "daytime"
        else:
            time_of_day = "nighttime"

        prompt = (
            f"Give me a list of 5 great song recommendations for the following atmosphere: "
            f"Weather is {weather_text}, it is {time_of_day}, and the temperature is {temperature}. "
            f"Return ONLY a JSON array of song titles and artists with keys 'song_title' and 'artist'. Do not include conversational filler. "
            f"Example: [{{'song_title': 'Holocene', 'artist': 'Bon Iver'}}, {{'song_title': 'Starman', 'artist': 'David Bowie'}}]"
        )

        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        print(response.text)
        
        # Try to parse the response as JSON
        try:
            result = json.loads(response.text)
            #print(f"Gemini response parsed as JSON: {result}")
            return result if isinstance(result, list) else [response.text]
        except json.JSONDecodeError:
            # Fallback if response isn't valid JSON
            return [response.text]
    except Exception as e:
        print(f"Gemini API error: {e}")
        return []
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
        temperature = weather_response['current']['temp_c']
        is_day = weather_response['current']['is_day'] 
        
        # 2. Get matching search string
        result = get_gemini_music_recommendation(weather_condition, is_day, temperature)
        # print(f"DEBUG: Gemini raw result: {result}")
        choice = random.choice(result) if result else None
        artist = choice["artist"] if choice else None
        title = choice["song_title"] if choice else None
        search_keyword = f"track:{title} artist:{artist}" if result else get_weather_playlist_keyword(weather_condition, is_day)

        # print(f"DEBUG: Gemini result: {result}, Search keyword: {search_keyword}")
        
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
            "temperature": temperature,
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
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))