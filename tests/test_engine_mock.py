"""用 mock 运营商做 image2image 端到端测试 (离线, 临时目录)。"""

import os

import yaml

from core.config import load_config
from core.engine import Engine


_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000100ffff00000005000100c2b7e4d4"
    "0000000049454e44ae426082"
)

_PROVIDERS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "providers.yaml",
)


def _make_cfg(tmp_path, data):
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return load_config(str(p))


def test_image2image_end_to_end_with_mock(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    for i in range(3):
        (in_dir / f"{i+1}.png").write_bytes(_PNG)

    cfg = _make_cfg(tmp_path, {
        "provider": "mock", "model": "mock-any", "task": "image2image",
        "input": {"type": "folder", "path": str(in_dir)},
        "output": {"type": "image", "path": str(out_dir), "format": "jpg"},
        "prompt": {"inline": "test"},
        "runtime": {"max_workers": 2, "request_delay": 0},
    })
    Engine(cfg, _PROVIDERS).run()

    produced = sorted(os.listdir(out_dir))
    assert produced == ["1.jpg", "2.jpg", "3.jpg"]
    for fn in produced:
        assert (out_dir / fn).stat().st_size > 0


def test_resume_skips_existing(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    (in_dir / "1.png").write_bytes(_PNG)
    (out_dir / "1.jpg").write_bytes(b"already")

    cfg = _make_cfg(tmp_path, {
        "provider": "mock", "model": "mock-any", "task": "image2image",
        "input": {"type": "folder", "path": str(in_dir)},
        "output": {"type": "image", "path": str(out_dir), "format": "jpg"},
        "prompt": {"inline": "t"}, "runtime": {"request_delay": 0},
    })
    Engine(cfg, _PROVIDERS).run()

    assert (out_dir / "1.jpg").read_bytes() == b"already"
