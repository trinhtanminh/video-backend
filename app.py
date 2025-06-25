# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import logging
import re
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask app
app = Flask(__name__)
# Enable CORS với cấu hình chi tiết hơn
CORS(app, origins=["*"], methods=["GET", "POST"], allow_headers=["Content-Type"])

def is_valid_url(url):
    """Validate if the URL is properly formatted"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def is_supported_platform(url):
    """Check if the URL is from supported platforms"""
    supported_domains = [
        'youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com',
        'facebook.com', 'www.facebook.com', 'm.facebook.com', 'fb.watch'
    ]
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return any(supported_domain in domain for supported_domain in supported_domains)
    except:
        return False

@app.route('/api/get_video_info', methods=['POST', 'OPTIONS'])
def get_video_info():
    """
    API endpoint to fetch video information using yt-dlp.
    Accepts a JSON payload with a "url" key.
    """
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    try:
        # Get JSON data
        data = request.get_json()
        if not data:
            logging.warning("No JSON data received")
            return jsonify({
                "error": "error_invalid_url", 
                "message": "No data received"
            }), 400

        if 'url' not in data:
            logging.warning("URL key missing from request")
            return jsonify({
                "error": "error_invalid_url", 
                "message": "URL is missing"
            }), 400

        video_url = data['url'].strip()
        
        # Validate URL format
        if not video_url:
            return jsonify({
                "error": "error_invalid_url", 
                "message": "URL is empty"
            }), 400
            
        if not is_valid_url(video_url):
            return jsonify({
                "error": "error_invalid_url", 
                "message": "Invalid URL format"
            }), 400
            
        if not is_supported_platform(video_url):
            return jsonify({
                "error": "error_invalid_url", 
                "message": "Unsupported platform. Only YouTube and Facebook are supported."
            }), 400

        logging.info(f"Processing request for URL: {video_url}")

        # yt-dlp options với cấu hình tối ưu
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best[ext=mp4]/best',
            'extractaudio': False,
            'audioformat': 'mp3',
            'outtmpl': '%(title)s.%(ext)s',
            'ignoreerrors': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info without downloading
                info_dict = ydl.extract_info(video_url, download=False)
                
                if not info_dict:
                    return jsonify({
                        "error": "error_fetch_failed", 
                        "message": "Could not extract video information"
                    }), 400
                
                # --- Prepare the response ---
                title = info_dict.get('title', 'Unknown Title')
                thumbnail = info_dict.get('thumbnail', '')
                
                formats = []
                
                # Process formats
                raw_formats = info_dict.get('formats', [])
                if not raw_formats:
                    return jsonify({
                        "error": "error_fetch_failed", 
                        "message": "No video formats available"
                    }), 400
                
                # Filter and collect relevant formats
                for f in raw_formats:
                    # Skip formats without URL
                    if not f.get('url'):
                        continue
                        
                    # Skip formats that are neither video nor audio
                    if f.get('vcodec') == 'none' and f.get('acodec') == 'none':
                        continue
                    
                    file_size = f.get('filesize') or f.get('filesize_approx')
                    
                    # Create quality label
                    quality_label = f.get('format_note', '')
                    if not quality_label:
                        if f.get('height'):
                            quality_label = f"{f.get('height')}p"
                        elif f.get('vcodec') == 'none':
                            abr = f.get('abr')
                            quality_label = f"Audio ({abr}k)" if abr else "Audio"
                        else:
                            quality_label = f.get('format_id', 'Unknown')

                    formats.append({
                        'ext': f.get('ext', 'unknown'),
                        'quality': quality_label,
                        'size': file_size,
                        'url': f.get('url'),
                        'format_id': f.get('format_id'),
                        'height': f.get('height'),
                        'filesize': file_size
                    })
                
                if not formats:
                    return jsonify({
                        "error": "error_fetch_failed", 
                        "message": "No downloadable formats found"
                    }), 400
                
                # Sort and deduplicate formats
                # Sort by height (video quality) and then by filesize
                formats.sort(key=lambda x: (
                    -(x.get('height') or 0),  # Higher resolution first
                    -(x.get('filesize') or 0)  # Larger files first
                ))
                
                # Remove duplicates based on quality
                unique_formats = []
                seen_qualities = set()
                for f in formats:
                    quality_key = f'{f["quality"]}_{f["ext"]}'
                    if quality_key not in seen_qualities:
                        unique_formats.append(f)
                        seen_qualities.add(quality_key)
                
                # Limit to top 10 formats to avoid overwhelming UI
                unique_formats = unique_formats[:10]

                response = {
                    'title': title,
                    'thumbnail': thumbnail,
                    'formats': unique_formats,
                    'url': video_url
                }
                
                logging.info(f"Successfully processed URL: {video_url}. Found {len(unique_formats)} formats.")
                return jsonify(response), 200

        except yt_dlp.utils.DownloadError as e:
            error_message = str(e)
            logging.error(f"yt-dlp download error for URL {video_url}: {error_message}")
            
            # Check for specific error types
            if "Private video" in error_message or "unavailable" in error_message.lower():
                return jsonify({
                    "error": "error_fetch_failed", 
                    "message": "Video is private or unavailable"
                }), 400
            elif "not found" in error_message.lower():
                return jsonify({
                    "error": "error_fetch_failed", 
                    "message": "Video not found"
                }), 400
            else:
                return jsonify({
                    "error": "error_fetch_failed", 
                    "message": f"Could not process video: {error_message}"
                }), 400
                
        except Exception as e:
            logging.error(f"Unexpected error during video processing for URL {video_url}: {e}")
            return jsonify({
                "error": "error_server_error", 
                "message": "An internal error occurred while processing the video"
            }), 500

    except Exception as e:
        logging.error(f"Unexpected error in get_video_info: {e}")
        return jsonify({
            "error": "error_server_error", 
            "message": "An internal server error occurred"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Server is running"}), 200

@app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return jsonify({
        "message": "Video Downloader API", 
        "version": "1.0",
        "endpoints": ["/api/get_video_info", "/health"]
    }), 200

if __name__ == '__main__':
    # Run the app
    app.run(host='0.0.0.0', port=5001, debug=True)
