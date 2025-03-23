import boto3
import time
import sys
import os
import uuid
import json
from credentials import read_credentials

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
            
            output_file = f"{os.path.splitext(file_path)[0]}_transcript.txt"
            with open(output_file, 'w') as f:
                f.write(transcript_text)
            
            s3_transcript_path = f"{unique_id}_transcript.txt"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_transcript_path,
                Body=transcript_text
            )
            
            print(f"Transcript saved locally to: {output_file}")
            print(f"Audio stored in S3 as: {s3_file_path}")
            print(f"Transcript stored in S3 as: {s3_transcript_path}")
            
            return transcript_text
        else:
            error_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown error')
            print(f"Transcription failed: {error_reason}")
            return None
    
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <path_to_m4a_file> [language_code]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    language_code = sys.argv[2] if len(sys.argv) > 2 else 'en-US'
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        sys.exit(1)
    
    transcribe_audio(file_path, language_code)