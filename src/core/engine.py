#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行引擎。

职责 (横切能力, 与具体平台/任务无关):
- 组装 provider / task / source / sink
- 校验 provider x task 能力 与 task 输入需求
- 并发执行 + 断点续传 + 进度展示 + 请求限速 + 日志

引擎只通过统一接口与各层交互。
"""

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from core.config import AppConfig, load_providers, resolve_provider
from core.registry import get_provider_class, get_task_class, validate_capability
from core.types import WorkItem, WorkResult
from dataio.sinks import build_sink
from dataio.sources import build_source

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class Engine:
    def __init__(self, config: AppConfig, providers_path: str, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.logger = self._setup_logging()

        providers_doc = load_providers(providers_path)
        self.provider_cfg = resolve_provider(config.provider, providers_doc)
        # 把运行期轮询参数透传给适配器
        self.provider_cfg.setdefault("poll_interval", config.runtime_get("poll_interval"))
        self.provider_cfg.setdefault("poll_timeout", config.runtime_get("poll_timeout"))
        self.provider_cfg.setdefault("max_retries", config.runtime_get("max_retries"))
        self.provider_cfg.setdefault("retry_delay", config.runtime_get("retry_delay"))

        self.api_type = self.provider_cfg.get("api_type", "openai")
        validate_capability(self.api_type, config.task)

        self.provider = get_provider_class(self.api_type)(self.provider_cfg)
        self.task = get_task_class(config.task)()

        self.system_prompt = config.resolve_prompt()
        self.prompt_text = self.system_prompt  # folder 源把 prompt 作为每张图的文本

    @staticmethod
    def _setup_logging():
        logger = logging.getLogger("aibatch")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            fh = logging.FileHandler("ai_processor.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(fh)
            logger.addHandler(ch)
        return logger

    def _validate_inputs(self, items: List[WorkItem]) -> None:
        """校验输入是否满足任务模式的 required_input。"""
        need = self.task.required_input
        if not items:
            return
        sample = items[0].task_input
        if "image" in need and not sample.images:
            raise ValueError(f"任务 '{self.task.name}' 需要图片输入, 但输入源未提供图片")
        if "text" in need and not (sample.text and sample.text.strip()):
            raise ValueError(f"任务 '{self.task.name}' 需要文本/prompt 输入, 但为空")

    def _process_one(self, item: WorkItem, sink) -> WorkResult:
        try:
            delay = float(self.config.runtime_get("request_delay", 0.5))
            if delay > 0:
                time.sleep(delay)
            output = self.provider.invoke(
                self.config.model, self.system_prompt,
                item.task_input, self.config.params, dry_run=self.dry_run,
            )
            output = self.task.postprocess(output)
            if self.dry_run:
                return WorkResult(item.key, True, "dry-run", output)
            sink.write(item, output)
            return WorkResult(item.key, True, "ok", output)
        except Exception as e:
            return WorkResult(item.key, False, str(e)[:200])

    def run(self) -> None:
        source = build_source(self.config.input, self.prompt_text, self.config.output)
        items = source.load()
        self._validate_inputs(items)

        sink = build_sink(self.config.output, source, self.config.model)

        # 断点续传: 过滤已完成
        pending = [it for it in items if self.dry_run or not sink.is_done(it)]
        skipped = len(items) - len(pending)

        self.logger.info(f"运营商: {self.config.provider} ({self.api_type}) | 模型: {self.config.model} | 任务: {self.config.task}")
        self.logger.info(f"输入: {self.config.input.get('type')} | 输出: {self.config.output.get('type')}")
        self.logger.info(f"共 {len(items)} 项, 跳过(已完成) {skipped} 项, 待处理 {len(pending)} 项")
        if self.dry_run:
            self.logger.info("[DRY-RUN] 只构建请求, 不真正调用 API")

        if not pending:
            self.logger.info("没有需要处理的项")
            return

        max_workers = int(self.config.runtime_get("max_workers", 3))
        done = failed = 0
        total = len(pending)
        save_lock_counter = 0

        progress = tqdm(total=total, ncols=80) if (HAS_TQDM and not self.dry_run) else None

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self._process_one, it, sink): it for it in pending}
            for fut in as_completed(futures):
                res = fut.result()
                done += 1
                if not res.success:
                    failed += 1
                    self.logger.info(f"[{done}/{total}] FAIL {res.key}: {res.message}")
                elif self.dry_run:
                    req = (res.output.raw or {}).get("request")
                    self.logger.info(f"[{done}/{total}] {res.key} -> {req}")
                else:
                    self.logger.info(f"[{done}/{total}] OK {res.key}")
                # 表格类边处理边定期落盘
                save_lock_counter += 1
                if not self.dry_run and getattr(sink, "output_type", "") == "table" and save_lock_counter % 10 == 0:
                    sink.finalize()
                if progress:
                    progress.update(1)

        if progress:
            progress.close()
        if not self.dry_run:
            sink.finalize()
        self.logger.info(f"完成! 成功 {done - failed}, 失败 {failed}")
