import json

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError


class LLMClient:
    """Thin wrapper around the OpenAI-compatible chat API."""

    def __init__(self, config: dict):
        llm_cfg = config["llm"]
        self.client = OpenAI(
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg.get("base_url", "https://api.openai.com/v1"),
        )
        self.model = llm_cfg.get("model", "gpt-4o")
        # Longer timeout for processing large documents (default is 10 minutes)
        self.timeout = llm_cfg.get("timeout", 600)

    def chat(
        self,
        messages: list[dict],
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion request and return the assistant reply.

        Parameters
        ----------
        messages : list[dict]
            OpenAI-style messages (role/content dicts).
        json_mode : bool
            If True, request JSON output via response_format.

        Returns
        -------
        str  The assistant's reply text.
        """
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "timeout": self.timeout,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except APITimeoutError:
            raise RuntimeError(
                "LLM API request timed out. Check your network or try again."
            )
        except APIConnectionError:
            raise RuntimeError(
                "Cannot connect to the LLM API. Check base_url in config.yaml."
            )
        except APIError as e:
            raise RuntimeError(f"LLM API error: {e.message}")

    def chat_json(self, messages: list[dict]) -> dict:
        """Send a chat request expecting JSON, parse and return as dict."""
        text = self.chat(messages, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```" in text:
                start = text.find("```")
                end = text.rfind("```")
                if start != end:
                    block = text[start:end].split("\n", 1)
                    if len(block) > 1:
                        try:
                            return json.loads(block[1])
                        except json.JSONDecodeError:
                            pass
            raise RuntimeError(
                f"LLM returned invalid JSON. Raw response:\n{text[:500]}"
            )

    def chat_stream(
        self,
        messages: list[dict],
    ):
        """Send a chat completion request and stream the response.

        Parameters
        ----------
        messages : list[dict]
            OpenAI-style messages (role/content dicts).

        Yields
        ------
        str  Chunks of the assistant's reply text.
        """
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "timeout": self.timeout,
        }

        try:
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except APITimeoutError:
            raise RuntimeError(
                "LLM API request timed out. Check your network or try again."
            )
        except APIConnectionError:
            raise RuntimeError(
                "Cannot connect to the LLM API. Check base_url in config.yaml."
            )
        except APIError as e:
            raise RuntimeError(f"LLM API error: {e.message}")
