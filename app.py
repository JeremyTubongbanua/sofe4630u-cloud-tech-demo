from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
import uuid
import json
import boto3
from credentials import read_credentials
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024

def transcribe_audio(file_path, language_code='en-US'):
    access_key_id, secret_access_key = read_credentials.get_aws_credentials()
    bucket_name = 'cloud-transcribe-meow'
    region = 'us-east-2'
    s3_client = boto3.client(
        's3',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region
    )
    transcribe_client = boto3.client(
        'transcribe',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region
    )
    
    unique_id = str(uuid.uuid4())
    job_name = f"transcribe-job-{unique_id}"
    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1]
    s3_file_path = f"{unique_id}{file_extension}"
    
    try:
        print(f"Uploading {file_path} to S3 as {s3_file_path}...")
        s3_client.upload_file(file_path, bucket_name, s3_file_path)
        
        print("Starting transcription job...")
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': f"s3://{bucket_name}/{s3_file_path}"},
            MediaFormat='mp4',
            LanguageCode=language_code
        )
        
        while True:
            status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            if job_status in ['COMPLETED', 'FAILED']:
                break
            
            print(f"Transcription in progress. Status: {job_status}")
            time.sleep(30)
        
        if job_status == 'COMPLETED':
            transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
            print(f"Transcription completed. Downloading transcript...")
            
            import urllib.request
            response = urllib.request.urlopen(transcript_uri)
            transcript_data = json.loads(response.read())
            
            transcript_text = transcript_data['results']['transcripts'][0]['transcript']
            
            s3_transcript_path = f"{unique_id}_transcript.txt"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_transcript_path,
                Body=transcript_text
            )
            
            print(f"Audio stored in S3 as: {s3_file_path}")
            print(f"Transcript stored in S3 as: {s3_transcript_path}")
            
            return {
                "success": True,
                "transcript": transcript_text,
                "s3_audio_path": s3_file_path,
                "s3_transcript_path": s3_transcript_path
            }
        else:
            error_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown error')
            print(f"Transcription failed: {error_reason}")
            return {
                "success": False,
                "error": f"Transcription failed: {error_reason}"
            }
    
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.route('/api/languages', methods=['GET'])
def get_languages():
    languages = [
        {"code": "en-US", "name": "English (US)"},
        {"code": "fr-CA", "name": "French (Canada)"},
    ]
    return jsonify(languages)

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
    
    language_code = request.form.get('language', 'en-US')
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            result = transcribe_audio(file_path, language_code)
            os.remove(file_path)
            return jsonify(result)
        except Exception as e:
            os.remove(file_path)
            return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)