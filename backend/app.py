from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq
import re
import json
import os

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.environ.get("GROQ_API_KEY")) # Replace with your Groq API key

def extract_video_id(url):
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript(video_id):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import WebshareProxyConfig
        
        proxy_config = WebshareProxyConfig(
            proxy_username="",
            proxy_password="",
        )
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
        fetched = ytt_api.fetch(video_id)
        full_text = " ".join([entry.text for entry in fetched])
        return full_text
    except Exception as e:
        print("Transcript error:", str(e))
        return None

def generate_mindmap_data(transcript):
    """Use Groq API to generate mind map structure"""
    prompt = f"""
    Analyze this video transcript and create a structured mind map.
    
    Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:
    {{
        "title": "Main Topic of the Video",
        "children": [
            {{
                "title": "Main Branch 1",
                "children": [
                    {{"title": "Sub point 1", "children": []}},
                    {{"title": "Sub point 2", "children": []}}
                ]
            }},
            {{
                "title": "Main Branch 2",
                "children": [
                    {{"title": "Sub point 1", "children": []}},
                    {{"title": "Sub point 2", "children": []}}
                ]
            }}
        ]
    }}
    
    Rules:
    - Minimum 5 main branches, maximum 7
    - Minimum 5 sub-points per branch, maximum 8
    - Each sub-point must have specific facts, examples or details from the video
    - Keep titles short (under 8 words)
    - Focus on key concepts only
    
    Transcript:
    {transcript[:6000]}
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.choices[0].message.content.strip()
    response_text = re.sub(r'```json|```', '', response_text).strip()
    return json.loads(response_text)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')
@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.get_json()
    youtube_url = data.get('url', '').strip()

    if not youtube_url:
        return jsonify({'error': 'YouTube URL is required'}), 400

    video_id = extract_video_id(youtube_url)
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    transcript = get_transcript(video_id)
    if not transcript:
        return jsonify({'error': 'Could not fetch transcript. Make sure the video has subtitles/captions enabled.'}), 400

    try:
        mindmap_data = generate_mindmap_data(transcript)
        return jsonify({'success': True, 'data': mindmap_data})
    except Exception as e:
        return jsonify({'error': f'Failed to generate mind map: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))