#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文生图: 文本输入, 图片输出。"""

from tasks.base import TaskMode


class Text2Image(TaskMode):
    name = "text2image"
    required_input = {"text"}
    output_type = "image"
