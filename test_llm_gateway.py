import json
import os
import unittest
from unittest.mock import patch

from llm_gateway import LLMConfig, chat_completion, config_from_env, missing_api_key_message


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LLMGatewayTest(unittest.TestCase):
    def test_config_from_env_defaults_to_deepseek_compatible_endpoint(self):
        env = {"LLM_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=True):
            config = config_from_env()

        self.assertEqual(config.base_url, "https://api.deepseek.com")
        self.assertEqual(config.model, "deepseek-chat")
        self.assertEqual(config.api_key, "test-key")

    def test_config_from_env_accepts_deepseek_api_key_alias(self):
        env = {"DEEPSEEK_API_KEY": "deepseek-key"}
        with patch.dict(os.environ, env, clear=True):
            config = config_from_env()

        self.assertEqual(config.api_key, "deepseek-key")

    def test_missing_api_key_message_names_supported_variables(self):
        message = missing_api_key_message()

        self.assertIn("LLM_API_KEY", message)
        self.assertIn("DEEPSEEK_API_KEY", message)

    def test_chat_completion_posts_openai_compatible_payload(self):
        config = LLMConfig(
            api_key="test-key",
            base_url="https://example.test/v1/",
            model="deepseek-chat",
            timeout=12,
            temperature=0.1,
            max_tokens=300,
        )
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": "答案"}}]})

        with patch("urllib.request.urlopen", fake_urlopen):
            answer = chat_completion("测试 prompt", config=config)

        self.assertEqual(answer, "答案")
        self.assertEqual(captured["url"], "https://example.test/v1/chat/completions")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(captured["body"]["model"], "deepseek-chat")
        self.assertEqual(captured["body"]["messages"][0]["role"], "user")
        self.assertEqual(captured["body"]["messages"][0]["content"], "测试 prompt")
        self.assertEqual(captured["body"]["temperature"], 0.1)
        self.assertEqual(captured["body"]["max_tokens"], 300)


if __name__ == "__main__":
    unittest.main()
