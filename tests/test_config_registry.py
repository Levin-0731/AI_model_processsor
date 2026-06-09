"""配置迁移与能力矩阵校验单测。"""

import os
import tempfile

import pytest
import yaml

from core.config import load_config
from core.registry import validate_capability, get_task_class
from core.types import TaskOutput


def _write_yaml(data):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)
    return path


def test_flat_config_migrates_to_image2text():
    path = _write_yaml({
        "provider": "bltcy", "model_name": "gpt-4o",
        "input_file": "data/x.xlsx", "prompt_file": "prompts/prompt.md",
        "image_column": "image_marker", "image_source": "embedded", "max_workers": 1,
    })
    cfg = load_config(path)
    os.unlink(path)
    assert cfg.task == "image2text"
    assert cfg.input["type"] == "excel"
    assert cfg.output["type"] == "table"
    assert cfg.model == "gpt-4o"


def test_flat_config_text_only_maps_text2text():
    path = _write_yaml({
        "provider": "deepseek", "model_name": "deepseek-chat",
        "input_file": "data/x.csv", "prompt_file": "p.md",
    })
    cfg = load_config(path)
    os.unlink(path)
    assert cfg.task == "text2text"
    assert cfg.input["type"] == "csv"


def test_nested_config_kept_as_is():
    path = _write_yaml({
        "provider": "replicate", "model": "google/nano-banana-2", "task": "image2image",
        "input": {"type": "folder", "path": "原图"},
        "output": {"type": "image", "path": "结果图"},
    })
    cfg = load_config(path)
    os.unlink(path)
    assert cfg.task == "image2image"
    assert cfg.input["type"] == "folder"


def test_capability_matrix_rejects_invalid_combo():
    with pytest.raises(ValueError):
        validate_capability("openai", "image2image")
    validate_capability("replicate", "image2image")  # 不应抛错


def test_image2text_json_postprocess():
    task = get_task_class("image2text")()
    out = TaskOutput(text='前缀\n```json\n{"a": 1}\n```\n后缀')
    out = task.postprocess(out)
    assert out.text == '{"a": 1}'
