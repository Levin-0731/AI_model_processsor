# AI Model Processor

一个功能强大的AI模型批量调用脚本，支持断点续传、进度显示和配置化管理。

## 功能特点

- 🔄 **断点续传**: 支持中断后从上次停止的地方继续处理
- 📊 **进度显示**: 实时显示处理进度和状态
- ⚙️ **配置化管理**: 通过JSON配置文件管理所有参数
- 🛡️ **错误处理**: 包含重试机制和详细的错误日志
- 📝 **智能解析**: 自动解析AI返回的多种JSON格式
- 🖼️ **图片支持**: 支持本地图片输入，兼容视觉模型（如GPT-4o、Claude 3等）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置设置

编辑 `config.json` 文件，设置您的API密钥：

```json
{
  "api_key": "your-actual-api-key-here",
  "csv_input_file": "sample_data.csv",
  "prompt_file": "system_prompt.md"
}
```

### 3. 准备数据

- 将您的数据放在CSV文件中（默认：`sample_data.csv`）
- 确保CSV文件包含 `user_prompt` 列
- 创建系统提示词文件（默认：`system_prompt.md`）

### 4. 运行脚本

```bash
# 开始处理
python ai_model_processor.py

# 查看处理状态
python ai_model_processor.py --status

# 重置进度重新开始
python ai_model_processor.py --reset
```

## 图片支持

### 使用图片输入

本脚本支持本地图片作为输入，适用于视觉模型（如GPT-4o、Claude 3 Vision等）。

#### 配置图片列

在 `config.json` 中添加图片相关配置：

```json
{
  "api_url": "https://api.openai.com/v1/chat/completions",
  "model_name": "gpt-4o",
  "image_column": "image_path",
  "image_base_path": "/path/to/images/",
  "image_detail": "auto"
}
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `image_column` | CSV中图片路径列名 | `""` (不使用图片) |
| `image_base_path` | 图片基础路径，用于拼接相对路径 | `""` |
| `image_detail` | 图片细节级别: `low`/`high`/`auto` | `"auto"` |

#### CSV格式示例

**纯文本模式：**
```csv
user_prompt
"请分析这段文本"
"另一段需要分析的内容"
```

**图片+文本模式：**
```csv
user_prompt,image_path
"请分析这张图片",/path/to/image1.jpg
"描述这张照片的内容",/path/to/image2.png
```

**使用相对路径：**
```csv
user_prompt,image_path
"请分析这张图片",image1.jpg
"描述这张照片的内容",image2.png
```
配合 `image_base_path` 配置使用。

#### 支持的图片格式

- JPEG/JPG
- PNG
- GIF
- WebP

### 单条图片测试

编辑 `single_test.py` 文件顶部的变量：

```python
USER_PROMPT = "请分析这张图片"
IMAGE_PATH = "/path/to/your/image.jpg"
```

然后运行：

```bash
python single_test.py
```

## 文件说明

- `ai_model_processor.py` - 主脚本文件
- `single_test.py` - 单条测试脚本
- `config.json` - 配置文件
- `system_prompt.md` - 系统提示词文件
- `sample_data.csv` - 样例数据文件
- `requirements.txt` - 依赖包列表

## 配置参数说明

### API配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `api_url` | API端点地址 | `https://api.moonshot.cn/v1/chat/completions` |
| `api_key` | API密钥 | `sk-your-api-key-here` |
| `model_name` | 模型名称 | `kimi-k2-0905-preview` |
| `temperature` | 采样温度 (0-1) | `0.6` |
| `max_tokens` | 最大输出token数 | `2000` |
| `timeout` | 请求超时时间(秒) | `30` |
| `max_retries` | 最大重试次数 | `3` |
| `retry_delay` | 重试延迟(秒) | `1` |

### 处理配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `csv_input_file` | 输入CSV文件路径 | `sample_data.csv` |
| `prompt_file` | 系统提示词文件路径 | `system_prompt.md` |
| `user_prompt_column` | 用户提示词列名 | `user_prompt` |
| `max_workers` | 并发线程数 | `3` |
| `request_delay` | 请求间隔(秒) | `0.5` |

### 图片配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `image_column` | 图片路径列名 | `""` (不使用图片) |
| `image_base_path` | 图片基础路径 | `""` |
| `image_detail` | 图片细节级别 | `"auto"` |

## 输出结果

脚本会在原CSV文件中新增两列：
- `reasoning_{model_name}` - AI的分析推理过程
- `classification_{model_name}` - 最终分类结果

## 支持的API

支持所有兼容OpenAI格式的API，包括：
- OpenAI (GPT-4, GPT-4o, GPT-4-turbo)
- 月之暗面 Kimi
- DeepSeek
- Claude (通过兼容层)
- 其他兼容OpenAI格式的API

## 许可证

MIT License
