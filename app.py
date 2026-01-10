from flask import Flask, render_template, request, jsonify, Response
import yaml
import os
import json
import threading
import time

# 导入实际的监控程序
from main import Cloud123Monitor

app = Flask(__name__)

# 配置文件路径
CONFIG_PATH = './conf/config.yaml'

# 从环境变量获取认证信息
AUTH_USERNAME = os.environ.get('APP_USERNAME', '')
AUTH_PASSWORD = os.environ.get('APP_PASSWORD', '')

# 检查是否启用了认证
AUTH_ENABLED = bool(AUTH_USERNAME and AUTH_PASSWORD)

# 基础HTTP验证装饰器
def requires_auth(f):
    def decorated(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        
        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            return Response(
                '请提供用户名和密码', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        
        if auth.username != AUTH_USERNAME or auth.password != AUTH_PASSWORD:
            return Response(
                '用户名或密码错误', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        
        return f(*args, **kwargs)
    
    decorated.__name__ = f.__name__
    return decorated

# 对所有请求启用认证
@app.before_request
def before_request():
    # 跳过静态文件的认证
    if request.path.startswith('/static/'):
        return
    
    if not AUTH_ENABLED:
        return
    
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return Response(
            '请提供用户名和密码', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )
    
    if auth.username != AUTH_USERNAME or auth.password != AUTH_PASSWORD:
        return Response(
            '用户名或密码错误', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )

# 用于控制后端服务的线程
monitor_instance = None
backend_thread = None
backend_running = False

# 读取配置文件
def read_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    # 从API配置中移除api_base_url（如果存在）
    if 'api' in config and 'api_base_url' in config['api']:
        del config['api']['api_base_url']
    return config

# 写入配置文件
def write_config(config):
    # 添加空值检查
    if config is None:
        config = {}
    
    # 处理monitored_shares，过滤掉last_sync_time字段
    monitored_shares = config.get('monitored_shares', [])
    filtered_shares = []
    for share in monitored_shares:
        # 复制分享链接配置，过滤掉last_sync_time字段
        filtered_share = {
            'subject': share.get('subject', ''),
            'enabled': share.get('enabled', True),
            'url': share.get('url', ''),
            'target_folder_id': share.get('target_folder_id', 0),
            'preserve_path': share.get('preserve_path', False),
            'duplicate': share.get('duplicate', 1),
            'password': share.get('password', '')
        }
        filtered_shares.append(filtered_share)
    
    # 只保留后端需要的配置字段
    filtered_config = {
        'api': {},
        'sync': {},
        'monitored_shares': filtered_shares,
        'logging': config.get('logging', {}),
        'scheduler': config.get('scheduler', {})
    }
    
    # API配置：只保留需要的字段
    if 'api' in config:
        api_config = config['api']
        filtered_config['api']['client_id'] = api_config.get('client_id', '')
        filtered_config['api']['client_secret'] = api_config.get('client_secret', '')
        filtered_config['api']['retry_attempts'] = api_config.get('retry_attempts', 3)
        filtered_config['api']['retry_delay'] = api_config.get('retry_delay', 2.0)
        filtered_config['api']['timeout'] = api_config.get('timeout', 30.0)
    
    # 转存配置：只保留需要的字段
    if 'sync' in config:
        sync_config = config['sync']
        filtered_config['sync']['thread_pool_size'] = sync_config.get('thread_pool_size', 5)
        filtered_config['sync']['max_retries'] = sync_config.get('max_retries', 3)
    
    # 确保API配置中不包含api_base_url（向后兼容）
    if 'api' in filtered_config and 'api_base_url' in filtered_config['api']:
        del filtered_config['api']['api_base_url']
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(filtered_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

# 实际的后端服务运行
def backend_service():
    global backend_running, monitor_instance
    backend_running = True
    
    try:
        # 创建监控实例
        monitor_instance = Cloud123Monitor(CONFIG_PATH)
        # 启动定时监控
        monitor_instance.start_scheduled_monitoring()
    except Exception as e:
        print(f"后端服务运行出错: {e}")
        backend_running = False

# API: 获取配置
@app.route('/api/config', methods=['GET'])
def get_config():
    config = read_config()
    return jsonify(config)

# API: 更新配置
@app.route('/api/config', methods=['POST'])
def update_config():
    global monitor_instance
    try:
        new_config = request.json
        
        # 添加空值检查
        if new_config is None:
            new_config = {}
        
        # 获取现有配置
        existing_config = read_config()
        
        # 合并配置 - 使用新配置中的值，但保留现有配置中不存在于新配置中的部分
        merged_config = {**existing_config, **new_config}
        
        # 对于嵌套字典，需要更精细的合并
        for key in existing_config:
            if key in new_config and isinstance(existing_config[key], dict) and isinstance(new_config[key], dict):
                merged_config[key] = {**existing_config[key], **new_config[key]}
        
        write_config(merged_config)
        
        # 清理monitor_state.json中不再存在的分享链接状态
        import json
        import os
        from main import Cloud123Monitor
        
        state_file = 'conf/monitor_state.json'
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                monitor_state = json.load(f)
            
            # 解析合并后的配置中的所有分享链接，生成对应的share_key
            current_share_keys = set()
            
            for share in merged_config.get('monitored_shares', []):
                url = share.get('url', '')
                
                # 从分享链接中提取share_id和URL中的密码
                import re
                # 匹配分享链接格式：https://www.123865.com/s/{share_id}?......
                pattern = r'https?://[^/]+/s/([^?/]+)'
                match = re.search(pattern, url)
                
                if match:
                    share_id = match.group(1)
                    
                    # 从链接中提取密码
                    pwd_pattern = r'pwd=([^&#]+)'
                    pwd_match = re.search(pwd_pattern, url)
                    url_password = pwd_match.group(1) if pwd_match else None
                    
                    # 优先使用用户在表单中提供的密码
                    user_password = share.get('password', '')
                    final_password = user_password if user_password else url_password
                    
                    # 生成share_key
                    share_key = f"{share_id}_{final_password or 'no_pwd'}"
                    current_share_keys.add(share_key)
            
            # 清理不再存在的分享链接状态
            shares_to_remove = [share_key for share_key in monitor_state if share_key not in current_share_keys]
            for share_key in shares_to_remove:
                del monitor_state[share_key]
            
            # 保存清理后的状态
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(monitor_state, f, ensure_ascii=False, indent=2)
        
        # 如果监控实例已经存在，重新加载配置
        if monitor_instance:
            try:
                monitor_instance.reload_config()
                app.logger.info("配置已更新并重新加载")
            except Exception as e:
                app.logger.error(f"重新加载配置失败: {e}")
        
        return jsonify({"message": "配置更新成功", "success": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"配置更新失败: {str(e)}", "success": False}), 500

# API: 启动订阅
@app.route('/api/subscribe/start', methods=['POST'])
def start_subscribe():
    global backend_thread, backend_running
    if not backend_running:
        backend_thread = threading.Thread(target=backend_service)
        backend_thread.daemon = True
        backend_thread.start()
        return jsonify({'success': True, 'message': '订阅服务已启动'})
    return jsonify({'success': False, 'message': '订阅服务已在运行中'})

# API: 停止订阅
@app.route('/api/subscribe/stop', methods=['POST'])
def stop_subscribe():
    global backend_running, monitor_instance
    
    # 如果监控实例存在，停止调度器
    if monitor_instance and hasattr(monitor_instance, 'scheduler_manager'):
        monitor_instance.scheduler_manager.stop()
    
    backend_running = False
    monitor_instance = None
    
    return jsonify({'success': True, 'message': '订阅服务已停止'})

# API: 获取服务状态
@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({'running': backend_running})

# API: 获取监控状态
@app.route('/api/monitor_state', methods=['GET'])
def get_monitor_state():
    import json
    import os
    
    state_file = 'conf/monitor_state.json'
    if os.path.exists(state_file):
        with open(state_file, 'r', encoding='utf-8') as f:
            monitor_state = json.load(f)
        return jsonify(monitor_state)
    return jsonify({})

# API: 立即检查单个分享链接
@app.route('/api/subscribe/check', methods=['POST'])
def check_single_share():
    global monitor_instance
    if not monitor_instance:
        return jsonify({'success': False, 'message': '监控服务未运行'}), 503
    
    try:
        share_url = request.json.get('url')
        if not share_url:
            return jsonify({'success': False, 'message': '分享链接不能为空'}), 400
        
        # 获取配置文件
        config = read_config()
        # 查找匹配的分享链接配置
        share_config = next((s for s in config['monitored_shares'] if s['url'] == share_url), None)
        if not share_config:
            return jsonify({'success': False, 'message': '分享链接不存在'}), 404
        
        # 在新线程中执行检查
        threading.Thread(target=monitor_instance._monitor_share_link, args=(share_config,)).start()
        return jsonify({'success': True, 'message': '立即检查已启动'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'立即检查失败: {str(e)}'}), 500

# 主页面
@app.route('/')
def index():
    return render_template('index.html')

# 在第一个请求前启动订阅服务
# @app.before_first_request
def before_first_request():
    start_subscribe()

if __name__ == '__main__':
    # 在启动Flask应用前，自动启动后台服务
    backend_thread = threading.Thread(target=backend_service)
    backend_thread.daemon = True
    backend_thread.start()
    
    # 禁用模板缓存，确保每次都加载最新的模板
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    app.run(debug=False, host='0.0.0.0', port=24512)