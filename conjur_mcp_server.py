import json
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Dict

import boto3
import json

app = FastAPI()

# Use Claude 3.5 Sonnet
BEDROCK_MODEL_ID = "anthropic.claude-3-7-sonnet-20250219-v1:0"
CONJUR_CLOUD_URL = 'https://alonbtest.secretsmgr.cyberark-everest-integdev.cloud'

# Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

TOOLS = [
    {
        "tool": "get_secret_value",
        "description": "Retrieves the value of a secret from Conjur Cloud.",
        "arguments": {
            "secret_id": {
                "type": "string",
                "description": "The full path of the secret (e.g., 'data/my-secret')"
            }
        },
        # "required": ["secret_id"]
    },
    {
        "tool": "set_secret_value",
        "description": "Sets the value of a secret in Conjur Cloud.",
        "arguments": {
            "secret_id": {
                "type": "string",
                "description": "The full path of the secret (e.g., 'data/my-secret')"
            },
            "secret_value": {
                "type": "string",
                "description": "The value of the secret"
            }
        },
    },
    {
        "tool": "load_policy",
        "description": "Loads a policy in conjur cloud.",
        "arguments": {
            "body": {
                "type": "string",
                "description": "Policy body in YAML format"
            },
            "url": {
                "type": "string",
                "description": "The branch to load the policy to (e.g., 'data/my-branch')"
            }
        },
    }
]

class MCPRequest(BaseModel):
    prompt: str

@app.post("/ai/mcp")
async def mcp_handler(req: Request, body: MCPRequest):
    prompt = body.prompt.strip()

    # Create instruction prompt
    instruction = (
        "You are a tool selector for Conjur Cloud.\n"
        "Your job is to extract the correct tool to use and return a JSON like:\n"

        "{\"tool\": \"tool_name\", \"url\": \"request_uri\", \"method_type\": \"method_type\", \"request_body\": \"body\"}\n"
        f"Valid tools are: {TOOLS}.\n"
        "ONLY return the JSON object. Do not include any explanations or extra text.\n"
        "If the user request does not exactly suit any tool - return an empty string in the tool name.\n"
        "Please provide these details in the JSON:\n"
        "- tool: The name of the tool to use (e.g., 'get_secret_value')\n"
        "- request_body: The body of the request if applicable (e.g., for set_secret_value)\n"  # Fixed: was "body"
        "- method_type: The HTTP method to use (e.g., 'GET', 'POST')\n"  # Fixed: was "method_name"
        "- url: The URL to call for the tool\n"

        "The user request is: '" + prompt + "'"
    )

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {
                "role": "user",
                "content": instruction
            }
        ],
        "max_tokens": 512  # REQUIRED
    }

    response = bedrock.invoke_model(
        modelId="arn:aws:bedrock:us-east-1:238637036211:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json"
    )
    print(f"Response from Bedrock: {response}")

    result = json.loads(response["body"].read())
    print(f"Response.body from Bedrock: {result}")

    text_output = result["content"][0]["text"]

    try:
        start = text_output.index("{")
        json_part = text_output[start:]
        parsed = json.loads(json_part)
        tool_name = parsed["tool"]
        if tool_name == '':
            return 'No matching tool'

        # args = parsed["arguments"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse model output: {text_output}")

    data = RequestData(
        body = parsed["request_body"],
        method_name= parsed["method_type"],
        tool_name=parsed["tool"],
        branch=parsed["url"],
    )
    print(data)
    return data


class RequestData(BaseModel):
    branch: str
    tool_name: str
    body: str
    method_name: str
