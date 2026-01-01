from flask import Flask, render_template, request, jsonify, session
import os
import replicate
import fal_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key_123') # Basic session security
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 # 10MB Limit

# Credits Config
INITIAL_CREDITS = 3
COST_PER_GEN = 1
REWARD_AMOUNT = 5

# Allowed extensions
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# You need a REPLICATE_API_TOKEN in a .env file
# Get one here: https://replicate.com/account/api-tokens

@app.route('/')
def index():
    if 'credits' not in session:
        session['credits'] = INITIAL_CREDITS
    return render_template('index.html')

@app.route('/credits', methods=['GET'])
def get_credits():
    return jsonify({'credits': session.get('credits', 0)})

@app.route('/reward', methods=['POST'])
def reward_credits():
    # In a real app, verify the ad callback signature here
    session['credits'] = session.get('credits', 0) + REWARD_AMOUNT
    return jsonify({'credits': session['credits'], 'message': f'Added {REWARD_AMOUNT} credits!'})

@app.route('/generate', methods=['POST'])
def generate_music():
    try:
        if session.get('credits', 0) < COST_PER_GEN:
             return jsonify({'error': 'Insufficient credits. Watch an ad to get more!'}), 402

        data = request.json
        prompt = data.get('prompt')
        duration = int(data.get('duration', 8)) # seconds

        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        # Using Meta's MusicGen model
        output = replicate.run(
            "meta/musicgen:7be0f12c54a8d033a0fbd14418c9af98962da9a86f5ff7811f9b3423a1f0b7d7",
            input={
                "prompt": prompt,
                "duration": duration
            }
        )
        
        # Output is usually a URL to the audio file
        session['credits'] -= COST_PER_GEN
        return jsonify({'audio_url': output, 'credits': session['credits']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/remix', methods=['POST'])
def remix_music():
    try:
        if session.get('credits', 0) < COST_PER_GEN:
             return jsonify({'error': 'Insufficient credits. Watch an ad to get more!'}), 402

        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file uploaded'}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '' or not allowed_file(audio_file.filename):
             return jsonify({'error': 'Invalid file type. Only MP3/WAV/OGG allowed.'}), 400

        prompt = request.form.get('prompt')
        duration = int(request.form.get('duration', 8))

        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        # Save temp file
        temp_path = f"temp_{audio_file.filename}"
        audio_file.save(temp_path)

        # Using MusicGen Melody (better for remixing/following structure)
        # We need to upload the file to Replicate (or pass it as a file handle)
        with open(temp_path, "rb") as file_handle:
            output = replicate.run(
                "meta/musicgen:7be0f12c54a8d033a0fbd14418c9af98962da9a86f5ff7811f9b3423a1f0b7d7",
                input={
                    "prompt": prompt,
                    "input_audio": file_handle,
                    "duration": duration,
                    "model_version": "melody" 
                }
            )

        # Cleanup
        try:
            os.remove(temp_path)
        except PermissionError:
            pass # Windows sometimes holds onto files; ignore if we can't delete immediately

        session['credits'] -= COST_PER_GEN
        return jsonify({'audio_url': output, 'credits': session['credits']})

    except Exception as e:
        # Cleanup in case of error
        if 'audio_file' in locals() and os.path.exists(f"temp_{audio_file.filename}"):
             try:
                os.remove(f"temp_{audio_file.filename}")
             except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/video', methods=['POST'])
def generate_video():
    try:
        if session.get('credits', 0) < COST_PER_GEN:
             return jsonify({'error': 'Insufficient credits. Watch an ad to get more!'}), 402

        data = request.json
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({'error': 'Visual prompt is required'}), 400

        # Using Fal.ai Minimax (High Quality Text-to-Video)
        handler = fal_client.submit(
            "fal-ai/minimax-video",
            arguments={
                "prompt": prompt,
                "duration": 5
            }
        )
        result = handler.get()
        video_url = result['video']['url']
        
        session['credits'] -= COST_PER_GEN
        return jsonify({'video_url': video_url, 'credits': session['credits']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
