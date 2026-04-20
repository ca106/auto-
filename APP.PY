import os
import requests
import json
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from openai import OpenAI  # 这里以OpenAI为例，你也可以换成deepseek等

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件最大16MB

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 初始化AI客户端（这里用DeepSeek举例，因为免费额度多）
client = OpenAI(
    api_key="YOUR_DEEPSEEK_API_KEY",  # 替换为你的API Key
    base_url="https://api.deepseek.com"
)

def upload_image_to_smms(image_path):
    """上传图片到 sm.ms 图床，返回URL"""
    url = "https://sm.ms/api/v2/upload"
    headers = {'Authorization': 'YOUR_SMMS_API_TOKEN'}  # sm.ms需要Token，可在官网获取
    # 注意：sm.ms v2 需要 Authorization，但也可以免Token使用旧版API，这里用新方式
    # 如果你没有Token，可以用以下无认证上传（但可能有更严格限制）：
    # files = {'smfile': open(image_path, 'rb')}
    # resp = requests.post("https://sm.ms/api/upload", files=files)
    # 这里演示使用v2版本，需要你在sm.ms注册后获取Secret Token
    with open(image_path, 'rb') as f:
        files = {'smfile': f}
        resp = requests.post(url, headers=headers, files=files)
        if resp.status_code == 200:
            data = resp.json()
            if data['success']:
                return data['data']['url']
            else:
                raise Exception(f"sm.ms上传失败: {data['message']}")
        else:
            raise Exception(f"上传请求失败: {resp.text}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        # 获取表单数据
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        style_desc = request.form.get('style', '').strip()
        
        # 处理上传的图片
        image_urls = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file.filename != '':
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    # 上传到图床
                    try:
                        img_url = upload_image_to_smms(filepath)
                        image_urls.append(img_url)
                    except Exception as e:
                        return jsonify({'error': f'图片上传失败: {str(e)}'}), 500
                    finally:
                        os.remove(filepath)  # 删除临时文件
        
        # 构造给AI的提示词
        prompt = f"""
你是一个专业的微信公众号排版设计师。请根据以下要求生成一段可直接用于秀米（xiù mǐ）HTML模式的代码。

【标题】
{title}

【正文内容】
{content}

【图片链接】
{image_urls}

【风格要求】
{style_desc}

【排版要求】
- 输出必须是完整的、自包含的HTML代码片段（无需<html><head>，只需<body>内部的内容），但需要包含<style>标签定义样式。
- 样式需适配移动端阅读（字体、行高、边距等适合手机屏幕）。
- 使用微信支持的CSS属性（避免flex、grid不兼容的情况，但基本都可以）。
- 图片居中显示，并可根据风格添加圆角、阴影等效果。
- 标题使用h1或h2，正文使用p标签，段落首行缩进2字符。
- 结尾可加上署名信息（如“西林学工”），但这不是必须的。
- 整体美观、符合描述的风格。

请直接输出HTML代码，不要包含任何解释性文字。
"""
        
        # 调用AI生成排版代码
        response = client.chat.completions.create(
            model="deepseek-chat",  # 或 gpt-4o-mini
            messages=[
                {"role": "system", "content": "你是一个微信公众号排版专家，只输出符合要求的HTML代码。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        html_output = response.choices[0].message.content.strip()
        
        # 清理可能出现的markdown代码块标记
        if html_output.startswith("```html"):
            html_output = html_output[7:]
        if html_output.endswith("```"):
            html_output = html_output[:-3]
        html_output = html_output.strip()
        
        return jsonify({'html': html_output})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run( host='0.0.0.0', port=5000)