import os
import yt_dlp
import google.generativeai as genai
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
import subprocess
import whisper
import json
import time

# Load API Keys
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
CORS(app)

# Download YouTube audio with progress tracking
def download_audio(youtube_url):
    progress_callback = {'progress': 0, 'status': 'Downloading video audio...'}
    
    def my_hook(d):
        if d['status'] == 'downloading':
            if 'total_bytes' in d and d['total_bytes'] > 0:
                # Calculate download percentage
                progress = (d['downloaded_bytes'] / d['total_bytes']) * 25  # 25% of the total process
                progress_callback['progress'] = progress
            elif 'downloaded_bytes' in d:
                # If total size unknown, use a simulated progress
                progress_callback['progress'] = min(20, progress_callback['progress'] + 1)

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'audio',
            'progress_hooks': [my_hook],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        # Convert MP3 to WAV for better Whisper support
        progress_callback['status'] = 'Converting audio format...'
        progress_callback['progress'] = 25  # Audio download complete
        wav_path = "audio.wav"
        subprocess.run(["ffmpeg", "-i", "audio.mp3", wav_path, "-y"], check=True)
        
        progress_callback['progress'] = 30  # Conversion complete
        return wav_path, progress_callback
    except Exception as e:
        print("Error downloading audio:", str(e))
        return None, progress_callback

# Transcribe audio using local Whisper
def transcribe_audio(audio_path, progress_callback):
    try:
        progress_callback['status'] = 'Loading Whisper model...'
        progress_callback['progress'] = 30
        model = whisper.load_model("small")
        
        progress_callback['status'] = 'Transcribing audio...'
        progress_callback['progress'] = 35
        
        # Start transcription
        result = model.transcribe(audio_path)
        
        progress_callback['progress'] = 70  # Transcription complete
        progress_callback['status'] = 'Transcription complete'
        return result["text"], progress_callback
    except Exception as e:
        print("Error in local Whisper transcription:", str(e))
        return None, progress_callback

# Summarize text using Gemini AI
def summarize_text(text, progress_callback):
    try:
        progress_callback['status'] = 'Generating summary with AI...'
        progress_callback['progress'] = 70
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(f"Provide a detailed and informative summary of the following transcript (dont make it too short):\n\n{text}")
        
        progress_callback['progress'] = 95  # Summary generation complete
        progress_callback['status'] = 'Finalizing summary...'
        return response.text if response and hasattr(response, 'text') else None, progress_callback
    except Exception as e:
        print("Error in Gemini API:", str(e))
        return None, progress_callback

@app.route('/summarize', methods=['POST'])
def summarize():
    data = request.json
    youtube_url = data.get('url')

    if not youtube_url:
        return jsonify({"error": "No URL provided"}), 400

    def generate():
        progress_callback = {'progress': 0, 'status': 'Starting process...'}
        try:
            # Step 1: Download audio
            yield f"data: {json.dumps(progress_callback)}\n\n"
            audio_path, progress_callback = download_audio(youtube_url)
            yield f"data: {json.dumps(progress_callback)}\n\n"
            
            if not audio_path:
                yield f"data: {json.dumps({'error': 'Failed to download audio'})}\n\n"
                return
            
            # Step 2: Transcribe audio
            transcript, progress_callback = transcribe_audio(audio_path, progress_callback)
            yield f"data: {json.dumps(progress_callback)}\n\n"
            
            if not transcript:
                yield f"data: {json.dumps({'error': 'Failed to transcribe audio'})}\n\n"
                return
            
            # Step 3: Summarize text
            summary, progress_callback = summarize_text(transcript, progress_callback)
            yield f"data: {json.dumps(progress_callback)}\n\n"
            
            if not summary:
                yield f"data: {json.dumps({'error': 'Failed to generate summary'})}\n\n"
                return
            
            # Step 4: Cleanup and return result
            progress_callback['progress'] = 100
            progress_callback['status'] = 'Complete'
            yield f"data: {json.dumps(progress_callback)}\n\n"
            
            # Send the final summary
            yield f"data: {json.dumps({'summary': summary, 'progress': 100})}\n\n"
            
            # Cleanup audio files
            if os.path.exists("audio"):
                os.remove("audio")
            if os.path.exists("audio.mp3"):
                os.remove("audio.mp3")
            if os.path.exists("audio.wav"):
                os.remove("audio.wav")
            if os.path.exists("audio.mp3.mp3"):
                os.remove("audio.mp3.mp3")
                
        except Exception as e:
            print("Server Error:", str(e))
            yield f"data: {json.dumps({'error': 'Internal Server Error', 'details': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(port=5000, debug=True)