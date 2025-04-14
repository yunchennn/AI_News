from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from bs4 import BeautifulSoup
import requests
import time
import src.LLM.deepLLM as deepLLM
import sqlite3

app = Flask(__name__)
CORS(app)  # Enables CORS for all domains

@app.route('/news')
def get_latest_news():
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("SELECT source, url, summary, timestamp FROM summaries ORDER BY timestamp DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    return {
        "news": [
            {"source": r[0], "url": r[1], "summary": r[2], "timestamp": r[3]}
            for r in rows
        ]
    }


@app.route('/summary', methods=['POST'])
def summarize_news():
    data = request.json
    url = data.get("url")

    if not url:
        return {"error": "Missing URL"}, 400

    try:
        summary = deepLLM.getReport(url)
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == '__main__':
    app.run(debug=True)  # Run the app in debug mode
