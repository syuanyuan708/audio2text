from flask import Flask, render_template, request, send_file, send_from_directory, jsonify
import whisper
import os
from datetime import timedelta
import tempfile
from opencc import OpenCC
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 最大文件限制

# 确保上传目录和日志目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

# 配置日志
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)

# 文件处理器 - 记录到文件
file_handler = RotatingFileHandler(
    'logs/whisper_app.log',
    maxBytes=10240,  # 10KB
    backupCount=10
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# 控制台处理器 - 输出到控制台
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# 添加处理器到应用日志记录器
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)
app.logger.setLevel(logging.INFO)

# 初始化繁简转换器
cc = OpenCC('t2s')  # 繁体转简体

# 修改支持的文件类型集合
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'mp4'}

def allowed_file(filename):
    print(filename)
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_timedelta(seconds):
    print(seconds)
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    seconds = td.seconds % 60
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def create_srt(segments):
    print(segment)
    srt_content = []
    for i, segment in enumerate(segments, start=1):
        start_time = format_timedelta(segment['start'])
        end_time = format_timedelta(segment['end'])
        # 将繁体文本转换为简体
        text = cc.convert(segment['text'].strip())
        srt_content.append(f"{i}\n{start_time} --> {end_time}\n{text}\n")
    return "\n".join(srt_content)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        app.logger.error('没有文件被上传')
        return jsonify({'error': '没有文件被上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        app.logger.error('没有选择文件')
        return jsonify({'error': '没有选择文件'}), 400
        
    if not allowed_file(file.filename):
        app.logger.error(f'不支持的文件类型: {file.filename}')
        return jsonify({'error': '不支持的文件类型'}), 400

    try:
        app.logger.info(f'开始处理文件: {file.filename}')
        
        # 保存上传的文件
        temp_audio = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_audio.name)
        
        # 加载Whisper模型
        app.logger.info('加载Whisper模型')
        model = whisper.load_model("base")
        
        # 转录音频，指定中文
        app.logger.info('开始音频转录')
        result = model.transcribe(temp_audio.name, language="zh")
        
        # 生成SRT内容
        app.logger.info('生成SRT文件')
        srt_content = create_srt(result['segments'])
        
        # 保存SRT文件
        srt_filename = os.path.splitext(file.filename)[0] + '.srt'
        srt_path = os.path.join(app.config['UPLOAD_FOLDER'], srt_filename)
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        # 清理临时文件
        os.unlink(temp_audio.name)
        
        app.logger.info(f'文件处理成功: {srt_filename}')
        return jsonify({
            'success': True,
            'message': '✅ 上传成功！字幕文件已生成',
            'filename': srt_filename
        })
    
    except Exception as e:
        app.logger.error(f'处理文件时出错: {str(e)}', exc_info=True)
        return jsonify({'error': f'处理文件时出错: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'],
                                 filename,
                                 as_attachment=True)
    except Exception as e:
        return jsonify({'error': '文件下载失败'}), 404

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run(debug=True) 