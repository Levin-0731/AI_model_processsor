#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI模型调用脚本
支持断点续传、进度显示和配置化管理
支持文本和图片输入（兼容视觉模型）
"""

import pandas as pd
import requests
import json
import time
import os
import sys
import base64
import mimetypes
from typing import Dict, Any, Optional, Tuple, List, Union
from tqdm import tqdm
import argparse
import logging
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

class AIModelProcessor:
    def __init__(self, config_file: str = "config.json"):
        """初始化AI模型处理器"""
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.csv_lock = Lock()  # CSV文件写入锁
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "api_url": "https://api.moonshot.cn/v1/chat/completions",
            "api_key": "sk-your-api-key-here",  # 请替换为您的实际API密钥
            "model_name": "kimi-k2-0905-preview",
            "temperature": 0.6,
            "max_tokens": 2000,
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1,
            "csv_input_file": "sample_data.csv",
            "prompt_file": "system_prompt.md",
            "user_prompt_column": "user_prompt",
            "image_column": "",  # 图片路径列名（可选，为空则不使用图片）
            "image_base_path": "",  # 图片基础路径（可选，用于拼接相对路径）
            "max_workers": 3,  # 并发线程数
            "request_delay": 0.5  # 请求间隔（秒）
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        else:
            # 创建默认配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"📝 已创建默认配置文件: {config_file}")
            print("⚠️  请修改配置文件中的API密钥等参数后重新运行")
            
        return default_config
    
    def setup_logging(self):
        """设置日志"""
        # 文件日志 - 详细信息
        file_handler = logging.FileHandler('ai_processor.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # 控制台日志 - 简化输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 禁用其他库的日志输出
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
    
    def load_system_prompt(self) -> str:
        """加载系统提示词"""
        prompt_file = self.config["prompt_file"]
        if not os.path.exists(prompt_file):
            self.logger.error(f"❌ 提示词文件不存在: {prompt_file}")
            return ""
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 如果文件包含 system_prompt = """...""" 格式，提取其中的内容
        if 'system_prompt = """' in content:
            start = content.find('system_prompt = """') + len('system_prompt = """')
            end = content.rfind('"""')
            if end > start:
                content = content[start:end]
        
        return content.strip()
    
    def check_row_processed(self, df: pd.DataFrame, index: int, reasoning_col: str, classification_col: str) -> bool:
        """检查指定行是否已经处理过"""
        if reasoning_col not in df.columns or classification_col not in df.columns:
            return False
        
        reasoning = df.at[index, reasoning_col]
        classification = df.at[index, classification_col]
        
        return (not pd.isna(reasoning) and str(reasoning).strip() != "" and
                not pd.isna(classification) and str(classification).strip() != "")
    
    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """将本地图片转换为Base64编码的data URL"""
        if not os.path.exists(image_path):
            self.logger.error(f"❌ 图片不存在: {image_path}")
            return None
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(image_path)
        supported_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        
        if mime_type not in supported_types:
            self.logger.error(f"❌ 不支持的图片格式: {mime_type} (支持: {', '.join(supported_types)})")
            return None
        
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            self.logger.error(f"❌ 读取图片失败: {str(e)}")
            return None
    
    def build_user_message(self, text: str, image_path: str = None) -> Union[str, List]:
        """
        构建用户消息（支持文本和图片）
        
        Args:
            text: 文本提示词
            image_path: 图片路径（可选）
        
        Returns:
            纯文本模式返回字符串，图片模式返回列表
        """
        # 纯文本模式
        if not image_path:
            return text
        
        # 处理图片路径
        image_base_path = self.config.get("image_base_path", "")
        if image_base_path and not os.path.isabs(image_path):
            image_path = os.path.join(image_base_path, image_path)
        
        # 编码图片
        image_url = self.encode_image_to_base64(image_path)
        if not image_url:
            # 图片处理失败，降级为纯文本
            self.logger.warning(f"⚠️ 图片处理失败，降级为纯文本模式")
            return text
        
        # 构建多模态消息
        content = []
        
        # 添加文本部分（如果有）
        if text and text.strip():
            content.append({"type": "text", "text": text})
        
        # 添加图片部分
        content.append({
            "type": "image_url",
            "image_url": {
                "url": image_url,
                "detail": self.config.get("image_detail", "auto")
            }
        })
        
        return content
    
    def call_ai_api(self, user_prompt: str, system_prompt: str, image_path: str = None) -> Optional[Dict[str, Any]]:
        """
        调用AI API（支持文本和图片）
        
        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词
            image_path: 图片路径（可选）
        
        Returns:
            解析后的响应字典，失败返回None
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        # 构建用户消息（支持图片）
        user_content = self.build_user_message(user_prompt, image_path)
        
        data = {
            "model": self.config["model_name"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": self.config["temperature"]
        }
        
        if "max_tokens" in self.config:
            data["max_tokens"] = self.config["max_tokens"]
        
        for attempt in range(self.config["max_retries"]):
            try:
                response = requests.post(
                    self.config["api_url"],
                    headers=headers,
                    json=data,
                    timeout=self.config["timeout"]
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"]
                        return self.parse_ai_response(content)
                    else:
                        self.logger.error(f"❌ API返回格式错误")
                else:
                    self.logger.error(f"❌ API调用失败 (状态码: {response.status_code})")
                
            except requests.exceptions.RequestException as e:
                if attempt == self.config["max_retries"] - 1:
                    self.logger.error(f"❌ API调用失败: {str(e)[:50]}...")
                if attempt < self.config["max_retries"] - 1:
                    time.sleep(self.config["retry_delay"] * (attempt + 1))
        
        return None
    
    def parse_ai_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析AI返回的JSON内容"""
        try:
            # 尝试直接解析JSON
            if content.strip().startswith('{') and content.strip().endswith('}'):
                return json.loads(content)
            
            # 如果内容包含在代码块中，提取JSON部分
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                if end > start:
                    json_content = content[start:end].strip()
                    return json.loads(json_content)
            
            # 尝试找到JSON对象
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                json_content = content[start:end]
                return json.loads(json_content)
            
            self.logger.error(f"❌ 无法解析AI响应为JSON")
            return None
            
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON解析错误: {str(e)[:30]}...")
            return None
    
    def process_single_row(self, index: int, user_prompt: str, system_prompt: str, 
                          df: pd.DataFrame, reasoning_col: str, classification_col: str,
                          image_path: str = None) -> bool:
        """
        处理单行数据（线程安全）
        
        Args:
            index: 行索引
            user_prompt: 用户提示词
            system_prompt: 系统提示词
            df: DataFrame
            reasoning_col: 推理结果列名
            classification_col: 分类结果列名
            image_path: 图片路径（可选）
        
        Returns:
            处理是否成功
        """
        try:
            # 添加请求延迟避免API限制
            time.sleep(self.config.get("request_delay", 0.5))
            
            # 调用AI API（支持图片）
            result = self.call_ai_api(user_prompt, system_prompt, image_path)
            
            if result:
                reasoning = result.get("Thoughts", "")
                classification = result.get("Category", "")
                
                # 线程安全地更新DataFrame
                with self.csv_lock:
                    df.at[index, reasoning_col] = reasoning
                    df.at[index, classification_col] = classification
                
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def process_csv(self) -> bool:
        """处理CSV文件（支持文本和图片输入）"""
        csv_file = self.config["csv_input_file"]
        
        if not os.path.exists(csv_file):
            self.logger.error(f"❌ CSV文件不存在: {csv_file}")
            return False
        
        # 读取CSV文件
        df = pd.read_csv(csv_file)
        user_prompt_col = self.config["user_prompt_column"]
        
        if user_prompt_col not in df.columns:
            self.logger.error(f"❌ CSV文件中不存在列: {user_prompt_col}")
            return False
        
        # 检查图片列配置
        image_col = self.config.get("image_column", "")
        has_image_col = image_col and image_col in df.columns
        
        if image_col and image_col not in df.columns:
            self.logger.warning(f"⚠️ 配置的图片列 '{image_col}' 不存在，将使用纯文本模式")
            has_image_col = False
        
        if has_image_col:
            self.logger.info(f"🖼️ 已启用图片模式，图片列: {image_col}")
        
        # 加载系统提示词
        system_prompt = self.load_system_prompt()
        if not system_prompt:
            self.logger.error("❌ 无法加载系统提示词")
            return False
        
        # 创建结果列
        model_name = self.config["model_name"].replace("-", "_")
        reasoning_col = f"reasoning_{model_name}"
        classification_col = f"classification_{model_name}"
        
        if reasoning_col not in df.columns:
            df[reasoning_col] = ""
        if classification_col not in df.columns:
            df[classification_col] = ""
        
        # 扫描CSV文件，收集需要处理的行
        total_rows = len(df)
        rows_to_process = []
        processed_count = 0
        
        self.logger.info(f"📊 扫描CSV文件，检查处理状态...")
        
        for index, row in df.iterrows():
            # 检查是否已经处理过
            if self.check_row_processed(df, index, reasoning_col, classification_col):
                processed_count += 1
                continue
            
            user_prompt = str(row[user_prompt_col])
            
            # 获取图片路径（如果有）
            image_path = None
            if has_image_col:
                img = row.get(image_col, "")
                if pd.notna(img) and str(img).strip():
                    image_path = str(img).strip()
            
            rows_to_process.append((index, user_prompt, image_path))
        
        self.logger.info(f"📈 扫描完成: 总计 {total_rows} 行，已处理 {processed_count} 行，待处理 {len(rows_to_process)} 行")
        
        if not rows_to_process:
            self.logger.info("✅ 所有数据已处理完成")
            return True
        
        self.logger.info(f"🚀 开始处理 {len(rows_to_process)} 条数据 (线程数: {self.config['max_workers']})")
        
        # 多线程处理
        new_processed_count = 0
        max_workers = self.config.get("max_workers", 3)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            with tqdm(total=len(rows_to_process), desc="📊 处理进度", 
                     bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                     ncols=80) as pbar:
                # 提交所有任务
                future_to_index = {}
                for index, user_prompt, image_path in rows_to_process:
                    future = executor.submit(
                        self.process_single_row, 
                        index, user_prompt, system_prompt, 
                        df, reasoning_col, classification_col,
                        image_path
                    )
                    future_to_index[future] = index
                
                # 处理完成的任务
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        success = future.result()
                        if success:
                            new_processed_count += 1
                        
                        # 定期保存CSV文件（线程安全）
                        if new_processed_count % 10 == 0:
                            with self.csv_lock:
                                df.to_csv(csv_file, index=False)
                                
                        pbar.update(1)
                        
                    except Exception as e:
                        pbar.update(1)
        
        # 最终保存
        with self.csv_lock:
            df.to_csv(csv_file, index=False)
        
        self.logger.info(f"🎉 处理完成！共处理 {new_processed_count} 条新数据")
        return True
    
    def reset_progress(self):
        """重置进度 - 清空CSV文件中的处理结果列"""
        csv_file = self.config["csv_input_file"]
        if not os.path.exists(csv_file):
            self.logger.error(f"❌ CSV文件不存在: {csv_file}")
            return
        
        df = pd.read_csv(csv_file)
        model_name = self.config["model_name"].replace("-", "_")
        reasoning_col = f"reasoning_{model_name}"
        classification_col = f"classification_{model_name}"
        
        # 清空结果列
        if reasoning_col in df.columns:
            df[reasoning_col] = ""
        if classification_col in df.columns:
            df[classification_col] = ""
        
        df.to_csv(csv_file, index=False)
        self.logger.info("🔄 进度已重置，已清空所有处理结果")
    
    def show_status(self):
        """显示当前状态"""
        csv_file = self.config["csv_input_file"]
        if not os.path.exists(csv_file):
            print(f"❌ CSV文件不存在: {csv_file}")
            return
        
        df = pd.read_csv(csv_file)
        model_name = self.config["model_name"].replace("-", "_")
        reasoning_col = f"reasoning_{model_name}"
        classification_col = f"classification_{model_name}"
        
        total_rows = len(df)
        processed_rows = 0
        
        # 使用新的检查方法
        for index in range(total_rows):
            if self.check_row_processed(df, index, reasoning_col, classification_col):
                processed_rows += 1
        
        progress_pct = processed_rows/total_rows*100 if total_rows > 0 else 0
        remaining = total_rows - processed_rows
        
        print(f"\n📊 处理状态")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📝 总行数:     {total_rows:,}")
        print(f"✅ 已处理:     {processed_rows:,}")
        print(f"⏳ 待处理:     {remaining:,}")
        print(f"📈 完成率:     {progress_pct:.1f}%")
        print(f"🔧 线程数:     {self.config.get('max_workers', 3)}")
        
        # 进度条
        bar_length = 30
        filled_length = int(bar_length * progress_pct / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        print(f"📊 进度条:     [{bar}] {progress_pct:.1f}%")
        
        # 预估剩余时间
        if processed_rows > 0 and remaining > 0:
            avg_time_per_item = 3.0 / self.config.get('max_workers', 3)
            estimated_hours = (remaining * avg_time_per_item) / 3600
            if estimated_hours < 1:
                estimated_minutes = (remaining * avg_time_per_item) / 60
                print(f"⏰ 预估时间:   {estimated_minutes:.0f} 分钟")
            else:
                print(f"⏰ 预估时间:   {estimated_hours:.1f} 小时")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


def main():
    parser = argparse.ArgumentParser(description='AI模型调用脚本')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    parser.add_argument('--reset', action='store_true', help='重置进度')
    parser.add_argument('--status', action='store_true', help='显示状态')
    parser.add_argument('--workers', type=int, help='并发线程数量 (覆盖配置文件设置)')
    
    args = parser.parse_args()
    
    processor = AIModelProcessor(args.config)
    
    # 命令行参数覆盖配置文件设置
    if args.workers is not None:
        processor.config["max_workers"] = args.workers
        print(f"🔧 使用命令行指定的线程数: {args.workers}")
    
    if args.reset:
        processor.reset_progress()
        return
    
    if args.status:
        processor.show_status()
        return
    
    # 检查API密钥
    if processor.config["api_key"] == "sk-your-api-key-here":
        print("⚠️  请在配置文件中设置正确的API密钥")
        return
    
    processor.process_csv()


if __name__ == "__main__":
    main()
