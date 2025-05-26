import json
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Dict

import boto3
import json

app = FastAPI()

# Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

TOOLS = [
    {
        "tool": "get_secret_value",
        "description": "Retrieves the value of a secret from Conjur Cloud",
    },
    {
        "tool": "set_secret_value",
        "description": "Sets the value of a secret in Conjur Cloud.",
    },
    {
        "tool": "load_policy",
        "description": "Loads a policy in conjur cloud.",

    },
    {
        "tool": "show_resource",
        "description": "The response to this method is a JSON document describing a single resource. The endpoint for show_resource is: {kind}/{identifier}",

    }
]

class MCPRequest(BaseModel):
    prompt: str

@app.post("/ai/mcp")
async def mcp_handler(body: MCPRequest):
    prompt = body.prompt.strip()

    # Create instruction prompt
    instruction = (f"""You are a tool selector for Conjur Cloud.
        Your job is to analyze the user request and select the appropriate tool, then return a JSON response.
        Available tools:{TOOLS}
        
        Instructions:
        1. Analyze the user request and determine which tool best matches their intent
        2. Return ONLY a JSON object with these fields:
           - "tool": The name of the tool to use (or empty string if no match)
           - "branch": The relative uri resource path, e.g., "data/lev"
           - "method_type": The HTTP method ("GET", "POST", "PUT", "DELETE")
           - "request_body": The body content (empty string if not applicable)
        
        3. If the user request doesn't match any available tool, set "tool" to an empty string
        4. Do not include explanations or extra text - only return the JSON object
        5. Try to guess the resource kind from the user request, if not specified in the request, assume it is a variable
        User request: "{prompt}"
        """
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse model output: {text_output}")

    data = RequestData(
        body = parsed["request_body"],
        method_name= parsed["method_type"],
        tool_name=parsed["tool"],
        branch=parsed["branch"],
    )
    print(data)
    return data


class RequestData(BaseModel):
    branch: str
    tool_name: str
    body: str
    method_name: str
