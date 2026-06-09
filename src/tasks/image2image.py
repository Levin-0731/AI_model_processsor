#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图生图: 图片 (通常配合 prompt) 输入, 图片输出。

典型场景: Replicate nano-banana-2 按 prompt 改写每张原图。
"""

from tasks.base import TaskMode


class Image2Image(TaskMode):
    name = "image2image"
    required_input = {"image"}
    output_type = "image"
