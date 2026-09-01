import json
from collections.abc import AsyncIterator

import httpx


def _model_names(data: dict) -> list[str]:
    return [
        str(item.get("name") or item.get("model"))
        for item in data.get("models", [])
        if item.get("name") or item.get("model")
    ]


class OllamaUnavailableError(RuntimeError):
    pass


async def call_ollama(prompt: str, model: str, base_url: str, timeout: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base_url}/api/generate", json=payload)
    except httpx.ConnectError as exc:
        raise OllamaUnavailableError(f"Cannot connect to Ollama at {base_url}.") from exc
    except httpx.TimeoutException as exc:
        raise OllamaUnavailableError(
            f"Ollama request timed out after {timeout}s."
        ) from exc
    except httpx.RequestError as exc:
        raise OllamaUnavailableError(f"Ollama request failed: {exc}") from exc

    if resp.status_code != 200:
        raise OllamaUnavailableError(
            f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    data = resp.json()
    answer = data.get("response", "").strip()
    if not answer:
        raise OllamaUnavailableError("Ollama returned an empty response.")

    return answer


async def get_ollama_info(base_url: str, model: str, timeout: int = 10) -> dict:
    """Check Ollama connectivity and whether the configured model is installed."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            tags_response = await client.get(f"{base_url}/api/tags")
            version_response = await client.get(f"{base_url}/api/version")
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        raise OllamaUnavailableError(f"Cannot connect to Ollama at {base_url}.") from exc

    if tags_response.status_code != 200:
        raise OllamaUnavailableError(
            f"Ollama returned HTTP {tags_response.status_code} while listing models."
        )

    names = _model_names(tags_response.json())
    configured_present = model in names
    version = None
    if version_response.status_code == 200:
        version = version_response.json().get("version")

    return {
        "status": "ok" if configured_present else "degraded",
        "version": version,
        "configured_model": model,
        "configured_model_present": configured_present,
        "models": names,
    }


async def stream_ollama(
    prompt: str, model: str, base_url: str, timeout: int
) -> AsyncIterator[dict]:
    """Yield token and completion dictionaries from Ollama's NDJSON stream."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.1},
    }
    received_text = False
    completed = False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", f"{base_url}/api/generate", json=payload
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode(errors="replace")
                    raise OllamaUnavailableError(
                        f"Ollama returned HTTP {response.status_code}: {body[:200]}"
                    )
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise OllamaUnavailableError(
                            "Ollama returned an invalid streaming response."
                        ) from exc
                    if data.get("error"):
                        raise OllamaUnavailableError(str(data["error"]))
                    token = data.get("response")
                    if token:
                        received_text = True
                        yield {"type": "token", "text": str(token)}
                    if data.get("done"):
                        if not received_text:
                            raise OllamaUnavailableError(
                                "Ollama returned an empty response."
                            )
                        completed = True
                        yield {
                            "type": "complete",
                            "prompt_tokens": data.get("prompt_eval_count"),
                            "output_tokens": data.get("eval_count"),
                        }
                if not completed:
                    raise OllamaUnavailableError(
                        "Ollama ended the stream before completion."
                    )
    except httpx.TimeoutException as exc:
        raise OllamaUnavailableError(
            f"Ollama request timed out after {timeout}s."
        ) from exc
    except httpx.RequestError as exc:
        raise OllamaUnavailableError(f"Cannot connect to Ollama at {base_url}.") from exc
