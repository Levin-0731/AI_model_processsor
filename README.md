# AI Model Processor

一个功能强大的AI模型批量调用脚本，支持多Provider、断点续传、进度显示和配置化管理。

## 功能特点

- 🔄 **断点续传**: 支持中断后从上次停止的地方继续处理
- 📊 **进度显示**: 实时显示处理进度和状态
- ⚙️ **配置化管理**: 通过JSON配置文件管理所有参数
- 🛡️ **错误处理**: 包含重试机制和详细的错误日志
- 📝 **智能解析**: 自动解析AI返回的多种JSON格式
- 🖼️ **图片支持**: 支持本地图片输入，兼容视觉模型
- 🔌 **多Provider支持**: 支持OpenAI、Anthropic、Google等多种API

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置Provider

编辑 `providers.json` 文件，设置您的API密钥：

```json
{
  "providers": {
    "openai": {
      "api_url": "https://api.openai.com/v1/chat/completions",
      "api_key": "your-api-key-here",
      "api_type": "openai"
    }
  }
}
```

### 3. 配置运行参数

编辑 `config.json` 文件：

```json
{
  "provider": "openai",
  "model_name": "gpt-4o",
  "csv_input_file": "sample_data.csv",
  "prompt_file": "system_prompt.md"
}
```

### 4. 运行脚本

```bash
# 开始处理
python ai_model_processor.py

# 查看处理状态
python ai_model_processor.py --status

# 列出所有Provider
python ai_model_processor.py --list-providers

# 重置进度重新开始
python ai_model_processor.py --reset

# 使用命令行指定Provider和模型
python ai_model_processor.py --provider openai --model gpt-4-turbo
```

## 多Provider支持

### 支持的API类型

| api_type | 调用结构 | 适用Provider |
|----------|----------|--------------|
| `openai` | OpenAI标准格式 | OpenAI, DeepSeek, Kimi, 通义千问, Groq等 |
| `anthropic` | Anthropic格式 | Claude |
| `google` | Google格式 | Gemini |

### providers.json 配置示例

```json
{
  "providers": {
    "openai": {
      "api_url": "https://api.openai.com/v1/chat/completions",
      "api_key": "sk-xxx",
      "api_type": "openai",
      "timeout": 60,
      "max_retries": 3,
      "retry_delay": 2,
      "available_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
    },
    "anthropic": {
      "api_url": "https://api.anthropic.com/v1/messages",
      "api_key": "sk-ant-xxx",
      "api_type": "anthropic",
      "api_version": "2023-06-01",
      "timeout": 60,
      "max_retries": 3,
      "retry_delay": 2,
      "available_models": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]
    },
    "deepseek": {
      "api_url": "https://api.deepseek.com/v1/chat/completions",
      "api_key": "sk-xxx",
      "api_type": "openai",
      "timeout": 30,
      "available_models": ["deepseek-chat", "deepseek-coder"]
    },
    "kimi": {
      "api_url": "https://api.moonshot.cn/v1/chat/completions",
      "api_key": "sk-xxx",
      "api_type": "openai",
      "timeout": 30,
      "available_models": ["kimi-k2-0905-preview", "moonshot-v1-8k"]
    },
    "google": {
      "api_url": "https://generativelanguage.googleapis.com/v1beta",
      "api_key": "xxx",
      "api_type": "google",
      "timeout": 60,
      "available_models": ["gemini-1.5-pro", "gemini-1.5-flash"]
    }
  },
  "default_provider": "openai"
}
```

### 切换Provider和模型

**方式1：修改 config.json**
```json
{
  "provider": "anthropic",
  "model_name": "claude-3-5-sonnet-20241022"
}
```

**方式2：命令行参数**
```bash
python ai_model_processor.py --provider deepseek --model deepseek-chat
```

## 图片支持

### 配置图片列

在 `config.json` 中添加图片相关配置：

```json
{
  "image_column": "image_path",
  "image_base_path": "/path/to/images/",
  "image_detail": "auto"
}
```

### CSV格式示例

**图片+文本模式：**
```csv
user_prompt,image_path
"请分析这张图片",/path/to/image1.jpg
"描述这张照片的内容",/path/to/image2.png
```

### 支持的图片格式

- JPEG/JPG
- PNG
- GIF
- WebP

## 文件说明

| 文件 | 说明 |
|------|------|
| `ai_model_processor.py` | 主脚本文件 |
| `single_test.py` | 单条测试脚本 |
| `config.json` | 运行配置文件 |
| `providers.json` | Provider配置文件 |
| `system_prompt.md` | 系统提示词文件 |
| `sample_data.csv` | 样例数据文件 |
| `requirements.txt` | 依赖包列表 |

## 配置参数说明

### config.json

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `provider` | 使用的Provider名称 | `openai` |
| `model_name` | 模型名称 | `gpt-4o` |
| `temperature` | 采样温度 (0-1) | `0.6` |
| `max_tokens` | 最大输出token数 | `2000` |
| `csv_input_file` | 输入CSV文件路径 | `sample_data.csv` |
| `prompt_file` | 系统提示词文件路径 | `system_prompt.md` |
| `user_prompt_column` | 用户提示词列名 | `user_prompt` |
| `image_column` | 图片路径列名 | `""` |
| `image_base_path` | 图片基础路径 | `""` |
| `image_detail` | 图片细节级别 | `"auto"` |
| `max_workers` | 并发线程数 | `3` |
| `request_delay` | 请求间隔(秒) | `0.5` |

### providers.json

| 参数 | 说明 |
|------|------|
| `api_url` | API端点地址 |
| `api_key` | API密钥 |
| `api_type` | API类型 (openai/anthropic/google) |
| `api_version` | API版本 (Anthropic专用) |
| `timeout` | 请求超时时间(秒) |
| `max_retries` | 最大重试次数 |
| `retry_delay` | 重试延迟(秒) |
| `available_models` | 可用模型列表 |

## 命令行参数

```bash
python ai_model_processor.py [选项]

选项:
  --config FILE       配置文件路径 (默认: config.json)
  --providers FILE    Provider配置文件路径 (默认: providers.json)
  --provider NAME     指定使用的Provider
  --model NAME        指定使用的模型
  --workers N         并发线程数量
  --status            显示处理状态
  --list-providers    列出所有Provider
  --reset             重置进度
```

## 输出结果

脚本会在原CSV文件中新增两列：
- `reasoning_{model_name}` - AI的分析推理过程
- `classification_{model_name}` - 最终分类结果

## 许可证

MIT License
