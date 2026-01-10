#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
123云盘分享监控程序
监控123云盘分享链接的内容，若有更新则转存更新文件到自己的云盘中
"""

import argparse
import sys
import time
import json
import logging
from typing import Dict, List, Optional, Any
import concurrent.futures
import threading

from config.logging_config import LoggingConfig
from config.config_manager import ConfigManager
from api.api_client import Cloud123APIClient
from api.share_handler import ShareHandler
from sync.file_comparator import FileComparator
from sync.file_syncer import FileSyncer
from scheduler.manager import SchedulerManager
from errors import Cloud123Error, ConfigError, ShareLinkError, FileOperationError


class Cloud123Monitor:
    """
    123云盘分享监控主程序类
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化监控程序
        
        Args:
            config_path: 配置文件路径（可选）
        """
        # 先加载配置，然后再设置日志
        if config_path is None:
            self.config_manager = ConfigManager()
        else:
            self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        
        # 使用加载的配置初始化日志
        LoggingConfig.setup_logging(self.config.get('logging', {}))
        
        self.logger = logging.getLogger(__name__)
        
        try:
            # 初始化API客户端
            self.api_client = Cloud123APIClient(self.config.get('api', {}))
            
            # 初始化分享处理器
            self.share_handler = ShareHandler(self.api_client)
            
            # 初始化文件比较器
            self.file_comparator = FileComparator()
            
            # 初始化文件同步器
            self.file_syncer = FileSyncer(self.api_client, self.file_comparator, self.share_handler)
            
            # 初始化调度器
            self.scheduler_manager = SchedulerManager()
            
            # 设置令牌缓存文件路径
            self.token_cache_file = self.config.get('sync', {}).get('token_cache_file', 'conf/token_cache.json')
            
            # 保存监控状态的缓存文件路径
            self.state_cache_file = self.config.get('sync', {}).get('state_cache_file', 'conf/monitor_state.json')
            self.monitor_state = self._load_monitor_state()
            
            # 加载令牌缓存
            self._load_token_cache()
            
            # 设置令牌更新回调
            self.api_client.token_update_callback = self._save_token_cache
            
            # 加载线程池配置
            self.thread_pool_size = self.config.get('sync', {}).get('thread_pool_size', 0)
            
            # 初始化线程锁，保护共享资源
            self.monitor_state_lock = threading.Lock()
            
            self.logger.info("监控程序初始化成功")
            
        except Exception as e:
            self.logger.error(f"监控程序初始化失败: {e}")
            raise
    
    def _generate_share_key(self, share_id: str, share_pwd: Optional[str]) -> str:
        """
        生成分享链接的唯一标识
        
        Args:
            share_id: 分享ID
            share_pwd: 分享密码
            
        Returns:
            分享链接的唯一标识
        """
        return f"{share_id}_{share_pwd or 'no_pwd'}"
    
    def _load_monitor_state(self) -> Dict[str, Dict]:
        """
        加载监控状态缓存
        
        Returns:
            监控状态字典
        """
        try:
            with open(self.state_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.logger.info("未找到状态缓存文件，将创建新的")
            return {}
    
    def _save_monitor_state(self):
        """
        保存监控状态缓存
        """
        try:
            with self.monitor_state_lock:
                with open(self.state_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.monitor_state, f, ensure_ascii=False, indent=2)
            self.logger.debug("监控状态已保存")
        except Exception as e:
            self.logger.error(f"保存监控状态失败: {e}")

    def _transfer_file(self, file_info: Dict[str, Any], share_id: str, share_pwd: Optional[str], 
                       target_folder_id: str, preserve_path: bool, duplicate: int = 2) -> None:
        """
        转存文件到云盘
        
        Args:
            file_info: 文件信息
            share_id: 分享ID
            share_pwd: 分享密码
            target_folder_id: 目标文件夹ID
            preserve_path: 是否保留路径
            duplicate: 文件重名处理方式：1-保留两者自动添加后缀，2-直接覆盖
        """
        try:
            self.logger.info(f"开始转存文件: {file_info['name']}")
            
            # 使用file_syncer执行转存操作
            self.file_syncer.sync_file(
                share_id=share_id,
                file_id=file_info['file_id'],
                target_folder_id=target_folder_id,
                share_pwd=share_pwd,
                file_path=file_info['path'],
                preserve_path=preserve_path,
                file_info=file_info,  # 传递完整的文件信息
                duplicate=duplicate  # 传递文件重名处理方式
            )
            
            self.logger.info(f"文件转存成功: {file_info['name']}")
        except Exception as e:
            self.logger.error(f"文件转存失败: {file_info['name']}, 错误: {e}")
            raise

    def reload_config(self):
        """
        重新加载配置文件并更新内存中的配置
        """
        try:
            # 重新加载配置文件
            self.config_manager.config = self.config_manager._load_config()
            self.config = self.config_manager.config
            
            # 更新日志配置
            LoggingConfig.setup_logging(self.config.get('logging', {}))
            
            # 更新API客户端配置
            self.api_client.update_config(self.config.get('api', {}))
            
            # 更新线程池配置
            self.thread_pool_size = self.config.get('sync', {}).get('thread_pool_size', 0)
            
            # 更新调度器配置
            if self.scheduler_manager.running:
                # 读取新的监控间隔
                monitor_interval_minutes = self.config.get('scheduler', {}).get('interval_minutes', 60)
                monitor_interval_seconds = monitor_interval_minutes * 60
                
                # 直接更新任务间隔，不删除重新添加，保持计时状态
                success = self.scheduler_manager.update_task_interval('monitor_all_shares', monitor_interval_seconds)
                
                if success:
                    self.logger.info(f"调度器配置已更新，新的监控间隔: {monitor_interval_seconds}秒")
                else:
                    self.logger.warning(f"更新调度器配置失败，可能是任务不存在")
            
            # 重新加载监控状态缓存，确保与最新的monitor_state.json文件一致
            self.monitor_state = self._load_monitor_state()
            
            self.logger.info("配置重新加载成功")
            return True
        except Exception as e:
            self.logger.error(f"重新加载配置失败: {e}")
            return False

    def _load_token_cache(self):
        """
        加载令牌缓存
        """
        try:
            with open(self.token_cache_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            # 更新API客户端的令牌信息
            if 'access_token' in token_data:
                self.api_client.access_token = token_data['access_token']
            if 'token_expires_at' in token_data:
                self.api_client.token_expires_at = token_data['token_expires_at']
            
            self.logger.info("令牌缓存加载成功")
        except (FileNotFoundError, json.JSONDecodeError):
            self.logger.info("未找到令牌缓存文件，将创建新的")
        except Exception as e:
            self.logger.error(f"加载令牌缓存失败: {e}")
    
    def _save_token_cache(self):
        """
        保存令牌缓存
        """
        try:
            token_data = {
                'access_token': self.api_client.access_token,
                'token_expires_at': self.api_client.token_expires_at
            }
            
            with open(self.token_cache_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug("令牌缓存已保存")
        except Exception as e:
            self.logger.error(f"保存令牌缓存失败: {e}")
    
    def _monitor_share_link(self, share_config: Dict[str, Any]) -> None:
        """
        监控单个分享链接
        
        Args:
            share_config: 分享链接配置信息
        """
        # 检查是否启用该分享链接
        if not share_config.get("enabled", True):
            self.logger.info(f"分享链接 {share_config['url']} 已禁用，跳过监控")
            return
            
        url = share_config["url"]
        target_folder_id = share_config["target_folder_id"]
        preserve_path = share_config.get("preserve_path", True)  # 默认保留路径
        duplicate = share_config.get("duplicate", 2)  # 默认直接覆盖
        
        try:
            # 解析分享链接
            share_id, link_pwd, host = self.share_handler.parse_share_link(url)
            
            # 获取用户单独提供的提取码
            user_password = share_config.get("password")
            
            # 确定最终使用的提取码：用户提供的提取码优先级高于链接中的提取码
            final_pwd = user_password if user_password else link_pwd
            
            # 记录最终使用的提取码
            self.logger.info(f"确定最终使用的提取码: {final_pwd} (user_password: {user_password}, link_pwd: {link_pwd})")
            
            # 生成分享链接的唯一标识（使用最终密码）
            share_key = self._generate_share_key(share_id, final_pwd)
            
            # 获取文件列表（使用最终密码）
            file_list = self.share_handler.get_file_list(share_id, user_password, link_pwd, host=host)
            
            # 获取当前监控状态（使用锁保护）
            with self.monitor_state_lock:
                monitor_state = self.monitor_state.get(share_key, {})
            
            # 判断文件是否有更新
            updated_files = self.file_comparator.get_files_to_sync(file_list, monitor_state.get('files', []))
            
            if updated_files:
                self.logger.info(f"分享链接 {url} 有 {len(updated_files)} 个文件需要更新")
                
                # 下载并转存更新的文件
                success_count = 0  # 记录成功转存的文件数量
                
                # 基于当前已同步的文件创建路径到文件信息的映射
                current_file_map = {file_info.get('path', ''): file_info 
                                  for file_info in monitor_state.get('files', [])}
                
                for file_info in updated_files:
                    try:
                        self._transfer_file(file_info, share_id, final_pwd, target_folder_id, preserve_path, duplicate)
                        success_count += 1  # 成功转存，计数器加1
                        
                        # 转存成功后立即更新监控状态
                        # 更新或添加当前文件到映射中
                        # 记录转存时间
                        file_info['synced_at'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                        current_file_map[file_info.get('path', '')] = file_info
                        
                        # 从映射中构建更新后的文件列表
                        current_file_list = list(current_file_map.values())
                        
                        # 更新监控状态
                        with self.monitor_state_lock:
                            self.monitor_state[share_key] = {
                                "last_monitor_time": time.time(),
                                "last_sync_time": time.time(),  # 添加最后转存时间
                                "files": current_file_list,
                                "last_synced_files_count": success_count  # 记录上次成功转存的文件数量
                            }
                        self._save_monitor_state()
                        self.logger.info(f"文件 {file_info['name']} 转存成功并更新监控状态")
                    except Exception as e:
                        self.logger.error(f"转存文件失败: {file_info['name']}, 错误: {e}")
                        continue
                
                self.logger.info(f"分享链接 {url} 监控状态已更新")
            else:
                self.logger.info(f"分享链接 {url} 没有文件更新")
                # 即使没有更新，也更新最后监控时间
                with self.monitor_state_lock:
                    # 创建新的监控状态对象，保留原有的last_sync_time字段
                    new_state = {
                        "last_monitor_time": time.time(),
                        "files": monitor_state.get("files", []),
                        "last_synced_files_count": 0  # 没有文件更新，设置为0
                    }
                    # 如果原状态中有last_sync_time字段，保留它
                    if "last_sync_time" in monitor_state:
                        new_state["last_sync_time"] = monitor_state["last_sync_time"]
                    
                    self.monitor_state[share_key] = new_state
                self._save_monitor_state()
                
        except ShareLinkError as e:
            self.logger.error(f"分享链接处理错误 {url}: {e}")
        except Exception as e:
            self.logger.error(f"监控分享链接失败 {url}: {e}")
    
    def monitor_all(self):
        """
        监控所有配置的分享链接
        """
        monitored_shares = self.config.get('monitored_shares', [])
        
        if not monitored_shares:
            self.logger.warning("没有配置要监控的分享链接")
            return
        
        self.logger.info(f"开始监控 {len(monitored_shares)} 个分享链接")
        self.logger.info(f"线程池配置: thread_pool_size={self.thread_pool_size}")
        
        if self.thread_pool_size == 0:
            # 不启用多线程，顺序执行
            self.logger.info("使用单线程模式监控分享链接")
            for share_config in monitored_shares:
                try:
                    self._monitor_share_link(share_config)
                    # 避免请求过于频繁
                    time.sleep(1)
                except Exception as e:
                    self.logger.error(f"监控分享链接失败: {e}")
        else:
            # 启用多线程
            max_workers = None if self.thread_pool_size == -1 else self.thread_pool_size
            self.logger.info(f"使用多线程模式监控分享链接，线程数: {max_workers if max_workers else '不限制'}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有分享链接的监控任务
                futures = [executor.submit(self._monitor_share_link, share_config) 
                          for share_config in monitored_shares]
                
                # 等待所有任务完成
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        self.logger.error(f"监控分享链接失败: {e}")
    
    def start_scheduled_monitoring(self):
        """
        启动定时监控
        """
        # 检查调度器是否已经在运行，如果是则不再执行任何操作
        if self.scheduler_manager.running:
            self.logger.info("调度器已经在运行中，跳过启动")
            return
        
        # 读取配置的监控间隔（分钟），并转换为秒
        monitor_interval_minutes = self.config.get('scheduler', {}).get('interval_minutes', 60)  # 默认1小时
        monitor_interval_seconds = monitor_interval_minutes * 60
        
        def monitor_task():
            self.logger.info("定时监控任务开始执行")
            try:
                self.monitor_all()
            except Exception as e:
                self.logger.error(f"定时监控任务执行失败: {e}")
        
        # 添加定时任务
        self.scheduler_manager.add_task(
            task_id='monitor_all_shares',
            task_func=monitor_task,
            interval_seconds=monitor_interval_seconds,
            task_name='监控所有分享链接'
        )
        
        # 启动调度器
        self.scheduler_manager.start()
        
        self.logger.info(f"定时监控已启动，监控间隔: {monitor_interval_seconds}秒")
        # 立即执行一次监控
        self.monitor_all()
    
    def run_once(self):
        """
        执行一次监控
        """
        try:
            self.monitor_all()
            return 0
        except Exception as e:
            self.logger.error(f"单次监控执行失败: {e}")
            return 1
    
    def add_monitored_share(self, share_url: str, target_folder_id: str):
        """
        添加要监控的分享链接
        
        Args:
            share_url: 分享链接
            target_folder_id: 目标文件夹ID
        """
        try:
            # 验证分享链接
            share_id, share_pwd, host = self.share_handler.parse_share_link(share_url)
            if not self.share_handler.is_valid_share_link(share_url):
                raise ShareLinkError(f"无效的分享链接: {share_url}")
            
            # 验证目标文件夹ID
            try:
                folder_info = self.api_client.get_folder_info(target_folder_id)
                self.logger.info(f"验证目标文件夹成功: {folder_info.get('folderName', '')}")
            except Exception as e:
                raise FileOperationError(f"无效的目标文件夹ID: {target_folder_id}, 原因: {e}")
            
            # 添加到配置
            self.config_manager.add_monitored_share(share_url, target_folder_id)
            self.config = self.config_manager.config  # 更新配置
            
            self.logger.info(f"成功添加监控分享链接: {share_url}")
            return True
        except Exception as e:
            self.logger.error(f"添加监控分享链接失败: {e}")
            raise
    
    def remove_monitored_share(self, share_url: str):
        """
        移除指定的分享链接监控
        
        Args:
            share_url: 要移除的分享链接
        """
        self.logger.info(f"移除分享链接监控: {share_url}")
        try:
            # 更新配置文件
            monitored_shares = self.config.get('monitored_shares', [])
            new_shares = [share for share in monitored_shares if share['url'] != share_url]
            self.config.set('monitored_shares', new_shares)
            self.config.save()
            
            # 更新监控状态
            # 找到匹配的分享链接配置
            share_config = next((share for share in monitored_shares if share['url'] == share_url), None)
            if share_config:
                # 解析分享链接生成share_key
                import re
                # 匹配分享链接格式：https://www.123865.com/s/{share_id}?......
                pattern = r'https?://[^/]+/s/([^?/]+)'
                match = re.search(pattern, share_url)
                
                if match:
                    share_id = match.group(1)
                    
                    # 从链接中提取密码
                    pwd_pattern = r'pwd=([^&#]+)'
                    pwd_match = re.search(pwd_pattern, share_url)
                    url_password = pwd_match.group(1) if pwd_match else None
                    
                    # 优先使用用户在配置中提供的密码
                    user_password = share_config.get('password', '')
                    final_password = user_password if user_password else url_password
                    
                    # 生成share_key
                    share_key = f"{share_id}_{final_password or 'no_pwd'}"
                    
                    # 从监控状态中删除
                    if share_key in self.monitor_state:
                        del self.monitor_state[share_key]
                        self._save_monitor_state()
            
            self.logger.info(f"分享链接监控已移除: {share_url}")
        except Exception as e:
            self.logger.error(f"移除分享链接监控失败: {e}")


def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(description="123网盘分享链接监控工具")
    parser.add_argument('command', choices=['run', 'once'], help="命令：run-启动监控，once-运行一次")
    parser.add_argument('-c', '--config', help="配置文件路径")
    return parser.parse_args()


def main():
    """
    主函数
    """
    # 解析命令行参数
    args = parse_arguments()
    
    # 初始化监控程序
    try:
        monitor = Cloud123Monitor(args.config)
        
        # 根据命令执行不同操作
        if args.command == 'run':
            # 启动定时监控
            monitor.start_scheduled_monitoring()
        elif args.command == 'once':
            # 运行一次监控
            monitor.run_once()
            
    except Exception as e:
        logging.error(f"程序运行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()