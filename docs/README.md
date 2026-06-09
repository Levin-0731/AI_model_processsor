# DancePhotoFix · 统一 AI 批处理引擎

一个与「平台」和「任务」解耦的 AI 批处理框架：用同一套配置和命令行，把一批输入（表格行 / 文件夹图片）批量送入不同的 AI 服务（OpenAI、Anthropic、Gemini、DeepSeek、Replicate 等），完成 **文生文 / 图生文 / 文生图 / 图生图** 等任务，并支持并发、断点续传、进度展示和限速。

> 项目最初用于人像/脸型分析等图像处理场景，后重构为通用引擎。

## ⭐ 核心原则（项目内核，不可妥协）

> **用一个通用的脚本，去完成所有 AI 批处理任务（图生图、文生图、图生文……），同时支持灵活切换不同运营商、不同任务模式。**

从产品经理视角，本项目最重要的三件事，也是任何改动都必须守住的底线：

1. **通用性** — 一套引擎覆盖所有任务类型与运营商；新增能力是"长进框架"，而不是在旁边孤立地再写一个脚本。
2. **可配置性** — 切换 provider、task、模型、输入输出，全部通过 YAML 配置完成，不改代码。
3. **可测试性** — 通过 mock provider 与 `--dry-run` 支持离线验证；新增运营商或任务类型必须配套测试。

**反面教训**：不要为某个具体任务（如某个图生图模型）单独新建脚本——这恰恰违背了项目内核。Provider 与 Task 都是**可插拔、可配置、可测试**的维度，任何新平台/新任务都应作为这两个维度的组合接入统一引擎。

## ✨ 特性

- **多运营商（Provider）**：通过 `config/providers.yaml` 统一管理各家 API，按 `api_type`（openai / anthropic / google 等）选择调用方式。
- **多任务模式（Task）**：`text2image`、`image2image` 等任务即插即用。
- **多数据源 / 落盘（Source / Sink）**：支持表格（CSV / Excel，含嵌入图片）与文件夹两类输入输出。
- **工程化能力**：并发执行、断点续传（跳过已完成）、请求限速、日志、`--dry-run` 预演。
- **密钥安全**：API Key 通过环境变量注入，不写入仓库。

## 📁 项目结构

```
DancePhotoFix/
├── src/
│   ├── cli.py              # 命令行入口（run / test / status / list-providers / reset）
│   ├── core/
│   │   ├── engine.py       # 执行引擎：组装 + 并发 + 续传 + 限速
│   │   └── types.py        # 统一数据结构（ImageRef / TaskInput / TaskOutput ...）
│   ├── providers/          # 各运营商适配器（base + 具体实现）
│   ├── tasks/              # 任务模式（image2image / text2image ...）
│   ├── dataio/             # 数据源与落盘
│   └── replicate_batch.py  # Replicate 批处理脚本
├── config/
│   ├── config.yaml         # 运行配置（provider / model / 输入输出 / 并发）
│   ├── providers.yaml      # 运营商与密钥配置
│   ├── env_template.sh     # 环境变量模板
│   └── requirements.txt    # 依赖
├── prompts/                # Prompt 文件
├── data/                   # 数据样例
├── tests/                  # 单元测试（pytest）
└── docs/                   # 文档（含本 README）
```

## 🚀 快速开始

### 1. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r config/requirements.txt
```

### 2. 配置密钥（推荐用环境变量）

密钥不写入仓库。复制模板并填入你的 Key：

```bash
cp config/env_template.sh .env.sh
# 编辑 .env.sh，填入对应运营商的 API Key，例如：
#   export BLTCY_API_KEY="sk-xxxx"
source .env.sh
```

`config/providers.yaml` 中各运营商的 `api_key` 留空时，引擎会自动从环境变量（默认 `<PROVIDER>_API_KEY`）读取。

### 3. 选择运营商与模型

编辑 `config/config.yaml`：

```yaml
provider: bltcy          # 见 providers.yaml
model_name: gpt-4o
```

### 4. 运行

```bash
# 查看可用运营商及密钥状态
python src/cli.py list-providers

# 单条/单图快速验证
python src/cli.py test --image path/to/img.jpg --prompt "描述这张图"

# 预演（只构建请求，不真正调用 API）
python src/cli.py run --dry-run

# 正式批处理
python src/cli.py run --config config/config.yaml

# 查看表格任务进度
python src/cli.py status

# 清空表格任务的结果列
python src/cli.py reset
```

常用参数：`--provider`、`--model`、`--task`、`--workers` 可在命令行临时覆盖配置。

## 🧩 命令一览

| 命令 | 说明 |
|------|------|
| `run` | 按配置批处理，支持 `--dry-run`、`--workers` |
| `test` | 单条 / 单图快速验证 |
| `status` | 查看表格类任务的处理进度 |
| `list-providers` | 列出运营商及密钥状态 |
| `reset` | 清空表格任务的结果列 |

## 🧪 测试

```bash
source venv/bin/activate
pytest tests/
```

## ⚠️ 注意事项

- `原图/`、`结果图/`、`生成图/` 等人像数据与生成产物**不纳入版本管理**（见 `.gitignore`），请勿提交隐私图片。
- 部分视觉模型对真实人像分析有内容政策限制，必要时更换运营商（如 Claude / Gemini / DeepSeek）。

---

最后更新：2026-06-09
