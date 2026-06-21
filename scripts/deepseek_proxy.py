"""
DeepSeek to OpenAI 格式代理服务器
用于在 Codex 桌面端使用 DeepSeek 模型
"""

from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', 'your-api-key-here')
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

@app.route('/v1/<path:endpoint>', methods=['GET', 'POST'])
def proxy(endpoint):
    """代理所有 /v1/* 请求到 DeepSeek API"""
    url = f"{DEEPSEEK_BASE_URL}/{endpoint}"
    
    # 准备请求头
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': request.content_type or 'application/json'
    }
    
    # 复制其他请求头
    for key in ['User-Agent', 'Accept']:
        if key in request.headers:
            headers[key] = request.headers[key]
    
    try:
        if request.method == 'POST':
            # 修改请求体中的模型名称
            data = request.get_json()
            if data and 'model' in data:
                # 可以将自定义模型名映射到 DeepSeek 模型
                model_mapping = {
                    'codex-deepseek-v4': 'deepseek-v4',
                    'codex-deepseek-v4-flash': 'deepseek-v4-flash',
                    'codex-deepseek-v4-pro': 'deepseek-v4-pro'
                }
                if data['model'] in model_mapping:
                    data['model'] = model_mapping[data['model']]
                request.data = json.dumps(data)
            
            response = requests.post(url, headers=headers, data=request.data, timeout=30)
        else:
            response = requests.get(url, headers=headers, params=request.args, timeout=10)
        
        # 返回响应
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/models', methods=['GET'])
def list_models():
    """返回可用的模型列表"""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "deepseek-v4",
                "object": "model",
                "owned_by": "deepseek"
            },
            {
                "id": "deepseek-v4-flash",
                "object": "model",
                "owned_by": "deepseek"
            },
            {
                "id": "deepseek-v4-pro",
                "object": "model",
                "owned_by": "deepseek"
            }
        ]
    })

if __name__ == '__main__':
    print("启动 DeepSeek 代理服务器...")
    print("访问 http://127.0.0.1:8000/v1/models 查看可用模型")
    print("在 Codex 桌面端设置中使用 base_url: http://127.0.0.1:8000")
    app.run(host='127.0.0.1', port=8000, debug=True)
