import logging
import re
import time
from typing import Dict, List, Optional, Any, Tuple

import requests

from errors import Cloud123Error, ShareLinkError, FileOperationError, APIError, AuthError


class ShareHandler:
    """
    123云盘分享链接处理器
    """
    
    def __init__(self, api_client=None):
        """
        初始化分享链接处理器
        
        Args:
            api_client: API客户端实例（可选）
        """
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)
        # 创建一个独立的session，用于访问非官方API
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def parse_share_link(self, share_url: str) -> Tuple[str, Optional[str], str]:
        """
        解析分享链接，提取分享key、提取码和host
        
        Args:
            share_url: 分享链接
            
        Returns:
            (分享key, 链接中的提取码, host)
            
        Raises:
            ShareLinkError: 解析分享链接失败
        """
        try:
            self.logger.info(f"解析分享链接: {share_url}")
            
            # 匹配分享链接格式：https://www.123865.com/s/{分享key}?......
            pattern = r'https?://([^/]+)/s/([^?/]+)'
            match = re.search(pattern, share_url)
            
            if not match:
                raise ShareLinkError(f"无效的分享链接格式: {share_url}")
            
            host = match.group(1)
            share_key = match.group(2)
            
            # 从链接中提取密码
            pwd_pattern = r'pwd=([^&#]+)'
            pwd_match = re.search(pwd_pattern, share_url)
            password = pwd_match.group(1) if pwd_match else None
            
            self.logger.info(f"解析分享链接成功: host={host}, share_key={share_key}, password={password}")
            return share_key, password, host
            
        except Exception as e:
            self.logger.error(f"解析分享链接失败: {e}")
            raise ShareLinkError(f"解析分享链接失败: {e}")
    
    def is_valid_share_link(self, share_url: str) -> bool:
        """
        验证分享链接是否有效
        
        Args:
            share_url: 分享链接
            
        Returns:
            链接是否有效
        """
        try:
            self.parse_share_link(share_url)
            return True
        except ShareLinkError:
            return False
    
    def get_share_info(self, share_key: str, share_pwd: Optional[str] = None, host: str = "www.123865.com") -> Dict[str, Any]:
        """
        获取分享信息
        
        Args:
            share_key: 分享key
            share_pwd: 提取码（可选）
            host: 分享链接的host
            
        Returns:
            分享信息
            
        Raises:
            ShareLinkError: 获取分享信息失败
        """
        try:
            self.logger.info(f"获取分享信息，分享key: {share_key}, host: {host}")
            
            # 获取根目录文件列表（用于获取分享信息）
            files, folders = self._get_share_file_list(share_key, "0", share_pwd, host=host)
            
            # 简单构造分享信息
            share_info = {
                "share_key": share_key,
                "share_pwd": share_pwd,
                "total_files": len(files),
                "total_folders": len(folders),
            }
            
            self.logger.info(f"获取分享信息成功: {share_info}")
            return share_info
            
        except Exception as e:
            self.logger.error(f"获取分享信息失败: {e}")
            if isinstance(e, ShareLinkError):
                raise
            else:
                raise ShareLinkError(f"获取分享信息失败: {e}")
    
    def _get_share_file_list(self, share_key: str, 
                           parent_file_id: str = "0", 
                           share_pwd: Optional[str] = None, 
                           page: int = 1,
                           host: str = "www.123865.com") -> Tuple[List[Dict], List[Dict]]:
        """
        获取分享文件列表（非官方接口）
        
        Args:
            share_key: 分享key
            parent_file_id: 父文件夹ID，默认根目录为0
            share_pwd: 提取码（可选）
            page: 页码
            host: 分享链接的host
            
        Returns:
            (文件列表, 文件夹列表)
            
        Raises:
            ShareLinkError: 获取分享文件列表失败
        """
        try:
            self.logger.info(f"获取分享文件列表，分享key: {share_key}, 父文件夹ID: {parent_file_id}, 页码: {page}, host: {host}")
            
            # 构造非官方接口URL
            web_api_url = f"https://{host}"
            url = f"{web_api_url}/b/api/share/get"
            params = {
                "limit": 100,
                "next": "0",
                "orderBy": "file_name",
                "orderDirection": "asc",
                "shareKey": share_key,
                "ParentFileId": parent_file_id,
                "Page": page,
                "event": "homeListFile",
                "operateType": 1,
                "OrderId": "",
                "superAdmin": None,
            }
            
            # 添加提取码（如果有）
            if share_pwd:
                params["SharePwd"] = share_pwd
                self.logger.info(f"添加提取码到参数: SharePwd={share_pwd}")
            else:
                self.logger.info("提取码为空，不添加到参数")
            
            # 构造浏览器请求头
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "Host": host,
                "Referer": f"https://{host}/s/{share_key}?{'pwd='+share_pwd if share_pwd else ''}&notoken=1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
                "platform": "web"
            }
            
            # 发送请求（使用普通浏览器形式，不添加开发者header）
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            self.logger.info(f"url: {response.url}")
            
            if response.status_code != 200:
                raise ShareLinkError(f"获取分享文件列表失败，状态码: {response.status_code}")
            
            result = response.json()
            
            # 检查响应是否成功
            if result.get("code") != 0:
                error_msg = result.get("message", "Unknown error")
                raise ShareLinkError(f"获取分享文件列表失败: {error_msg}")
            
            # 解析文件和文件夹
            data = result.get("data", {})
            file_list = data.get("InfoList", [])
            files = []
            folders = []
            
            for item in file_list:
                if item["Type"] == 0:  # 文件
                    files.append({
                        "file_id": str(item["FileId"]),
                        "name": item["FileName"],
                        "size": item["Size"],
                        "update_at": item["UpdateAt"],
                        "type": item["Type"],
                        "etag": item.get("Etag", "")
                    })
                elif item["Type"] == 1:  # 文件夹
                    folders.append({
                        "folder_id": str(item["FileId"]),
                        "name": item["FileName"],
                        "type": item["Type"],
                        "update_at": item["UpdateAt"]
                    })
            
            # 检查是否有下一页
            next_page = data.get("Next", "-1")
            if next_page != "-1":
                # 递归获取下一页
                next_files, next_folders = self._get_share_file_list(
                    share_key, parent_file_id, share_pwd, page + 1
                )
                files.extend(next_files)
                folders.extend(next_folders)
            
            self.logger.info(f"获取分享文件列表成功，文件数: {len(files)}, 文件夹数: {len(folders)}")
            return files, folders
            
        except Exception as e:
            self.logger.error(f"获取分享文件列表失败: {e}")
            if isinstance(e, ShareLinkError):
                raise
            else:
                raise ShareLinkError(f"获取分享文件列表失败: {e}")
    
    def get_file_list(self, share_key: str, 
                     user_password: Optional[str] = None,
                     link_pwd: Optional[str] = None,
                     current_path: str = "",
                     parent_folder_id: str = "0",
                     host: str = "www.123865.com") -> List[Dict[str, Any]]:
        """
        递归获取分享链接下的所有文件，包括子文件夹
        
        Args:
            share_key: 分享key
            user_password: 用户单独提供的提取码（可选）
            link_pwd: 从链接中提取的提取码（可选，优先级低于用户提供的提取码）
            current_path: 当前路径（用于递归时跟踪路径）
            parent_folder_id: 当前父文件夹ID
            host: 分享链接的host
            
        Returns:
            所有文件的列表，包含完整路径信息
            
        Raises:
            ShareLinkError: 获取文件列表失败
        """
        all_files = []
        
        try:
            # 确定最终使用的提取码：用户提供的提取码优先级高于链接中的提取码
            final_pwd = user_password if user_password else link_pwd
            
            # 获取当前文件夹的文件和子文件夹
            files, folders = self._get_share_file_list(share_key, parent_folder_id, final_pwd, host=host)
            
            # 处理当前文件夹的文件
            for file in files:
                file_path = f"{current_path}/{file['name']}" if current_path else file['name']
                file_info = {
                    "file_id": file["file_id"],
                    "name": file["name"],
                    "path": file_path,
                    "size": file["size"],
                    "update_at": file["update_at"],
                    "type": file["type"],
                    "etag": file.get("etag", ""),
                    "md5": file.get("etag", "")  # 使用etag作为md5值
                }
                all_files.append(file_info)
            
            # 递归处理子文件夹
            for folder in folders:
                folder_path = f"{current_path}/{folder['name']}" if current_path else folder['name']
                
                # 获取子文件夹中的所有文件
                subfolder_files = self.get_file_list(
                    share_key, user_password, link_pwd, folder_path, folder['folder_id'], host=host
                )
                all_files.extend(subfolder_files)
            
            return all_files
            
        except Exception as e:
            self.logger.error(f"递归获取文件列表失败: {e}")
            if isinstance(e, ShareLinkError):
                raise
            else:
                raise ShareLinkError(f"递归获取文件列表失败: {e}")
    
    def save_file_to_cloud(self, share_key: str, 
                          file_id: str, 
                          target_folder_id: str, 
                          file_path: str, 
                          share_pwd: Optional[str] = None,
                          preserve_path: bool = True,
                          file_info: Optional[Dict] = None,
                          duplicate: int = 2) -> Dict[str, Any]:
        """
        保存分享文件到云盘
        
        Args:
            share_key: 分享key
            file_id: 文件ID
            target_folder_id: 目标文件夹ID
            file_path: 文件完整路径
            share_pwd: 提取码（可选）
            preserve_path: 是否保留文件在分享链接中的路径结构
            file_info: 文件详细信息（包含etag和size）
            duplicate: 文件重名处理方式：1-保留两者自动添加后缀，2-直接覆盖
            
        Returns:
            保存结果
            
        Raises:
            ShareLinkError: 保存文件失败
        """
        try:
            self.logger.info(f"保存文件到云盘: {file_path} -> 文件夹ID: {target_folder_id}, preserve_path: {preserve_path}")
            
            if preserve_path:
                # 使用API的containDir参数直接保存包含路径的文件
                self.logger.debug(f"使用API的containDir参数保存文件，包含路径: {file_path}")
                # 调用API客户端保存分享文件
                result = self.api_client.save_shared_file(
                file_id=file_id,
                file_info=file_info,
                target_folder_id=target_folder_id,
                filename=file_path,
                contain_dir=True,
                duplicate=duplicate
            )
            else:
                # 不包含路径，只使用文件名
                filename = file_path.split('/')[-1] if '/' in file_path else file_path
                self.logger.debug(f"不包含路径保存文件: {filename}")
                result = self.api_client.save_shared_file(
                    file_id=file_id,
                    file_info=file_info,
                    target_folder_id=target_folder_id,
                    filename=filename,
                    contain_dir=False,
                    duplicate=duplicate
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"保存文件到云盘失败: {e}")
            raise ShareLinkError(f"保存文件失败: {e}")
    
    def get_all_files_info(self, share_url: str, share_pwd: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取分享链接下的所有文件信息
        
        Args:
            share_url: 分享链接
            share_pwd: 用户单独提供的提取码（可选，优先级高于链接中的提取码）
            
        Returns:
            文件信息列表
            
        Raises:
            ShareLinkError: 获取文件信息失败
        """
        try:
            # 解析分享链接
            share_key, link_pwd, host = self.parse_share_link(share_url)
            
            # 确定最终使用的提取码：用户提供的提取码优先级高于链接中的提取码
            final_pwd = share_pwd if share_pwd is not None else link_pwd
            
            # 获取分享信息（使用最终密码）
            self.get_share_info(share_key, final_pwd, host=host)
            
            # 获取所有文件列表（使用最终密码）
            files = self.get_file_list(share_key, share_pwd, link_pwd, host=host)
            
            self.logger.info(f"获取分享链接下的所有文件成功，共 {len(files)} 个文件")
            return files
            
        except Exception as e:
            self.logger.error(f"获取分享链接下的所有文件信息失败: {e}")
            if isinstance(e, ShareLinkError):
                raise
            else:
                raise ShareLinkError(f"获取分享链接下的所有文件信息失败: {e}")