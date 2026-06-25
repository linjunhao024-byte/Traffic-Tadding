#!/usr/bin/env python3
"""测试 DeepSeek API 连通性"""
import json
import time
import urllib.request
import ssl

API_KEY = "ad9eef82782f75050b28f407026813735a5109db"
BASE_URL = "https://api-x4l639rbh7gdz1pa.aistudio-app.com/v1/chat/completions"
MODEL = "DeepSeek-R1-Distill-Llama-8B-F16"

ssl_ctx = ssl.create_default_context()

payload = json.dumps({
    "model": MODEL,
    "temperature": 0.6,
    "messages": [{"role": "user", "content": "用一句话介绍你自己"}],
    "stream": False,
    "max_tokens": 100,
}).encode('utf-8')

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}

print(f"正在调用 API: {BASE_URL}")
print(f"模型: {MODEL}")
print(f"等待响应...")

start = time.time()
try:
    req = urllib.request.Request(BASE_URL, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
        elapsed = time.time() - start
        result = json.loads(resp.read().decode('utf-8'))
        content = result['choices'][0]['message']['content']
        print(f"\n✅ 成功! 耗时: {elapsed:.1f}秒")
        print(f"回复: {content}")
except Exception as e:
    elapsed = time.time() - start
    print(f"\n❌ 失败! 耗时: {elapsed:.1f}秒")
    print(f"错误: {e}")
