#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI模型调用脚本
支持断点续传、进度显示和配置化管理
支持文本和图片输入（兼容视觉模型）
支持多Provider和多种API调用方式
"""

import pandas as pd
import requests
import json
import yaml
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
    def __init__(self, config_file: str = "config.yaml", providers_file: str = "providers.yaml"):
        """初始化AI模型处理器"""
        self.config = self.load_config(config_file)
        self.providers = self.load_providers(providers_file)
        self.provider_config = self.get_provider_config()
        self.setup_logging()
        self.csv_lock = Lock()  # CSV文件写入锁
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """加载运行配置文件"""
        default_config = {
            "provider": "openai",
            "model_name": "gpt-4o",
            "temperature": 0.6,
            "max_tokens": 2000,
            "csv_input_file": "sample_data.csv",
            "prompt_file": "system_prompt.md",
            "user_prompt_column": "user_prompt",
            "image_column": "",
            "image_base_path": "",
            "image_detail": "auto",
            "max_workers": 3,
            "request_delay": 0.5
        }

        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
        else:
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
            print(f"📝 已创建默认配置文件: {config_file}")

        return default_config
    
    def load_providers(self, providers_file: str) -> Dict[str, Any]:
        """加载Provider配置文件"""
        default_providers = {
            "providers": {
                "openai": {
                    "api_url": "https://api.openai.com/v1/chat/completions",
                    "api_key": "",
                    "api_type": "openai",
                    "timeout": 60,
                    "max_retries": 3,
                    "retry_delay": 2
                }
            },
            "default_provider": "openai"
        }

        if os.path.exists(providers_file):
            with open(providers_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            with open(providers_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_providers, f, allow_unicode=True, default_flow_style=False)
            print(f"📝 已创建默认Provider配置文件: {providers_file}")
            return default_providers
    
    def get_provider_config(self) -> Dict[str, Any]:
        """获取当前Provider的配置"""
        provider_name = self.config.get("provider", self.providers.get("default_provider", "openai"))
        providers = self.providers.get("providers", {})
        
        if provider_name not in providers:
            print(f"❌ Provider '{provider_name}' 不存在于 providers.yaml")
            print(f"可用的Provider: {', '.join(providers.keys())}")
            sys.exit(1)
        
        return providers[provider_name]
    
    def setup_logging(self):
        """设置日志"""
        file_handler = logging.FileHandler('ai_processor.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        # 避免重复添加handler
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
        
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
        
        mime_type, _ = mimetypes.guess_type(image_path)
        supported_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        
        if mime_type not in supported_types:
            self.logger.error(f"❌ 不支持的图片格式: {mime_type}")
            return None
        
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            self.logger.error(f"❌ 读取图片失败: {str(e)}")
            return None
    
    def get_image_base64_raw(self, image_path: str) -> Optional[Tuple[str, str]]:
        """获取图片的原始Base64数据和MIME类型"""
        if not os.path.exists(image_path):
            return None
        
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            return None
        
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            return image_data, mime_type
        except:
            return None
    
    def build_user_message_openai(self, text: str, image_path: str = None) -> Union[str, List]:
        """构建OpenAI格式的用户消息"""
        if not image_path:
            return text
        
        image_base_path = self.config.get("image_base_path", "")
        if image_base_path and not os.path.isabs(image_path):
            image_path = os.path.join(image_base_path, image_path)
        
        image_url = self.encode_image_to_base64(image_path)
        if not image_url:
            return text
        
        content = []
        if text and text.strip():
            content.append({"type": "text", "text": text})
        
        content.append({
            "type": "image_url",
            "image_url": {
                "url": image_url,
                "detail": self.config.get("image_detail", "auto")
            }
        })
        
        return content
    
    def build_user_message_anthropic(self, text: str, image_path: str = None) -> List:
        """构建Anthropic格式的用户消息"""
        content = []
        
        if image_path:
            image_base_path = self.config.get("image_base_path", "")
            if image_base_path and not os.path.isabs(image_path):
                image_path = os.path.join(image_base_path, image_path)
            
            result = self.get_image_base64_raw(image_path)
            if result:
                image_data, mime_type = result
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": image_data
                    }
                })
        
        if text and text.strip():
            content.append({"type": "text", "text": text})
        
        return content if content else [{"type": "text", "text": text or ""}]
    
    def call_api_openai(self, user_prompt: str, system_prompt: str, image_path: str = None) -> Optional[str]:
        """调用OpenAI兼容格式的API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.provider_config['api_key']}"
        }
        
        user_content = self.build_user_message_openai(user_prompt, image_path)
        
        data = {
            "model": self.config["model_name"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": self.config.get("temperature", 0.6)
        }
        
        if "max_tokens" in self.config:
            data["max_tokens"] = self.config["max_tokens"]
        
        max_retries = self.provider_config.get("max_retries", 3)
        retry_delay = self.provider_config.get("retry_delay", 1)
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.provider_config["api_url"],
                    headers=headers,
                    json=data,
                    timeout=self.provider_config.get("timeout", 60)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"]
                else:
                    self.logger.error(f"❌ API调用失败 (状态码: {response.status_code})")
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"❌ API调用失败: {str(e)[:50]}...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
        
        return None
    
    def call_api_anthropic(self, user_prompt: str, system_prompt: str, image_path: str = None) -> Optional[str]:
        """调用Anthropic Claude API"""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.provider_config['api_key'],
            "anthropic-version": self.provider_config.get("api_version", "2023-06-01")
        }
        
        user_content = self.build_user_message_anthropic(user_prompt, image_path)
        
        data = {
            "model": self.config["model_name"],
            "max_tokens": self.config.get("max_tokens", 4096),
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_content}
            ]
        }
        
        if "temperature" in self.config:
            data["temperature"] = self.config["temperature"]
        
        max_retries = self.provider_config.get("max_retries", 3)
        retry_delay = self.provider_config.get("retry_delay", 2)
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.provider_config["api_url"],
                    headers=headers,
                    json=data,
                    timeout=self.provider_config.get("timeout", 60)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "content" in result and len(result["content"]) > 0:
                        return result["content"][0]["text"]
                else:
                    self.logger.error(f"❌ API调用失败 (状态码: {response.status_code})")
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"❌ API调用失败: {str(e)[:50]}...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
        
        return None
    
    def call_api_google(self, user_prompt: str, system_prompt: str, image_path: str = None) -> Optional[str]:
        """调用Google Gemini API"""
        model_name = self.config["model_name"]
        api_key = self.provider_config['api_key']
        base_url = self.provider_config["api_url"]
        url = f"{base_url}/models/{model_name}:generateContent?key={api_key}"
        
        headers = {"Content-Type": "application/json"}
        
        # 构建内容
        parts = []
        
        # 添加系统提示词作为文本的一部分
        if system_prompt:
            parts.append({"text": f"System: {system_prompt}\n\nUser: {user_prompt}"})
        else:
            parts.append({"text": user_prompt})
        
        # 添加图片
        if image_path:
            image_base_path = self.config.get("image_base_path", "")
            if image_base_path and not os.path.isabs(image_path):
                image_path = os.path.join(image_base_path, image_path)
            
            result = self.get_image_base64_raw(image_path)
            if result:
                image_data, mime_type = result
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_data
                    }
                })
        
        data = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": self.config.get("temperature", 0.6),
                "maxOutputTokens": self.config.get("max_tokens", 2048)
            }
        }
        
        max_retries = self.provider_config.get("max_retries", 3)
        retry_delay = self.provider_config.get("retry_delay", 2)
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=self.provider_config.get("timeout", 60)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result and len(result["candidates"]) > 0:
                        candidate = result["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            return candidate["content"]["parts"][0]["text"]
                else:
                    self.logger.error(f"❌ API调用失败 (状态码: {response.status_code})")
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"❌ API调用失败: {str(e)[:50]}...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
        
        return None
    
    def call_ai_api(self, user_prompt: str, system_prompt: str, image_path: str = None) -> Optional[Dict[str, Any]]:
        """统一的API调用入口，根据api_type选择调用方式"""
        api_type = self.provider_config.get("api_type", "openai")
        
        if api_type == "openai":
            content = self.call_api_openai(user_prompt, system_prompt, image_path)
        elif api_type == "anthropic":
            content = self.call_api_anthropic(user_prompt, system_prompt, image_path)
        elif api_type == "google":
            content = self.call_api_google(user_prompt, system_prompt, image_path)
        else:
            self.logger.error(f"❌ 不支持的API类型: {api_type}")
            return None
        
        if content:
            return self.parse_ai_response(content)
        return None
    
    def parse_ai_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析AI返回的JSON内容"""
        try:
            if content.strip().startswith('{') and content.strip().endswith('}'):
                return json.loads(content)
            
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                if end > start:
                    json_content = content[start:end].strip()
                    return json.loads(json_content)
            
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
        """处理单行数据（线程安全）"""
        try:
            time.sleep(self.config.get("request_delay", 0.5))
            
            result = self.call_ai_api(user_prompt, system_prompt, image_path)
            
            if result:
                reasoning = result.get("Thoughts", "")
                classification = result.get("Category", "")
                
                with self.csv_lock:
                    df.at[index, reasoning_col] = reasoning
                    df.at[index, classification_col] = classification
                
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def process_csv(self) -> bool:
        """处理CSV文件"""
        csv_file = self.config["csv_input_file"]
        
        if not os.path.exists(csv_file):
            self.logger.error(f"❌ CSV文件不存在: {csv_file}")
            return False
        
        df = pd.read_csv(csv_file)
        user_prompt_col = self.config["user_prompt_column"]
        
        if user_prompt_col not in df.columns:
            self.logger.error(f"❌ CSV文件中不存在列: {user_prompt_col}")
            return False
        
        # 显示当前使用的Provider和模型
        provider_name = self.config.get("provider", "unknown")
        model_name = self.config.get("model_name", "unknown")
        api_type = self.provider_config.get("api_type", "unknown")
        self.logger.info(f"🤖 Provider: {provider_name} | 模型: {model_name} | API类型: {api_type}")
        
        image_col = self.config.get("image_column", "")
        has_image_col = image_col and image_col in df.columns
        
        if image_col and image_col not in df.columns:
            self.logger.warning(f"⚠️ 配置的图片列 '{image_col}' 不存在，将使用纯文本模式")
            has_image_col = False
        
        if has_image_col:
            self.logger.info(f"🖼️ 已启用图片模式，图片列: {image_col}")
        
        system_prompt = self.load_system_prompt()
        if not system_prompt:
            self.logger.error("❌ 无法加载系统提示词")
            return False
        
        model_name_safe = self.config["model_name"].replace("-", "_").replace(".", "_")
        reasoning_col = f"reasoning_{model_name_safe}"
        classification_col = f"classification_{model_name_safe}"
        
        if reasoning_col not in df.columns:
            df[reasoning_col] = ""
        if classification_col not in df.columns:
            df[classification_col] = ""
        
        total_rows = len(df)
        rows_to_process = []
        processed_count = 0
        
        self.logger.info(f"📊 扫描CSV文件，检查处理状态...")
        
        for index, row in df.iterrows():
            if self.check_row_processed(df, index, reasoning_col, classification_col):
                processed_count += 1
                continue
            
            user_prompt = str(row[user_prompt_col])
            
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
        
        new_processed_count = 0
        max_workers = self.config.get("max_workers", 3)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            with tqdm(total=len(rows_to_process), desc="📊 处理进度", 
                     bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                     ncols=80) as pbar:
                future_to_index = {}
                for index, user_prompt, image_path in rows_to_process:
                    future = executor.submit(
                        self.process_single_row, 
                        index, user_prompt, system_prompt, 
                        df, reasoning_col, classification_col,
                        image_path
                    )
                    future_to_index[future] = index
                
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        success = future.result()
                        if success:
                            new_processed_count += 1
                        
                        if new_processed_count % 10 == 0:
                            with self.csv_lock:
                                df.to_csv(csv_file, index=False)
                                
                        pbar.update(1)
                        
                    except Exception as e:
                        pbar.update(1)
        
        with self.csv_lock:
            df.to_csv(csv_file, index=False)
        
        self.logger.info(f"🎉 处理完成！共处理 {new_processed_count} 条新数据")
        return True
    
    def reset_progress(self):
        """重置进度"""
        csv_file = self.config["csv_input_file"]
        if not os.path.exists(csv_file):
            self.logger.error(f"❌ CSV文件不存在: {csv_file}")
            return
        
        df = pd.read_csv(csv_file)
        model_name_safe = self.config["model_name"].replace("-", "_").replace(".", "_")
        reasoning_col = f"reasoning_{model_name_safe}"
        classification_col = f"classification_{model_name_safe}"
        
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
        model_name_safe = self.config["model_name"].replace("-", "_").replace(".", "_")
        reasoning_col = f"reasoning_{model_name_safe}"
        classification_col = f"classification_{model_name_safe}"
        
        total_rows = len(df)
        processed_rows = 0
        
        for index in range(total_rows):
            if self.check_row_processed(df, index, reasoning_col, classification_col):
                processed_rows += 1
        
        progress_pct = processed_rows/total_rows*100 if total_rows > 0 else 0
        remaining = total_rows - processed_rows
        
        provider_name = self.config.get("provider", "unknown")
        model_name = self.config.get("model_name", "unknown")
        
        print(f"\n📊 处理状态")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"🤖 Provider:   {provider_name}")
        print(f"📦 模型:       {model_name}")
        print(f"📝 总行数:     {total_rows:,}")
        print(f"✅ 已处理:     {processed_rows:,}")
        print(f"⏳ 待处理:     {remaining:,}")
        print(f"📈 完成率:     {progress_pct:.1f}%")
        print(f"🔧 线程数:     {self.config.get('max_workers', 3)}")
        
        bar_length = 30
        filled_length = int(bar_length * progress_pct / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        print(f"📊 进度条:     [{bar}] {progress_pct:.1f}%")
        
        if processed_rows > 0 and remaining > 0:
            avg_time_per_item = 3.0 / self.config.get('max_workers', 3)
            estimated_hours = (remaining * avg_time_per_item) / 3600
            if estimated_hours < 1:
                estimated_minutes = (remaining * avg_time_per_item) / 60
                print(f"⏰ 预估时间:   {estimated_minutes:.0f} 分钟")
            else:
                print(f"⏰ 预估时间:   {estimated_hours:.1f} 小时")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    def list_providers(self):
        """列出所有可用的Provider"""
        providers = self.providers.get("providers", {})
        default_provider = self.providers.get("default_provider", "")
        
        print(f"\n📋 可用的Provider列表")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        for name, config in providers.items():
            is_default = " (默认)" if name == default_provider else ""
            api_type = config.get("api_type", "unknown")
            has_key = "✅" if config.get("api_key") else "❌"
            models = config.get("available_models", [])
            
            print(f"\n🔹 {name}{is_default}")
            print(f"   API类型: {api_type}")
            print(f"   密钥状态: {has_key}")
            print(f"   可用模型: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
        
        print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


def main():
    parser = argparse.ArgumentParser(description='AI模型调用脚本（支持多Provider）')
    parser.add_argument('--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('--providers', default='providers.yaml', help='Provider配置文件路径')
    parser.add_argument('--reset', action='store_true', help='重置进度')
    parser.add_argument('--status', action='store_true', help='显示状态')
    parser.add_argument('--list-providers', action='store_true', help='列出所有Provider')
    parser.add_argument('--workers', type=int, help='并发线程数量')
    parser.add_argument('--provider', type=str, help='指定使用的Provider')
    parser.add_argument('--model', type=str, help='指定使用的模型')
    
    args = parser.parse_args()
    
    processor = AIModelProcessor(args.config, args.providers)
    
    # 命令行参数覆盖
    if args.workers is not None:
        processor.config["max_workers"] = args.workers
        print(f"🔧 使用命令行指定的线程数: {args.workers}")
    
    if args.provider is not None:
        processor.config["provider"] = args.provider
        processor.provider_config = processor.get_provider_config()
        print(f"🔧 使用命令行指定的Provider: {args.provider}")
    
    if args.model is not None:
        processor.config["model_name"] = args.model
        print(f"🔧 使用命令行指定的模型: {args.model}")
    
    if args.list_providers:
        processor.list_providers()
        return
    
    if args.reset:
        processor.reset_progress()
        return
    
    if args.status:
        processor.show_status()
        return
    
    # 检查API密钥
    if not processor.provider_config.get("api_key"):
        provider_name = processor.config.get("provider", "unknown")
        print(f"⚠️  请在 providers.yaml 中为 '{provider_name}' 设置API密钥")
        return
    
    processor.process_csv()


if __name__ == "__main__":
    main()
