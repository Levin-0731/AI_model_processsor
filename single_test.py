#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单个AI识别测试脚本
支持文本和图片输入（兼容视觉模型）
直接在代码中写入user_prompt和image_path，在终端展示输出结果
"""

# ==================== 在这里修改你要测试的内容 ====================
USER_PROMPT = """
以下是该挂单的信息：
 typeName = 潮玩系列，spuName = WHY SO SERIOUS系列搪胶毛绒挂件，是megaspu
 挂单对应商品的规格 spec = 官方直发+现货+单盒
 挂单描述 = 盲盒官方直发
 
"""

# 图片路径（可选，留空则使用纯文本模式）
# 支持绝对路径或相对路径
# 示例: IMAGE_PATH = "/path/to/image.jpg"
IMAGE_PATH = ""
# ================================================================

import requests
import json
import time
import os
import base64
import mimetypes
from typing import Dict, Any, Optional, List, Union


class SingleAITest:
    def __init__(self, config_file: str = "config.json"):
        """初始化AI测试器"""
        self.config = self.load_config(config_file)
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "api_url": "https://api.moonshot.cn/v1/chat/completions",
            "api_key": "sk-your-api-key-here",
            "model_name": "kimi-k2-0905-preview",
            "temperature": 0.6,
            "max_tokens": 2000,
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1,
            "prompt_file": "system_prompt.md",
            "image_base_path": "",
            "image_detail": "auto"
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def load_system_prompt(self) -> str:
        """加载系统提示词"""
        prompt_file = self.config["prompt_file"]
        if not os.path.exists(prompt_file):
            print(f"❌ 提示词文件不存在: {prompt_file}")
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
    
    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """将本地图片转换为Base64编码的data URL"""
        if not os.path.exists(image_path):
            print(f"❌ 图片不存在: {image_path}")
            return None
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(image_path)
        supported_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        
        if mime_type not in supported_types:
            print(f"❌ 不支持的图片格式: {mime_type} (支持: {', '.join(supported_types)})")
            return None
        
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            print(f"❌ 读取图片失败: {str(e)}")
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
            print(f"⚠️ 图片处理失败，降级为纯文本模式")
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
        
        print("🚀 正在调用AI API...")
        if image_path:
            print(f"🖼️ 使用图片: {image_path}")
        
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
                        print(f"❌ API返回格式错误")
                else:
                    print(f"❌ API调用失败 (状态码: {response.status_code})")
                    print(f"响应内容: {response.text}")
                
            except requests.exceptions.RequestException as e:
                if attempt == self.config["max_retries"] - 1:
                    print(f"❌ API调用失败: {str(e)}")
                else:
                    print(f"⚠️  第 {attempt + 1} 次尝试失败，重试中...")
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
            
            print(f"❌ 无法解析AI响应为JSON")
            print(f"原始响应: {content}")
            return None
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {str(e)}")
            print(f"原始响应: {content}")
            return None
    
    def test_single_prompt(self, user_prompt: str, image_path: str = None):
        """
        测试单个提示词（支持图片）
        
        Args:
            user_prompt: 用户提示词
            image_path: 图片路径（可选）
        """
        print("\n" + "="*80)
        print("🧪 AI识别测试")
        if image_path:
            print("🖼️ 模式: 图片+文本")
        else:
            print("📝 模式: 纯文本")
        print("="*80)
        
        # 加载系统提示词
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
        
        # 调用API（支持图片）
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
    # 创建测试器实例
    tester = SingleAITest()
    
    # 检查API密钥
    if tester.config["api_key"] == "sk-your-api-key-here":
        print("⚠️  请在 config.json 中设置正确的API密钥")
        return
    
    # 获取图片路径（如果设置了的话）
    image_path = IMAGE_PATH.strip() if IMAGE_PATH else None
    
    # 执行测试（支持图片）
    tester.test_single_prompt(USER_PROMPT.strip(), image_path)


if __name__ == "__main__":
    main()
