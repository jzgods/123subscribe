import logging
import time
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

from errors import Cloud123Error, AuthError, APIError, RateLimitError, RetryExhaustedError
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


class Cloud123APIClient:
    """
    123云盘API客户端
    """
    
    # API基础URL
    API_BASE_URL = "https://open-api.123pan.com"
    
    # Web API基础URL（非官方接口）
    WEB_API_URL = "https://www.123865.com"
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化API客户端
        
        Args:
            config: 配置字典，包含client_id、client_secret等信息
        """
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.access_token = config.get('token')
        self.token_expires_at = config.get('token_expires_at')
        
        # 添加timeout配置，默认为30秒
        self.timeout = config.get('timeout', 30)
        
        # 令牌更新回调
        self.token_update_callback = None
        
        self.logger = logging.getLogger(__name__)
        
        # 初始化会话
        self.session = requests.Session()
        
        # 设置重试策略
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT"],
            raise_on_status=True,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.logger.info("API客户端初始化成功")
    
    @property
    def web_api_url(self):
        """获取Web API URL"""
        return self.WEB_API_URL
    
    def update_config(self, config: Dict[str, Any]):
        """
        更新API客户端配置
        
        Args:
            config: 新的配置字典
        """
        if 'client_id' in config:
            self.client_id = config['client_id']
        if 'client_secret' in config:
            self.client_secret = config['client_secret']
        if 'timeout' in config:
            self.timeout = config['timeout']
        
        # 更新重试策略
        if 'retry_attempts' in config or 'retry_delay' in config:
            retry_attempts = config.get('retry_attempts', 3)
            
            retry_strategy = Retry(
                total=retry_attempts,
                status_forcelist=[429, 500, 502, 503, 504],
                backoff_factor=config.get('retry_delay', 1),
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT"],
                raise_on_status=True,
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            
            # 重新挂载适配器
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
        
        self.logger.info("API客户端配置已更新")

    def _is_token_expired(self) -> bool:
        """
        检查令牌是否过期
        
        Returns:
            令牌是否过期
        """
        if not self.token_expires_at:
            return True
        
        return time.time() >= self.token_expires_at
    
    def get_access_token(self, client_id: Optional[str] = None, 
                        client_secret: Optional[str] = None) -> Dict[str, Any]:
        """
        获取访问令牌
        
        Args:
            client_id: 客户端ID
            client_secret: 客户端密钥
            
        Returns:
            包含访问令牌的字典
            
        Raises:
            AuthError: 认证失败
        """
        try:
            client_id = client_id or self.client_id
            client_secret = client_secret or self.client_secret
            
            if not client_id or not client_secret:
                raise AuthError("缺少客户端ID或密钥")
            
            url = f"{self.API_BASE_URL}/api/v1/access_token"
            payload = {
                "clientID": client_id,
                "clientSecret": client_secret
            }
            
            headers = {
                "Platform": "open_platform",
                "Content-Type": "application/json"
            }
            
            response = self.session.post(url, json=payload, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                raise AuthError(f"获取令牌失败，状态码: {response.status_code}")
            
            result = response.json()
            
            if result.get('code') != 0:
                raise AuthError(f"获取令牌失败: {result.get('message', 'Unknown error')}")
            
            data = result.get('data', {})
            if 'accessToken' not in data:
                raise AuthError(f"获取令牌失败: 响应中缺少accessToken")
            
            # 保存令牌信息
            self.access_token = data['accessToken']
            
            # 计算过期时间
            if 'expiredAt' in data:
                # 解析ISO格式的时间字符串
                try:
                    expired_at = datetime.fromisoformat(data['expiredAt'].replace('Z', '+00:00'))
                    self.token_expires_at = expired_at.timestamp()
                except ValueError:
                    self.logger.warning(f"无法解析expiredAt: {data['expiredAt']}")
                    self.token_expires_at = time.time() + 3600  # 默认1小时后过期
            
            # 调用令牌更新回调
            if self.token_update_callback:
                try:
                    self.token_update_callback()
                except Exception as e:
                    self.logger.error(f"执行令牌更新回调失败: {e}")
            
            self.logger.info("获取访问令牌成功")
            return result
            
        except Exception as e:
            self.logger.error(f"获取访问令牌失败: {e}")
            if isinstance(e, AuthError):
                raise
            else:
                raise AuthError(f"获取访问令牌失败: {e}")
    
    def create_folder(self, parent_file_id: str, folder_name: str) -> Dict[str, Any]:
        """
        创建文件夹
        
        Args:
            parent_file_id: 父文件夹ID，上传到根目录时填写 0
            folder_name: 文件夹名称
            
        Returns:
            创建结果
            
        Raises:
            APIError: 创建文件夹失败
        """
        try:
            self._ensure_token()
            
            url = f"{self.API_BASE_URL}/upload/v1/file/mkdir"
            data = {
                "name": folder_name,
                "parentID": parent_file_id
            }
            
            headers = {
                "Content-Type": "application/json",
                "Platform": "open_platform",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = self.session.post(url, json=data, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                raise APIError(f"创建文件夹失败，状态码: {response.status_code}, 响应: {response.text}")
            
            result = response.json()
            
            if result.get('code') != 0:
                raise APIError(f"创建文件夹失败: {result.get('message', 'Unknown error')}")
            
            self.logger.info(f"创建文件夹成功: {folder_name} (父ID: {parent_file_id})")
            return result
            
        except Exception as e:
            self.logger.error(f"创建文件夹失败: {e}")
            if isinstance(e, APIError):
                raise
            else:
                raise APIError(f"创建文件夹失败: {e}")
    
    def _ensure_token(self) -> None:
        """
        确保令牌有效
        """
        if self._is_token_expired():
            self.logger.info("令牌已过期，重新获取令牌")
            self.get_access_token()

    def save_shared_file(self, file_id, file_info, target_folder_id, filename=None, contain_dir=True, duplicate=2):
        """
        保存分享文件到云盘
        file_id: 文件ID
        file_info: 文件信息字典，包含etag和size
        target_folder_id: 目标文件夹ID
        filename: 保存的文件名，如果不提供则使用file_id
        contain_dir: 是否包含目录结构
        duplicate: 文件重名处理方式：1-保留两者自动添加后缀，2-直接覆盖
        """
        try:
            self._ensure_token()
            
            # 使用与上传相同的接口URL
            url = f"{self.API_BASE_URL}/upload/v2/file/create"
            
            # 从file_info中获取必要的参数
            etag = file_info.get("etag") or ""  # 使用文件的etag值
            size = file_info.get("size", 0)       # 使用文件的实际大小
            
            # 清理文件名，移除不允许的字符
            if filename:
                # 移除不允许的字符："\/*?|><
                # 当contain_dir=True时，保留斜杠/作为路径分隔符
                invalid_chars = '"\\:*?|><'
                if not contain_dir:
                    invalid_chars += '/'
                
                for char in invalid_chars:
                    filename = filename.replace(char, '')
                # 确保文件名长度不超过256个字符
                if len(filename) > 256:
                    import os
                    name_part, ext_part = os.path.splitext(filename)
                    filename = name_part[:256 - len(ext_part)] + ext_part
            
            # 构建API请求参数
            data = {
                "parentFileID": int(target_folder_id),  # 确保使用整数类型
                "filename": filename if filename else file_id,
                "etag": etag,  # 使用文件的etag值
                "size": size,    # 使用文件的实际大小
                "duplicate": duplicate,  # 文件重名处理方式：1-保留两者自动添加后缀，2-直接覆盖
                "containDir": contain_dir  # 使用传入的参数，不再硬编码为False
                # 移除shareKey、fileId和sharePwd参数，这些在该API中不需要
            }
            
            headers = {
                "Content-Type": "application/json",
                "Platform": "open_platform",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            # 添加详细日志
            self.logger.debug(f"保存分享文件请求: URL={url}, data={json.dumps(data, ensure_ascii=False)}, headers={headers}")
            
            response = self.session.post(url, json=data, headers=headers, timeout=self.timeout)
            
            self.logger.debug(f"保存分享文件响应: 状态码={response.status_code}, 响应内容={response.text}")
            
            if response.status_code != 200:
                raise APIError(f"保存分享文件失败，状态码: {response.status_code}, 响应: {response.text}")
            
            result = response.json()
            
            if result.get('code') != 0:
                raise APIError(f"保存分享文件失败: {result.get('message', 'Unknown error')}")
            
            self.logger.info(f"保存分享文件成功: {file_id} -> {target_folder_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"保存分享文件失败: {e}")
            if isinstance(e, APIError):
                raise
            else:
                raise APIError(f"保存分享文件失败: {e}")