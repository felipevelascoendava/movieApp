import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import requests

app = Flask(__name__)
# Enable CORS for all routes so the browser/frontend can fetch data
CORS(app, resources={r"/*": {"origins": "*"}})

MONGO_URI = os.getenv("MONGO_URI", "mongodb://movie-db:27017/movies_db")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")

client = MongoClient(MONGO_URI)
db = client.get_database("movies_db")

@app.route("/api/movies", methods=["GET"])
def get_movies():
    try:
        category = request.args.get("category", "").lower().strip()
        query = {"category": category} if category else {}
        
        # EXPLICITLY exclude _id from projection: {"_id": 0}
        movies = list(db.movies.find(query, {"_id": 0}))
        
        return jsonify({
            "category": category or "all",
            "count": len(movies),
            "movies": movies
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/api/movies/summary", methods=["GET"])
def summarize_movies():
    category = request.args.get("category", "").lower().strip()
    query = {"category": category} if category else {}

    movies = list(db.movies.find(query, {"_id": 0}))

    if not movies:
        return jsonify({"category": category or "all", "count": 0, "summary": "No movies found."})

    movie_list = "\n".join(
        f"- {movie['title']} ({movie.get('year', 'year unknown')})"
        for movie in movies
    )

    prompt = (
        f"Give a short overview of these {category or 'movie'} titles. "
        "Only use the titles and years provided. Do not invent plot details.\n Recommend similar movies"
        f"{movie_list}"
    )

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "qwen2.5:0.5b",
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        summary = response.json()["response"]
        return jsonify({
            "category": category or "all",
            "count": len(movies),
            "movies": movies,
            "summary": summary,
        })
    except requests.RequestException:
        return jsonify({"error": "The AI service is unavailable. Try again shortly."}), 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
