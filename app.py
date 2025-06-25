# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
# Enable CORS to allow requests from your frontend (GitHub Pages)
# It's good practice to restrict this to your actual domain in production
CORS(app) 

@app.route('/api/get_video_info', methods=['POST'])
def get_video_info():
    """
    API endpoint to fetch video information using yt-dlp.
    Accepts a JSON payload with a "url" key.
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "error_invalid_url", "message": "URL is missing."}), 400

    video_url = data['url']
    logging.info(f"Received request for URL: {video_url}")

    # yt-dlp options
    # We ask for a format list without actually downloading the video
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # Prioritize mp4
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            
            # --- Prepare the response ---
            title = info_dict.get('title', 'No title')
            thumbnail = info_dict.get('thumbnail', '')
            
            formats = []
            
            # Filter and collect relevant formats
            for f in info_dict.get('formats', []):
                # We only want formats with a direct URL that we can send to the client
                if f.get('url') and (f.get('vcodec') != 'none' or f.get('acodec') != 'none'):
                    file_size = f.get('filesize') or f.get('filesize_approx')
                    
                    # Create a quality label
                    quality_label = f.get('format_note')
                    if not quality_label:
                        if f.get('height'):
                            quality_label = f"{f.get('height')}p"
                        elif f.get('vcodec') == 'none':
                            quality_label = f"Audio ({f.get('abr')}k)"
                        else:
                            quality_label = "Unknown"

                    formats.append({
                        'ext': f.get('ext'),
                        'quality': quality_label,
                        'size': file_size,
                        'url': f.get('url'),
                    })
            
            # Simple deduplication based on quality label to avoid clutter
            unique_formats = []
            seen_qualities = set()
            for f in sorted(formats, key=lambda x: x.get('size') or 0, reverse=True):
                if f['quality'] not in seen_qualities:
                    unique_formats.append(f)
                    seen_qualities.add(f['quality'])


            response = {
                'title': title,
                'thumbnail': thumbnail,
                'formats': unique_formats,
            }
            
            logging.info(f"Successfully processed URL: {video_url}. Found {len(unique_formats)} unique formats.")
            return jsonify(response)

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"yt-dlp download error for URL {video_url}: {e}")
        return jsonify({"error": "error_fetch_failed", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"An unexpected error occurred for URL {video_url}: {e}")
        return jsonify({"error": "error_server_error", "message": "An internal server error occurred."}), 500

if __name__ == '__main__':
    # Run the app. 
    # Use host='0.0.0.0' to make it accessible on your local network.
    # The port is changed to 5001 to avoid conflicts.
    app.run(host='0.0.0.0', port=5001, debug=True)
