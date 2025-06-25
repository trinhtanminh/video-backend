# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

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

    # More robust yt-dlp options to increase success rate
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'noplaylist': True,
        'ignoreerrors': True,  # Ignore errors on individual videos
        'geo_bypass': True,  # Attempt to bypass geographic restrictions
        'nocheckcertificate': True,  # Suppress SSL certificate verification
        'source_address': '0.0.0.0'  # Force IPv4, which can sometimes help
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract video information
            info_dict = ydl.extract_info(video_url, download=False)
            
            # Check if info was actually extracted
            if not info_dict:
                raise yt_dlp.utils.DownloadError("Failed to extract video information.")

            title = info_dict.get('title', 'No title')
            thumbnail = info_dict.get('thumbnail', '')
            
            formats = []
            
            # Check if any formats are available
            if not info_dict.get('formats'):
                 raise yt_dlp.utils.DownloadError("No downloadable formats found for this video.")

            # Collect and filter formats
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
            
            # Raise error if no valid formats were found
            if not formats:
                raise yt_dlp.utils.DownloadError("Could not find any valid formats with direct URLs.")

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
        # Return the actual error message from yt-dlp to the frontend
        error_message = str(e).replace('ERROR: ', '') # Clean up the message a bit
        logging.error(f"yt-dlp download error for URL {video_url}: {error_message}")
        return jsonify({"error": "error_fetch_failed", "message": error_message}), 400
    except Exception as e:
        logging.error(f"An unexpected error occurred for URL {video_url}: {e}")
        return jsonify({"error": "error_server_error", "message": "An internal server error occurred."}), 500

if __name__ == '__main__':
    # Render will use gunicorn to run the app. This section is for local testing.
    # The port can be changed if 5001 is in use.
    app.run(host='0.0.0.0', port=5001, debug=True)
