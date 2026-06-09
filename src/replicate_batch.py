#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量调用 Replicate 平台的 nano-banana-2 (Banana2) 图生图接口。

功能:
- 读取输入文件夹中的所有图片
- 对每张图片应用同一段 prompt, 调用 Replicate 生成新图
- 自动轮询异步任务直到完成, 下载结果图到输出文件夹
- 断点续传: 结果图已存在则跳过
- 多线程并发

用法:
    export REPLICATE_API_TOKEN="r8_xxx"
    python src/replicate_batch.py
    python src/replicate_batch.py --input 原图 --output 结果图 --workers 3 --limit 1
"""

import os
import sys
import base64
import time
import mimetypes
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


MODEL = "google/nano-banana-2"
CREATE_URL = f"https://api.replicate.com/v1/models/{MODEL}/predictions"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def log(msg: str):
    print(msg, flush=True)


def image_to_data_uri(path: str) -> str:
    """把本地图片读成 data URI (base64 内联), 供 Replicate image_input 使用"""
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def build_input(prompt, image_uri, resolution, aspect_ratio, output_format):
    return {
        "prompt": prompt,
        "resolution": resolution,
        "image_input": [image_uri],
        "aspect_ratio": aspect_ratio,
        "image_search": False,
        "google_search": False,
        "output_format": output_format,
    }


def create_prediction(token, payload, timeout=120):
    """创建预测任务。用 Prefer: wait 让接口尽量同步返回结果, 减少轮询。"""
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
        "Prefer": "wait=60",
    }
    resp = requests.post(CREATE_URL, headers=headers, json={"input": payload}, timeout=timeout)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"创建任务失败 HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def poll_prediction(token, get_url, poll_interval=2.0, max_wait=600.0):
    """轮询任务直到 succeeded / failed / canceled。"""
    headers = {"Authorization": f"Token {token}"}
    start = time.time()
    while True:
        resp = requests.get(get_url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status in ("succeeded", "failed", "canceled"):
            return data
        if time.time() - start > max_wait:
            raise TimeoutError(f"任务超时 (>{max_wait}s), 最后状态: {status}")
        time.sleep(poll_interval)


def extract_output_url(data):
    """从结果中取出图片 URL。output 可能是字符串或列表。"""
    output = data.get("output")
    if not output:
        return None
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        return output[0]
    return None


def download(url, dest, token):
    headers = {}
    if "api.replicate.com" in url:
        headers["Authorization"] = f"Token {token}"
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


def process_one(token, img_path, out_path, prompt, resolution, aspect_ratio, output_format):
    """处理单张图片, 返回状态描述。"""
    name = os.path.basename(img_path)
    try:
        image_uri = image_to_data_uri(img_path)
        payload = build_input(prompt, image_uri, resolution, aspect_ratio, output_format)

        created = create_prediction(token, payload)
        status = created.get("status")

        if status not in ("succeeded", "failed", "canceled"):
            get_url = created.get("urls", {}).get("get")
            if not get_url:
                return f"\u274c {name}: \u65e0\u6cd5\u83b7\u53d6\u8f6e\u8be2\u5730\u5740"
            created = poll_prediction(token, get_url)
            status = created.get("status")

        if status != "succeeded":
            err = created.get("error") or status
            return f"\u274c {name}: \u4efb\u52a1\u672a\u6210\u529f ({err})"

        out_url = extract_output_url(created)
        if not out_url:
            return f"\u274c {name}: \u6210\u529f\u4f46\u672a\u8fd4\u56de\u56fe\u7247 URL"

        download(out_url, out_path, token)
        return f"\u2705 {name} -> {os.path.basename(out_path)}"

    except Exception as e:
        return f"\u274c {name}: {str(e)[:200]}"


def main():
    parser = argparse.ArgumentParser(description="Replicate nano-banana-2 批量图生图")
    parser.add_argument("--input", default="原图", help="输入图片文件夹")
    parser.add_argument("--output", default="结果图", help="输出文件夹")
    parser.add_argument("--prompt-file", default="prompts/banana_prompt.txt", help="prompt 文本文件")
    parser.add_argument("--prompt", default=None, help="直接指定 prompt(优先于 --prompt-file)")
    parser.add_argument("--resolution", default="1K", help="分辨率, 如 1K/2K/4K")
    parser.add_argument("--aspect-ratio", default="match_input_image", help="宽高比")
    parser.add_argument("--output-format", default="jpg", help="输出格式 jpg/png")
    parser.add_argument("--workers", type=int, default=3, help="并发线程数")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 张(0=全部), 便于先测试")
    args = parser.parse_args()

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        log("\u274c 未设置环境变量 REPLICATE_API_TOKEN")
        log('   请先运行:  export REPLICATE_API_TOKEN="r8_你的token"')
        sys.exit(1)

    if args.prompt is not None:
        prompt = args.prompt
    else:
        if not os.path.exists(args.prompt_file):
            log(f"\u274c prompt 文件不存在: {args.prompt_file}")
            sys.exit(1)
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    if not prompt:
        log("\u274c prompt 为空, 请在 prompts/banana_prompt.txt 写入内容, 或用 --prompt 指定")
        sys.exit(1)

    if not os.path.isdir(args.input):
        log(f"\u274c 输入文件夹不存在: {args.input}")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    files = [f for f in os.listdir(args.input)
             if os.path.splitext(f)[1].lower() in IMAGE_EXTS]

    def sort_key(fn):
        stem = os.path.splitext(fn)[0]
        return (0, int(stem)) if stem.isdigit() else (1, fn)

    files.sort(key=sort_key)

    if args.limit > 0:
        files = files[:args.limit]

    out_ext = "." + args.output_format.lstrip(".")

    tasks = []
    skipped = 0
    for fn in files:
        stem = os.path.splitext(fn)[0]
        out_path = os.path.join(args.output, stem + out_ext)
        if os.path.exists(out_path):
            skipped += 1
            continue
        tasks.append((os.path.join(args.input, fn), out_path))

    log(f"\U0001f4c1 输入: {args.input}  |  输出: {args.output}")
    log(f"\U0001f916 模型: {MODEL}  |  分辨率: {args.resolution}  |  比例: {args.aspect_ratio}")
    log(f"\U0001f4dd prompt: {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
    log(f"\U0001f5bc\ufe0f 共 {len(files)} 张, 已完成跳过 {skipped} 张, 待处理 {len(tasks)} 张, 并发 {args.workers}")
    log("\u2500" * 50)

    if not tasks:
        log("\u2705 没有需要处理的图片")
        return

    done = 0
    failed = 0
    total = len(tasks)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(process_one, token, ip, op, prompt,
                      args.resolution, args.aspect_ratio, args.output_format): ip
            for ip, op in tasks
        }
        for fut in as_completed(futures):
            result = fut.result()
            done += 1
            if result.startswith("\u274c"):
                failed += 1
            log(f"[{done}/{total}] {result}")

    log("\u2500" * 50)
    log(f"\U0001f389 完成! 成功 {done - failed} 张, 失败 {failed} 张, 结果在 {args.output}/")


if __name__ == "__main__":
    main()
