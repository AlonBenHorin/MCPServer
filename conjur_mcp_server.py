import json
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Dict

import boto3

app = FastAPI()

# Use Claude 3.5 Sonnet
BEDROCK_MODEL_ID = "anthropic.claude-3-7-sonnet-20250219-v1:0"
CONJUR_CLOUD_URL = 'alonbtest.secretsmgr.cyberark-everest-integdev.cloud'

# Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# Tools schema (informational only for prompt, not passed to model)
TOOLS = [
    {
        "name": "get_secret_value",
        "description": "Retrieves the value of a secret from Conjur Cloud.",
        "arguments": {
            "secret_id": {
                "type": "string",
                "description": "The full path of the secret (e.g., 'data/my-secret')"
            }
        },
        "required": ["secret_id"]
    },
    {
        "name": "set_secret_value",
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
        "required": ["secret_id", "secret_value"]
    },
    {
        "name": "generate_policy",
        "description": "Craft a Conjur Cloud policy in a YAML format.",
        "arguments": {
            "policy": {
                "type": "string",
                "description": "The policy in YAML format"
            }
        },
        "required": ["policy"]
    }
]

class MCPRequest(BaseModel):
    prompt: str

@app.post("/mcp")
async def mcp_handler(req: Request, body: MCPRequest):
    token = req.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    prompt = body.prompt.strip()

    # Create instruction prompt
    instruction = (
        "You are a tool selector for Conjur Cloud.\n"
        "Your job is to extract the correct tool to use and return a JSON like:\n"
        "{\"tool\": \"tool_name\", \"arguments\": { ... } }\n"
        f"Valid tools are: {TOOLS}.\n"
        "ONLY return the JSON object. Do not include any explanations or extra text.\n"
        "if the user request does not exactly suit to any tool - return an empty string in the tool name.\n"
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

    result = json.loads(response["body"].read())
    text_output = result["content"][0]["text"]

    try:
        start = text_output.index("{")
        json_part = text_output[start:]
        parsed = json.loads(json_part)
        tool_name = parsed["tool"]
        if tool_name == '':
            return 'No matching tool'
        args = parsed["arguments"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse model output: {text_output}")

    data = RequestData(
        args = args,
        tool_name='',
        url="https://api.example.com/data",
    )

    if tool_name == "get_secret_value":
        data.url = f'https://{CONJUR_CLOUD_URL}/api/secrets/conjur/variable/{args["secret_id"]}' # TODO url encode
        data.tool_name = 'Get Secret'
    elif tool_name == "set_secret_value":
        data.url = f'https://{CONJUR_CLOUD_URL}/api/secrets/conjur/variable/{args["secret_id"]}' # TODO url encode
        data.tool_name = 'Set Secret'
    elif tool_name == "generate_policy":
        data.url = f'https://{CONJUR_CLOUD_URL}/api/policies/conjur/policy/data'
        data.tool_name = 'Load Policy'
    else:
        raise HTTPException(status_code=400, detail="No matching tool found.")
    
    return data
    


class RequestData(BaseModel):
    url: HttpUrl
    tool_name: str
    args: Dict[str, str]