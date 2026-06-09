#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ProviderAdapter 抽象基类。

子类只需实现 `invoke`: 输入统一的 (model, system_prompt, TaskInput, params),
返回统一的 TaskOutput。引擎与任务模式对具体平台零感知。

约定:
- `capabilities`: 声明该平台支持的任务集合, 供能力矩阵校验。
- `is_async`: 是否异步 (需要轮询)。轮询逻辑应封装在子类 invoke 内部,
  对外表现为同步。
"""

from typing import Any, Dict, Optional, Set

from core.types import TaskInput, TaskOutput


class ProviderAdapter:
    capabilities: Set[str] = set()
    is_async: bool = False

    def __init__(self, provider_config: Dict[str, Any]):
        self.cfg = provider_config

    def invoke(
        self,
        model: str,
        system_prompt: Optional[str],
        task_input: TaskInput,
        params: Dict[str, Any],
        dry_run: bool = False,
    ) -> TaskOutput:
        raise NotImplementedError

    # --- 共用小工具 ---

    def _retry_params(self):
        return (
            int(self.cfg.get("max_retries", 3)),
            float(self.cfg.get("retry_delay", 2)),
            int(self.cfg.get("timeout", 60)),
        )
