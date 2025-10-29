#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单个AI识别测试脚本
直接在代码中写入user_prompt，在终端展示输出结果
"""

# ==================== 在这里修改你要测试的内容 ====================
USER_PROMPT = """
以下是该挂单的信息：
 typeName = 潮玩系列，spuName = WHY SO SERIOUS系列搪胶毛绒挂件，是megaspu
 挂单对应商品的规格 spec = 官方直发+现货+单盒
 挂单描述 = 盲盒官方直发
 
"""
# ================================================================

import requests
import json
import time
import os
from typing import Dict, Any, Optional

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
            "prompt_file": "system_prompt.md"
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
        
        print("🚀 正在调用AI API...")
        
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
    
    def test_single_prompt(self, user_prompt: str):
        """测试单个提示词"""
        print("\n" + "="*80)
        print("🧪 AI识别测试")
        print("="*80)
        
        # 加载系统提示词
        system_prompt = self.load_system_prompt()
        if not system_prompt:
            print("❌ 无法加载系统提示词")
            return
        
        print(f"\n📝 用户输入:")
        print("-" * 80)
        print(user_prompt)
        print("-" * 80)
        
        # 调用API
        result = self.call_ai_api(user_prompt, system_prompt)
        
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
    
    # 执行测试
    tester.test_single_prompt(USER_PROMPT.strip())


if __name__ == "__main__":
    main()

