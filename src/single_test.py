#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单个AI识别测试脚本
支持文本和图片输入（兼容视觉模型）
支持多Provider和多种API调用方式
"""

# ==================== 在这里修改你要测试的内容 ====================
USER_PROMPT = """请分析这张照片的脸型和外貌特征"""

# 图片路径（可选，留空则使用纯文本模式）
IMAGE_PATH = "test_face_compressed.jpg"
# ================================================================

import requests
import json
import yaml
import time
import os
import base64
import mimetypes
from typing import Dict, Any, Optional, List, Union, Tuple


class SingleAITest:
    def __init__(self, config_file: str = "config.yaml", providers_file: str = "providers.yaml"):
        """初始化AI测试器"""
        self.config = self.load_config(config_file)
        self.providers = self.load_providers(providers_file)
        self.provider_config = self.get_provider_config()
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """加载运行配置文件"""
        default_config = {
            "provider": "openai",
            "model_name": "gpt-4o",
            "temperature": 0.6,
            "max_tokens": 2000,
            "prompt_file": "system_prompt.md",
            "image_base_path": "",
            "image_detail": "auto"
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
        
        return default_config
    
    def load_providers(self, providers_file: str) -> Dict[str, Any]:
        """加载Provider配置文件"""
        if os.path.exists(providers_file):
            with open(providers_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {"providers": {}, "default_provider": "openai"}
    
    def get_provider_config(self) -> Dict[str, Any]:
        """获取当前Provider的配置，支持从环境变量读取API密钥"""
        provider_name = self.config.get("provider", self.providers.get("default_provider", "openai"))
        providers = self.providers.get("providers", {})
        
        if provider_name not in providers:
            print(f"❌ Provider '{provider_name}' 不存在于 providers.yaml")
            return {}
        
        config = providers[provider_name].copy()
        
        # 如果配置文件中没有 API 密钥，尝试从环境变量读取
        if not config.get("api_key"):
            env_key_name = f"{provider_name.upper()}_API_KEY"
            env_api_key = os.environ.get(env_key_name)
            if env_api_key:
                config["api_key"] = env_api_key
                print(f"🔑 已从环境变量 {env_key_name} 读取API密钥")
        
        return config
    
    def load_system_prompt(self) -> str:
        """加载系统提示词"""
        prompt_file = self.config["prompt_file"]
        if not os.path.exists(prompt_file):
            print(f"❌ 提示词文件不存在: {prompt_file}")
            return ""
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'system_prompt = """' in content:
            start = content.find('system_prompt = """') + len('system_prompt = """')
            end = content.rfind('"""')
            if end > start:
                content = content[start:end]
        
        return content.strip()
    
    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """将本地图片转换为Base64编码的data URL"""
        if not os.path.exists(image_path):
            print(f"❌ 图片不存在: {image_path}")
            return None
        
        mime_type, _ = mimetypes.guess_type(image_path)
        supported_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        
        if mime_type not in supported_types:
            print(f"❌ 不支持的图片格式: {mime_type}")
            return None
        
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            print(f"❌ 读取图片失败: {str(e)}")
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
                    print(f"❌ API调用失败 (状态码: {response.status_code})")
                    print(f"响应内容: {response.text[:200]}")
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"❌ API调用失败: {str(e)}")
                else:
                    print(f"⚠️  第 {attempt + 1} 次尝试失败，重试中...")
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
                    print(f"❌ API调用失败 (状态码: {response.status_code})")
                    print(f"响应内容: {response.text[:200]}")
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"❌ API调用失败: {str(e)}")
                else:
                    print(f"⚠️  第 {attempt + 1} 次尝试失败，重试中...")
                    time.sleep(retry_delay * (attempt + 1))
        
        return None
    
    def call_api_google(self, user_prompt: str, system_prompt: str, image_path: str = None) -> Optional[str]:
        """调用Google Gemini API"""
        model_name = self.config["model_name"]
        api_key = self.provider_config['api_key']
        base_url = self.provider_config["api_url"]
        url = f"{base_url}/models/{model_name}:generateContent?key={api_key}"
        
        headers = {"Content-Type": "application/json"}
        
        parts = []
        if system_prompt:
            parts.append({"text": f"System: {system_prompt}\n\nUser: {user_prompt}"})
        else:
            parts.append({"text": user_prompt})
        
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
                    print(f"❌ API调用失败 (状态码: {response.status_code})")
                    print(f"响应内容: {response.text[:200]}")
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"❌ API调用失败: {str(e)}")
                else:
                    print(f"⚠️  第 {attempt + 1} 次尝试失败，重试中...")
                    time.sleep(retry_delay * (attempt + 1))
        
        return None
    
    def call_ai_api(self, user_prompt: str, system_prompt: str, image_path: str = None) -> Optional[Dict[str, Any]]:
        """统一的API调用入口"""
        api_type = self.provider_config.get("api_type", "openai")
        
        print(f"🚀 正在调用AI API...")
        print(f"   Provider: {self.config.get('provider', 'unknown')}")
        print(f"   模型: {self.config['model_name']}")
        print(f"   API类型: {api_type}")
        if image_path:
            print(f"   🖼️ 图片: {image_path}")
        
        if api_type == "openai":
            content = self.call_api_openai(user_prompt, system_prompt, image_path)
        elif api_type == "anthropic":
            content = self.call_api_anthropic(user_prompt, system_prompt, image_path)
        elif api_type == "google":
            content = self.call_api_google(user_prompt, system_prompt, image_path)
        else:
            print(f"❌ 不支持的API类型: {api_type}")
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
            
            print(f"❌ 无法解析AI响应为JSON")
            print(f"原始响应: {content}")
            return None
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {str(e)}")
            print(f"原始响应: {content}")
            return None
    
    def test_single_prompt(self, user_prompt: str, image_path: str = None):
        """测试单个提示词"""
        print("\n" + "="*80)
        print("🧪 AI识别测试")
        if image_path:
            print("🖼️ 模式: 图片+文本")
        else:
            print("📝 模式: 纯文本")
        print("="*80)
        
        system_prompt = self.load_system_prompt()
        if not system_prompt:
            print("❌ 无法加载系统提示词")
            return
        
        print(f"\n📝 用户输入:")
        print("-" * 80)
        print(user_prompt)
        if image_path:
            print(f"\n🖼️ 图片路径: {image_path}")
        print("-" * 80)
        
        result = self.call_ai_api(user_prompt, system_prompt, image_path)
        
        if result:
            print("\n✅ AI识别结果:")
            print("="*80)
            print(f"\n💭 思考过程 (Thoughts):")
            print("-" * 80)
            thoughts = result.get("Thoughts", "")
            print(thoughts if thoughts else "无")
            
            print(f"\n🏷️  分类结果 (Category):")
            print("-" * 80)
            category = result.get("Category", "")
            print(category if category else "无")
            
            print("\n📋 完整JSON响应:")
            print("-" * 80)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("="*80)
        else:
            print("\n❌ 识别失败")
        
        print()


def main():
    """主函数"""
    tester = SingleAITest()
    
    # 检查API密钥
    if not tester.provider_config.get("api_key"):
        provider_name = tester.config.get("provider", "unknown")
        print(f"⚠️  请在 providers.yaml 中为 '{provider_name}' 设置API密钥，或设置环境变量 {provider_name.upper()}_API_KEY")
        return
    
    image_path = IMAGE_PATH.strip() if IMAGE_PATH else None
    
    tester.test_single_prompt(USER_PROMPT.strip(), image_path)


if __name__ == "__main__":
    main()
