"""运营商适配器层: 把统一的 TaskInput 翻译成各平台 HTTP 调用, 再把响应
归一化为 TaskOutput。异步平台 (如 Replicate) 的轮询封装在适配器内部。
"""
