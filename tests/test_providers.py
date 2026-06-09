"""运营商适配器的纯函数 (请求构建) 单测。"""

from core.types import ImageRef, TaskInput
from providers.openai_provider import OpenAIProvider
from providers.anthropic_provider import AnthropicProvider
from providers.google_provider import GoogleProvider
from providers.replicate_provider import ReplicateProvider


DATA_URI = "data:image/png;base64,QUJD"


def test_openai_text_only():
    ti = TaskInput(text="hello")
    assert OpenAIProvider.build_user_content(ti) == "hello"


def test_openai_with_image():
    ti = TaskInput(text="desc", images=[ImageRef(data_uri=DATA_URI)])
    content = OpenAIProvider.build_user_content(ti, "high")
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == DATA_URI
    assert content[1]["image_url"]["detail"] == "high"


def test_openai_payload_has_system():
    ti = TaskInput(text="q")
    payload = OpenAIProvider.build_payload("gpt-4o", "sys", ti, {"max_tokens": 100})
    assert payload["model"] == "gpt-4o"
    assert payload["messages"][0]["role"] == "system"
    assert payload["max_tokens"] == 100


def test_anthropic_image_parsing():
    ti = TaskInput(text="t", images=[ImageRef(data_uri=DATA_URI)])
    content = AnthropicProvider.build_content(ti)
    img = [c for c in content if c["type"] == "image"][0]
    assert img["source"]["media_type"] == "image/png"
    assert img["source"]["data"] == "QUJD"


def test_google_parts_inline_image():
    ti = TaskInput(text="t", images=[ImageRef(data_uri=DATA_URI)])
    parts = GoogleProvider.build_parts("sys", ti)
    assert any("inline_data" in p for p in parts)


def test_replicate_input_injects_prompt_and_image():
    ti = TaskInput(text="make it blue", images=[ImageRef(data_uri=DATA_URI)])
    model_input = ReplicateProvider.build_input("sys", ti, {"resolution": "1K"})
    assert "make it blue" in model_input["prompt"]
    assert model_input["resolution"] == "1K"
    assert model_input["image_input"] == [DATA_URI]


def test_replicate_capabilities():
    assert ReplicateProvider.capabilities == {"text2image", "image2image"}
    assert ReplicateProvider.is_async is True
