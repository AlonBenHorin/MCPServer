import boto3
from botocore.exceptions import ClientError

models = [
    "anthropic.claude-3-haiku-20240307-v1:0",
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0"
]


bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

for model_id in models:
    try:
        print(f"Testing {model_id}...")
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=b'{"prompt":"Hello","max_tokens":5}'
        )
        print(f"✅ Access granted: {model_id}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessDeniedException":
            print(f"❌ Access denied: {model_id}")
        else:
            print(f"⚠️ Error with {model_id}: {e}")
