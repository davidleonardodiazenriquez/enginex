"""Responses API adapter for the portfolio analyst's function-call loop."""

import re
from urllib import parse

from django.conf import settings

from core.ai.tools import TOOLS
from core.integrations import foundry


def request_payload(messages, *, allow_tools):
    chat_url, is_v1 = foundry._chat_endpoint()
    endpoint = parse.urlsplit(chat_url)
    path = endpoint.path.removesuffix("/chat/completions") + "/responses"
    if not is_v1:
        path = re.sub(r"/openai/deployments/[^/]+/responses$", "/openai/v1/responses", path)
    query = [(key, value) for key, value in parse.parse_qsl(endpoint.query)
             if key != "api-version" or value == "preview"]
    url = parse.urlunsplit((endpoint.scheme, endpoint.netloc, path, parse.urlencode(query), ""))
    inputs = []
    for message in messages:
        if "_response_output" in message:
            # Replay every output item, including encrypted reasoning, before
            # submitting function results; state stays within this application turn.
            inputs.extend(message["_response_output"])
        elif message["role"] == "tool":
            inputs.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                           "output": message["content"]})
        else:
            inputs.append({"role": message["role"], "content": message["content"]})
    payload = {
        "model": settings.AZURE_AI_FOUNDRY_DEPLOYMENT.strip(),
        "input": inputs, "max_output_tokens": 6000, "store": False,
        "reasoning": {"effort": "low"}, "include": ["reasoning.encrypted_content"],
    }
    if allow_tools:
        # Preserve optional filters in the existing, server-validated schemas.
        payload.update(tools=[{"type": "function", **tool["function"], "strict": False} for tool in TOOLS],
                       tool_choice="auto")
    return url, payload


def parse_reply(body):
    if not isinstance(body, dict) or body.get("status") != "completed" or not isinstance(body.get("output"), list):
        raise ValueError("Incomplete model response")
    text, calls = [], []
    for item in body["output"]:
        if item["type"] == "function_call":
            if not all(isinstance(item.get(key), str) and item[key] for key in ("call_id", "name", "arguments")):
                raise ValueError("Invalid function call")
            calls.append({"id": item["call_id"], "type": "function",
                          "function": {"name": item["name"], "arguments": item["arguments"]}})
        elif item["type"] == "message":
            for content in item.get("content", []):
                if content["type"] == "output_text":
                    text.append(content["text"])
                elif content["type"] == "refusal":
                    text.append(content["refusal"])
    return {"role": "assistant", "content": "\n".join(text), "tool_calls": calls,
            "_response_output": body["output"]}
