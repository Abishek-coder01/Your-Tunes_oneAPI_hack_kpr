import os
from flask import Flask, session, url_for, request, redirect, render_template
from spotipy import Spotify
import json
import base64
from requests import post, get
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from beyondllm import retrieve, generator
from beyondllm.source import fit
import re
# from beyondllm.embeddings import GeminiEmbeddings
# from beyondllm.llms import GeminiModel
from beyondllm.embeddings import FastEmbedEmbeddings
from beyondllm.llms import OllamaModel
from dotenv import load_dotenv

load_dotenv()
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')

# embed_model = GeminiEmbeddings(api_key=google_api, model_name="models/embedding-001")
embed_model = FastEmbedEmbeddings(model_name="your_fast_embed_model_name")
# llm = GeminiModel(model_name="gemini-pro") 
# llm = ipex.optimize(llm, dtype=torch.float16)
llm = OllamaModel(model="wizardlm2")
# llm2 = OllamaModel(model="llama3.2")
# llm3 = OllamaModel(model="phi3.5")
data = fit(path="data/text.md", dtype="md", chunk_size=512, chunk_overlap=100)
retriever = retrieve.auto_retriever(data=data, embed_model=embed_model, type="normal", top_k=4)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)

redirect_uri = 'http://localhost:5000/callback'
scope = "playlist-read-private, user-modify-playback-state, user-read-playback-state, playlist-modify-private, playlist-modify-public, user-top-read"


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)

redirect_uri = 'http://localhost:5000/callback'
scope = "playlist-read-private, user-modify-playback-state, user-read-playback-state, playlist-modify-private, playlist-modify-public, user-top-read"

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)

sp = Spotify(auth_manager=sp_oauth)

def get_token():
    auth_string = client_id + ":" + client_secret
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-type": "application/x-www-form-urlencoded"
    }

    data = {"grant_type": "client_credentials"}
    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result["access_token"]
    return token

def get_auth_header(token):
    return {"Authorization": "Bearer " + token}


def search_song_id(token, song_name):
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q={song_name}&type=track&limit=1"
    query_url = url + query
    result = get(query_url, headers=headers)
    json_result = json.loads(result.content)
    tracks = json_result.get("tracks", {}).get("items", [])
    if not tracks:
        return None
    return tracks[0]


def search_artists_id(token, artist_name):
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q={artist_name}&type=artist&limit=1"
    query_url = url + query
    result = get(query_url, headers=headers)
    json_result = json.loads(result.content)["artists"]["items"]
    if not json_result:
        return None
    return json_result[0]


def get_songs_of_artist(token, artist_id):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?country=ID"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    json_result = json.loads(result.content)["tracks"]
    return json_result

def safe_call(pipeline):
    try:
        return pipeline.call()
    except Exception as e:
        print(f"Error: {e}")
        return None



def extract_songs(text):
    # Assuming each song is on a new line
    lines = text.split('\n')
    songs = [line.strip() for line in lines if line.strip()]
    return songs

def clean_song_list(song_list):
    cleaned_songs = []
    for song in song_list:
        # Split by ". " and take the part after it, which removes the numbering
        cleaned_song = song.split('. ', 1)[-1].strip()
        cleaned_songs.append(cleaned_song)
    
    # Remove duplicates by converting to a set, then back to a list
    unique_songs = list(set(cleaned_songs))
    return unique_songs

def songs_from_top_artists(user_input):
    top_artists = sp.current_user_top_artists(limit=5, offset=0, time_range='medium_term')
    artists_name = [artist['name'] for artist in top_artists['items']]
    
    pipeline = generator.Generate(
        question=user_input,
        system_prompt=f"You are a playlist generator based on the user's {user_input} from {artists_name}. Provide 10 songs that match the user input and situation. I need the output in a simple list format, one song per line.",
        retriever=retriever,
        llm=llm
    )
    
    response = safe_call(pipeline)
    if response:
        songs = extract_songs(response)
        # Clean the song list to remove numbers and duplicates
        unique_cleaned_songs = clean_song_list(songs)
        print("Getting unique and cleaned songs from top artists")
        print(unique_cleaned_songs)
        return unique_cleaned_songs
    
    return []


def playlist_generator(user_input, preferred_language):
    pipeline = generator.Generate(
        question=f"Give me a list of songs based on this mood {user_input}. I need the output in the format 'song'.",
        system_prompt=f"""You are a playlist generator based on the {user_input}. 
        Provide 50 songs that match {user_input} and output only in {preferred_language}. 
        I need you to send the name of the song in English text.""",
        retriever=retriever,
        llm=llm
    )
    
    response = safe_call(pipeline)
    if response:
        songs = extract_songs(response)
        # Clean the song list to remove numbers and duplicates
        unique_cleaned_songs = clean_song_list(songs)
        print("Generating unique and cleaned songs based on user's input")
        print(unique_cleaned_songs)
        return unique_cleaned_songs
    
    return []


def extract_playlist_name(text):
    match = re.search(r'^\s*"(.+?)"\s*$|^\s*\*\*(.+?)\*\*\s*$|^\s*(\w[\w\s]*)\s*$', text)
    if match:
        return match.group(1) or match.group(2) or match.group(3)
    return text


def playlist_name_generator(user_input):
    pipeline = generator.Generate(
        question="Generate one Name for my playlist",
        system_prompt=f"""Based on the user input and {user_input}, generate a single name for the playlist that resonates with the mood.
        i need the response in one to three words""",
        retriever=retriever,
        llm=llm
    )
    response = safe_call(pipeline)
    extracted_name = extract_playlist_name(response)
    if extracted_name is None:
        print("YourTunes")
        return "YourTunes"
    print(response)
    return response

def playlist_description_generator(user_input, name):
    pipeline = generator.Generate(
        question=f"i need description for my playlist based on {user_input} and {name}",
        system_prompt=f"Generate a brief description for the a playlist just the description no ned additional explanation.",
        retriever=retriever,
        llm=llm
    )
    response = safe_call(pipeline)
    print(response)
    return response

@app.route('/')
def login():
    return render_template("yourtunes.html")

@app.route('/home')
def home():
    return render_template("yourtunes.html")

if __name__ == '__main__':
    app.run(debug=True)