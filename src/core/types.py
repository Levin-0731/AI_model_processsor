#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一数据结构。

这一层是引擎、运营商适配器、任务模式之间的通用契约: 任何 provider 与
task 都只通过这些结构交互, 从而彻底解耦"用什么平台"和"做什么任务"。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImageRef:
    """对一张图片的统一引用, 三选一填充。

    - data_uri: data:image/xxx;base64,.... (内联, 最通用)
    - url: 远程可访问 URL
    - path: 本地文件路径
    """
    data_uri: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None

    def as_data_uri(self) -> Optional[str]:
        """尽力返回一个 data URI 或 URL 形式的字符串。"""
        if self.data_uri:
            return self.data_uri
        if self.url:
            return self.url
        return None


@dataclass
class TaskInput:
    """送入模型的统一输入。"""
    text: Optional[str] = None
    images: List[ImageRef] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskOutput:
    """模型返回的统一输出。

    - text: 文本结果 (文生文 / 图生文)
    - image_bytes: 已下载的图片字节 (文生图 / 图生图)
    - image_urls: 结果图片的远程 URL
    - raw: 平台原始响应, 便于调试与扩展
    """
    text: Optional[str] = None
    image_bytes: List[bytes] = field(default_factory=list)
    image_urls: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkItem:
    """一个待处理单元。"""
    key: str                      # 唯一标识 (表格行号 / 文件名 stem)
    task_input: TaskInput
    dest: str                     # 输出目标 (文件路径 或 表格列名)
    source_ref: Any = None        # 原始引用 (如 DataFrame index), 供写回使用


@dataclass
class WorkResult:
    """一个单元的处理结果。"""
    key: str
    success: bool
    message: str = ""
    output: Optional[TaskOutput] = None
