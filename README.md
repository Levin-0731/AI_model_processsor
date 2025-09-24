# AI Model Processor

一个功能强大的AI模型批量调用脚本，支持断点续传、进度显示和配置化管理。

## 功能特点

- 🔄 **断点续传**: 支持中断后从上次停止的地方继续处理
- 📊 **进度显示**: 实时显示处理进度和状态
- ⚙️ **配置化管理**: 通过JSON配置文件管理所有参数
- 🛡️ **错误处理**: 包含重试机制和详细的错误日志
- 📝 **智能解析**: 自动解析AI返回的多种JSON格式

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

## 文件说明

- `ai_model_processor.py` - 主脚本文件
- `config.json` - 配置文件
- `system_prompt.md` - 系统提示词文件
- `sample_data.csv` - 样例数据文件
- `requirements.txt` - 依赖包列表

## 输出结果

脚本会在原CSV文件中新增两列：
- `reasoning_{model_name}` - AI的分析推理过程
- `classification_{model_name}` - 最终分类结果

## 支持的API

目前支持月之暗面Kimi模型，可通过修改配置文件支持其他兼容OpenAI格式的API。

## 许可证

MIT License
