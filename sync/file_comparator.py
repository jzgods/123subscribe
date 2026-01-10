import logging
from typing import Dict, List, Any

class FileComparator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_files_to_sync(self, source_files: List[Dict[str, Any]], target_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        获取需要同步的文件列表
        
        基于文件MD5值比较，找出新增或更新的文件
        
        Args:
            source_files: 源文件列表（分享链接中的文件）
            target_files: 目标文件列表（上次监控的文件）
            
        Returns:
            需要同步的文件列表
        """
        self.logger.info(f"比较文件列表，源文件数: {len(source_files)}, 目标文件数: {len(target_files)}")
        
        # 映射目标文件路径到文件信息
        target_file_map = {file_info.get('path', ''): file_info for file_info in target_files}
        
        files_to_sync = []
        
        for source_file in source_files:
            # 跳过文件夹
            if source_file.get('type') == 1:
                continue
            
            file_path = source_file.get('path', '')
            source_md5 = source_file.get('md5', '')
            
            if file_path not in target_file_map:
                # 目标文件不存在，需要同步
                files_to_sync.append(source_file)
                self.logger.debug(f"新增文件: {file_path}")
            else:
                # 目标文件存在，比较MD5值
                target_file = target_file_map[file_path]
                target_md5 = target_file.get('md5', '')
                
                if source_md5 != target_md5:
                    # MD5值不同，文件已更新，需要同步
                    files_to_sync.append(source_file)
                    self.logger.debug(f"更新文件: {file_path} (MD5: {source_md5} -> {target_md5})")
        
        self.logger.info(f"找到{len(files_to_sync)}个需要同步的文件（新增/更新）")
        return files_to_sync
    
    def group_files_by_directory(self, files: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        按目录分组文件
        
        Args:
            files: 文件列表
            
        Returns:
            按目录路径分组的文件字典
        """
        grouped_files = {}
        
        for file_info in files:
            # 获取文件路径
            file_path = file_info.get('path', '')
            
            # 提取目录部分
            if '/' in file_path:
                directory = file_path.rsplit('/', 1)[0]
            else:
                directory = ''  # 根目录
            
            # 将文件添加到对应目录
            if directory not in grouped_files:
                grouped_files[directory] = []
            grouped_files[directory].append(file_info)
        
        return grouped_files