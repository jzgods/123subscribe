import logging
import time
from typing import Dict, Optional

class FileSyncer:
    def __init__(self, api_client, file_comparator, share_handler):
        self.api_client = api_client
        self.file_comparator = file_comparator
        self.share_handler = share_handler
        self.logger = logging.getLogger(__name__)
    
    def sync_file(self, share_id: str, 
                  file_id: str, 
                  target_folder_id: str, 
                  share_pwd: Optional[str] = None, 
                  retries: int = 3,
                  file_path: Optional[str] = None,
                  preserve_path: bool = True,
                  file_info: Optional[Dict] = None,
                  duplicate: int = 2):
        """同步单个文件
        
        Args:
            share_id: 分享ID
            file_id: 文件ID
            target_folder_id: 目标文件夹ID
            share_pwd: 分享密码
            retries: 失败重试次数
            file_path: 文件完整路径
            preserve_path: 是否保留文件路径结构
            file_info: 文件详细信息（包含etag和size）
            duplicate: 文件重名处理方式：1-保留两者自动添加后缀，2-直接覆盖
        """
        self.logger.info(f"开始同步文件，文件ID: {file_id}, preserve_path: {preserve_path}")
        
        # 检查必要参数
        if not file_id or not share_id:
            error_msg = f"缺少必要参数: file_id或share_id"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 尝试保存文件
        for attempt in range(retries + 1):
            try:
                if preserve_path and file_path:
                    # 调用share_handler保存文件并保留路径
                    result = self.share_handler.save_file_to_cloud(
                        share_key=share_id,
                        file_id=file_id,
                        target_folder_id=target_folder_id,
                        file_path=file_path,
                        share_pwd=share_pwd,
                        file_info=file_info,  # 传递文件信息
                        duplicate=duplicate  # 传递文件重名处理方式
                    )
                else:
                    # 直接保存文件到目标文件夹
                    filename = None
                    if file_path:
                        # 从file_path中提取文件名
                        filename = file_path.split('/')[-1] if '/' in file_path else file_path
                    
                    result = self.api_client.save_shared_file(
                        file_id=file_id,
                        file_info=file_info,
                        target_folder_id=target_folder_id,
                        filename=filename,
                        contain_dir=False,
                        duplicate=duplicate  # 传递文件重名处理方式
                    )
                
                # 检查结果
                if result and result.get('code') == 0:
                    self.logger.info(f"文件同步成功，文件ID: {file_id}")
                    return result
                else:
                    error_msg = f"保存文件返回非成功状态: {result}"
                    self.logger.error(error_msg)
            except Exception as e:
                error_msg = f"同步文件失败: {str(e)}"
                self.logger.error(f"{error_msg}, 第{attempt + 1}次尝试")
                
                # 如果不是最后一次尝试，等待一段时间后重试
                if attempt < retries:
                    wait_time = (attempt + 1) * 2  # 指数退避策略
                    self.logger.info(f"{wait_time}秒后重试...")
                    time.sleep(wait_time)
        
        # 所有尝试都失败
        raise Exception(f"文件同步失败，已尝试{retries + 1}次: {error_msg}")