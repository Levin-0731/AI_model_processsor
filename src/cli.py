#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 AI 批处理引擎 命令行入口。

子命令:
    run             按 config 执行批处理 (支持 --dry-run)
    test            单条/单图快速验证
    status          查看处理进度 (表格任务)
    list-providers  列出运营商及密钥状态
    reset           清空表格任务的结果列

示例:
    python src/cli.py run --config config/config.yaml
    python src/cli.py run --config config/examples/image2image.yaml --dry-run
    python src/cli.py list-providers
"""

import argparse
import os
import sys

# 让 src/ 下的包 (core/providers/tasks/dataio) 可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config, load_providers, resolve_provider  # noqa: E402
from core.engine import Engine  # noqa: E402


DEFAULT_CONFIG = "config/config.yaml"
DEFAULT_PROVIDERS = "config/providers.yaml"


def cmd_run(args):
    config = load_config(args.config)
    if args.provider:
        config.provider = args.provider
    if args.model:
        config.model = args.model
    if args.task:
        config.task = args.task
    if args.workers:
        config.runtime["max_workers"] = args.workers
    Engine(config, args.providers, dry_run=args.dry_run).run()


def cmd_test(args):
    """单条测试: 用 config 的 provider/task, 但只处理一个输入。"""
    from core.types import ImageRef, TaskInput
    from core.registry import get_provider_class, get_task_class, validate_capability

    config = load_config(args.config)
    if args.provider:
        config.provider = args.provider
    if args.model:
        config.model = args.model
    if args.task:
        config.task = args.task

    providers_doc = load_providers(args.providers)
    provider_cfg = resolve_provider(config.provider, providers_doc)
    api_type = provider_cfg.get("api_type", "openai")
    validate_capability(api_type, config.task)

    provider = get_provider_class(api_type)(provider_cfg)
    task = get_task_class(config.task)()

    text = args.prompt or config.resolve_prompt()
    images = []
    if args.image:
        from dataio.sources import file_to_data_uri
        images = [ImageRef(data_uri=file_to_data_uri(args.image))]

    ti = TaskInput(text=text, images=images)
    print(f"运营商={config.provider}({api_type}) 模型={config.model} 任务={config.task}")
    out = provider.invoke(config.model, config.resolve_prompt(), ti, config.params, dry_run=args.dry_run)
    out = task.postprocess(out)
    if out.text:
        print("文本输出:\n" + out.text)
    if out.image_bytes:
        dest = args.out or "test_output.jpg"
        with open(dest, "wb") as f:
            f.write(out.image_bytes[0])
        print(f"图片已保存: {dest}")
    if args.dry_run:
        print("请求体:", out.raw.get("request"))


def cmd_list_providers(args):
    doc = load_providers(args.providers)
    providers = doc.get("providers", {})
    print("可用运营商:")
    for name, cfg in providers.items():
        env_key = cfg.get("env_key") or f"{name.upper()}_API_KEY"
        has_key = bool(cfg.get("api_key")) or bool(os.environ.get(env_key))
        mark = "OK" if has_key else "--"
        api_type = cfg.get("api_type", "?")
        print(f"  [{mark}] {name:12s} api_type={api_type:10s} 密钥={'有' if has_key else '无(设 ' + env_key + ')'}")


def cmd_status(args):
    config = load_config(args.config)
    if config.output.get("type") != "table":
        print("status 仅适用于表格类任务 (output.type=table)")
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dataio.sources import build_source
    source = build_source(config.input, config.resolve_prompt(), config.output)
    items = source.load()
    safe = config.model.replace("-", "_").replace(".", "_").replace("/", "_")
    col = f"ai_response_{safe}"
    df = source.df
    total = len(df)
    done = 0
    if col in df.columns:
        done = int(df[col].apply(lambda v: not source.pd.isna(v) and str(v).strip() != "").sum())
    print(f"文件: {config.input.get('path')}")
    print(f"模型: {config.model} | 总计 {total} | 已处理 {done} | 待处理 {total - done}")


def cmd_reset(args):
    config = load_config(args.config)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dataio.sources import build_source
    from dataio.sinks import TableSink
    source = build_source(config.input, config.resolve_prompt(), config.output)
    source.load()
    sink = TableSink(source, source.path, config.model)
    source.df[sink.col] = ""
    sink.finalize()
    print(f"已清空结果列: {sink.col}")


def build_parser():
    p = argparse.ArgumentParser(description="统一 AI 批处理引擎")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--config", default=DEFAULT_CONFIG)
        sp.add_argument("--providers", default=DEFAULT_PROVIDERS)
        sp.add_argument("--provider", default=None)
        sp.add_argument("--model", default=None)
        sp.add_argument("--task", default=None)

    sp_run = sub.add_parser("run", help="批处理")
    add_common(sp_run)
    sp_run.add_argument("--workers", type=int, default=None)
    sp_run.add_argument("--dry-run", action="store_true")
    sp_run.set_defaults(func=cmd_run)

    sp_test = sub.add_parser("test", help="单条测试")
    add_common(sp_test)
    sp_test.add_argument("--prompt", default=None)
    sp_test.add_argument("--image", default=None)
    sp_test.add_argument("--out", default=None)
    sp_test.add_argument("--dry-run", action="store_true")
    sp_test.set_defaults(func=cmd_test)

    sp_list = sub.add_parser("list-providers", help="列出运营商")
    sp_list.add_argument("--providers", default=DEFAULT_PROVIDERS)
    sp_list.set_defaults(func=cmd_list_providers)

    sp_status = sub.add_parser("status", help="查看进度")
    add_common(sp_status)
    sp_status.set_defaults(func=cmd_status)

    sp_reset = sub.add_parser("reset", help="清空结果列")
    add_common(sp_reset)
    sp_reset.set_defaults(func=cmd_reset)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
