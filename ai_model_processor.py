#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI模型调用脚本
支持断点续传、进度显示和配置化管理
"""

import pandas as pd
import requests
import json
import time
import os
import sys
from typing import Dict, Any, Optional, Tuple
from tqdm import tqdm
import argparse
import logging
from datetime import datetime

class AIModelProcessor:
    def __init__(self, config_file: str = "config.json"):
        """初始化AI模型处理器"""
        self.config = self.load_config(config_file)
        self.setup_logging()
        
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
            "progress_file": "progress.json"
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        else:
            # 创建默认配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"已创建默认配置文件: {config_file}")
            print("请修改配置文件中的API密钥等参数后重新运行")
            
        return default_config
    
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ai_processor.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_system_prompt(self) -> str:
        """加载系统提示词"""
        prompt_file = self.config["prompt_file"]
        if not os.path.exists(prompt_file):
            self.logger.error(f"提示词文件不存在: {prompt_file}")
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
    
    def load_progress(self) -> Dict[str, Any]:
        """加载进度文件"""
        progress_file = self.config["progress_file"]
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"processed_rows": [], "last_processed_index": -1}
    
    def save_progress(self, progress: Dict[str, Any]):
        """保存进度文件"""
        progress_file = self.config["progress_file"]
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
    
    def call_ai_api(self, user_prompt: str, system_prompt: str) -> Optional[Dict[str, Any]]:
        """调用AI API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        data = {
            "model": self.config["model_name"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
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
                        self.logger.error(f"API返回格式错误: {result}")
                else:
                    self.logger.error(f"API调用失败 (状态码: {response.status_code}): {response.text}")
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"API调用异常 (尝试 {attempt + 1}/{self.config['max_retries']}): {e}")
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
            
            self.logger.error(f"无法解析AI响应为JSON: {content}")
            return None
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析错误: {e}, 内容: {content}")
            return None
    
    def process_csv(self) -> bool:
        """处理CSV文件"""
        csv_file = self.config["csv_input_file"]
        
        if not os.path.exists(csv_file):
            self.logger.error(f"CSV文件不存在: {csv_file}")
            return False
        
        # 读取CSV文件
        df = pd.read_csv(csv_file)
        user_prompt_col = self.config["user_prompt_column"]
        
        if user_prompt_col not in df.columns:
            self.logger.error(f"CSV文件中不存在列: {user_prompt_col}")
            return False
        
        # 加载系统提示词
        system_prompt = self.load_system_prompt()
        if not system_prompt:
            self.logger.error("无法加载系统提示词")
            return False
        
        # 加载进度
        progress = self.load_progress()
        start_index = progress["last_processed_index"] + 1
        
        # 创建结果列
        model_name = self.config["model_name"].replace("-", "_")
        reasoning_col = f"reasoning_{model_name}"
        classification_col = f"classification_{model_name}"
        
        if reasoning_col not in df.columns:
            df[reasoning_col] = ""
        if classification_col not in df.columns:
            df[classification_col] = ""
        
        # 处理数据
        total_rows = len(df)
        processed_count = 0
        
        with tqdm(total=total_rows, initial=start_index, desc="处理进度") as pbar:
            for index, row in df.iterrows():
                if index < start_index:
                    continue
                
                # 检查是否已经处理过
                if (not pd.isna(row[reasoning_col]) and row[reasoning_col] != "" and
                    not pd.isna(row[classification_col]) and row[classification_col] != ""):
                    pbar.update(1)
                    continue
                
                user_prompt = str(row[user_prompt_col])
                
                self.logger.info(f"处理第 {index + 1} 行数据...")
                
                # 调用AI API
                result = self.call_ai_api(user_prompt, system_prompt)
                
                if result:
                    reasoning = result.get("reasoning", "")
                    classification = result.get("classification", "")
                    
                    df.at[index, reasoning_col] = reasoning
                    df.at[index, classification_col] = classification
                    
                    processed_count += 1
                    self.logger.info(f"成功处理第 {index + 1} 行: {classification}")
                else:
                    self.logger.error(f"处理第 {index + 1} 行失败")
                
                # 更新进度
                progress["last_processed_index"] = index
                if index not in progress["processed_rows"]:
                    progress["processed_rows"].append(index)
                self.save_progress(progress)
                
                # 保存CSV文件
                df.to_csv(csv_file, index=False)
                
                pbar.update(1)
                
                # 添加延迟避免API限制
                time.sleep(0.1)
        
        self.logger.info(f"处理完成！共处理 {processed_count} 条新数据")
        return True
    
    def reset_progress(self):
        """重置进度"""
        progress_file = self.config["progress_file"]
        if os.path.exists(progress_file):
            os.remove(progress_file)
        self.logger.info("进度已重置")
    
    def show_status(self):
        """显示当前状态"""
        csv_file = self.config["csv_input_file"]
        if not os.path.exists(csv_file):
            print(f"CSV文件不存在: {csv_file}")
            return
        
        df = pd.read_csv(csv_file)
        model_name = self.config["model_name"].replace("-", "_")
        reasoning_col = f"reasoning_{model_name}"
        classification_col = f"classification_{model_name}"
        
        total_rows = len(df)
        processed_rows = 0
        
        if reasoning_col in df.columns and classification_col in df.columns:
            processed_rows = len(df[(df[reasoning_col].notna()) & 
                                   (df[reasoning_col] != "") & 
                                   (df[classification_col].notna()) & 
                                   (df[classification_col] != "")])
        
        print(f"总行数: {total_rows}")
        print(f"已处理: {processed_rows}")
        print(f"待处理: {total_rows - processed_rows}")
        print(f"完成率: {processed_rows/total_rows*100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='AI模型调用脚本')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    parser.add_argument('--reset', action='store_true', help='重置进度')
    parser.add_argument('--status', action='store_true', help='显示状态')
    
    args = parser.parse_args()
    
    processor = AIModelProcessor(args.config)
    
    if args.reset:
        processor.reset_progress()
        return
    
    if args.status:
        processor.show_status()
        return
    
    # 检查API密钥
    if processor.config["api_key"] == "sk-your-api-key-here":
        print("请在配置文件中设置正确的API密钥")
        return
    
    processor.process_csv()


if __name__ == "__main__":
    main()
