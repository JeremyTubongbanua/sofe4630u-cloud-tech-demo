import boto3
from botocore.exceptions import ClientError
import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import credentials

def publish_message(message, topic_name, region=None, subject=None):
    try:
        sns_client = boto3.client('sns', region_name=region) if region else boto3.client('sns')
        topics_response = sns_client.list_topics()
        topic_arn = None
        for topic in topics_response.get('Topics', []):
            arn = topic['TopicArn']
            if arn.split(':')[-1] == topic_name:
                topic_arn = arn
                break
        if not topic_arn:
            return None
        publish_params = {
            'TopicArn': topic_arn,
            'Message': message
        }
        if subject:
            publish_params['Subject'] = subject
        response = sns_client.publish(**publish_params)
        return response
    except ClientError:
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--message', default='Hello, world!')
    parser.add_argument('--subject', default='System Alert')
    parser.add_argument('--region', default='us-east-2')
    parser.add_argument('--topic', default='tts')
    parser.add_argument('--rootkey_path', default='./rootkey.csv')

    args = parser.parse_args()

    credentials.get_aws_credentials(rootkey_path=args.rootkey_path)

    result = publish_message(
        args.message,
        topic_name=args.topic,
        region=args.region,
        subject=args.subject
    )

    if result:
        print("Message published successfully")
    else:
        print("Failed to publish message")