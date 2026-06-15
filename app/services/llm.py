import httpx


class OllamaUnavailableError(RuntimeError):
    pass


async def call_ollama(prompt: str, model: str, base_url: str, timeout: int) -> str:
    payload = {"model": model, "prompt": prompt, "stream": False}
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
