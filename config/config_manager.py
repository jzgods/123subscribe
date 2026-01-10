import yaml
import os
import logging
from typing import Dict, Any, List, Optional

# 引入自定义错误类
from errors import ConfigError

class ConfigManager:
    def __init__(self, config_path: str = './conf/config.yaml'):
        self.config_path = config_path
        self._logger = None  # 显式初始化_logger
        self.config = self._load_config()
        self._validate_config()
    
    @property
    def logger(self):
        """获取logger实例，延迟初始化"""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        # 如果配置文件不存在，则创建默认配置文件
        if not os.path.exists(self.config_path):
            default_config = self._get_default_config()
            self._save_config(default_config)
            self.logger.warning(f"配置文件不存在，已创建默认配置文件: {self.config_path}")
            return default_config
        
        # 读取配置文件
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            # 确保返回的是字典，如果文件为空或格式不正确，返回默认配置
            if config is None:
                config = self._get_default_config()
                self._save_config(config)
                self.logger.warning(f"配置文件为空，已使用默认配置并保存")
                return config
            
            # 从API配置中移除api_base_url（如果存在）
            if "api" in config and "api_base_url" in config["api"]:
                del config["api"]["api_base_url"]
                
            # 确保sync部分只包含需要的配置项
            if "sync" in config:
                # 移除不需要的配置项
                for key in ["chunk_size", "download_threads", "save_path", "transfer_interval"]:
                    if key in config["sync"]:
                        del config["sync"][key]
                # 确保必要的配置项存在
                if "max_retries" not in config["sync"]:
                    config["sync"]["max_retries"] = 3
                if "thread_pool_size" not in config["sync"]:
                    config["sync"]["thread_pool_size"] = 5
                
            return config
        except yaml.YAMLError as e:
            self.logger.error(f"配置文件解析错误: {e}")
            raise ConfigError(f"配置文件格式错误: {e}")
        except Exception as e:
            self.logger.error(f"读取配置文件失败: {e}")
            raise ConfigError(f"加载配置失败: {e}")
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """保存配置文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")  # 使用print而不是logger，避免循环依赖
            raise ConfigError(f"保存配置失败: {e}")
    
    def save_config(self):
        """
        保存配置到文件
        只保存用户需要提供的配置项，不保存程序运行时生成的access_token等信息
        """
        try:
            # 只保存用户需要提供的配置项，不保存程序运行时生成的access_token等信息
            config_to_save = {
                'api': {
                    'client_id': self.config['api']['client_id'],
                    'client_secret': self.config['api']['client_secret'],
                    'retry_attempts': self.config['api']['retry_attempts'],
                    'retry_delay': self.config['api']['retry_delay'],
                    'timeout': self.config['api']['timeout']
                },
                'sync': {
                    'max_retries': self.config['sync'].get('max_retries', 3),
                    'thread_pool_size': self.config['sync'].get('thread_pool_size', 5)
                },
                'monitored_shares': self.config.get('monitored_shares', []),
                'logging': self.config.get('logging', {}),
                'scheduler': self.config.get('scheduler', {})
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_to_save, f, allow_unicode=True, default_flow_style=False, indent=2)
            self.logger.debug(f"配置已保存到 {self.config_path}")
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            raise ConfigError(f"保存配置失败: {e}")

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "api": {
                "client_id": "",
                "client_secret": "",
                "retry_attempts": 3,
                "retry_delay": 2.0,
                "timeout": 30.0
            },
            "sync": {
                "max_retries": 3,  # 最大重试次数
                "thread_pool_size": 5  # 线程池大小，0表示不启用多线程，-1表示不限制，>0表示具体线程数
            },
            "monitored_shares": [],
            "logging": {
                "level": "INFO",
                "log_file": "./logs/123subscrib.log",
                "max_bytes": 10485760,  # 10MB
                "backup_count": 5
            },
            "scheduler": {
                "interval_minutes": 60,
                "max_history": 1000
            }
        }
    
    def _validate_config(self) -> None:
        """
        验证配置文件的有效性
        """
        try:
            # 检查必要的配置项
            required_sections = ["sync", "monitored_shares", "logging", "scheduler"]
            for section in required_sections:
                if section not in self.config:
                    raise ConfigError(f"配置文件缺少必要的部分: {section}")
            
            # API配置部分可以为空，因为API客户端会使用硬编码的配置
            if "api" not in self.config:
                self.config["api"] = {
                    "client_id": "",
                    "client_secret": "",
                    "retry_attempts": 3,
                    "retry_delay": 2.0,
                    "timeout": 30.0
                }
            
            # 验证监控分享链接配置
            if not isinstance(self.config["monitored_shares"], list):
                raise ConfigError("monitored_shares必须是一个列表")
            
            # 验证每个分享链接是否包含必要字段
            for share in self.config["monitored_shares"]:
                required_share_fields = ["url", "enabled", "target_folder_id"]
                for field in required_share_fields:
                    if field not in share or share[field] is None:
                        raise ConfigError(f"分享链接配置缺少必要的字段: {field}")
        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"配置验证失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持点号分隔的嵌套键"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            self.logger.debug(f"配置项不存在: {key}，使用默认值: {default}")
            return default
    
    def set(self, key: str, value: Any) -> None:
        """设置配置项，支持点号分隔的嵌套键"""
        keys = key.split('.')
        config = self.config
        
        # 导航到目标键的父级
        try:
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # 设置值
            config[keys[-1]] = value
            
            # 保存配置
            self._save_config(self.config)
            self.logger.info(f"已更新配置项: {key} = {value}")
        except Exception as e:
            self.logger.error(f"设置配置项失败: {key}, {e}")
            raise ConfigError(f"更新配置失败: {e}")
    
    def get_api_config(self) -> Dict[str, Any]:
        """获取API配置，不包含api_base_url"""
        api_config = self.config.get("api", {})
        # 移除api_base_url配置项（如果存在）
        if "api_base_url" in api_config:
            api_config.pop("api_base_url")
        return api_config
    
    def get_sync_config(self) -> Dict[str, Any]:
        """获取同步配置"""
        return self.config.get("sync", {})
    
    def get_monitored_shares(self) -> List[Dict[str, Any]]:
        """获取监控的分享链接列表"""
        return self.config.get("monitored_shares", [])
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config.get("logging", {})
    
    def get_scheduler_config(self) -> Dict[str, Any]:
        """获取调度器配置"""
        return self.config.get("scheduler", {})
    
    def add_monitored_share(self, share_url: str, target_folder_id: str, enabled: bool = True, preserve_path: bool = True, password: Optional[str] = None) -> None:
        """
        添加新的监控分享链接
        
        Args:
            share_url: 分享链接
            target_folder_id: 目标文件夹ID
            enabled: 是否启用监控
            preserve_path: 是否保留文件路径
            password: 用户单独提供的提取码（可选，优先级高于链接中的提取码）
        """
        try:
            shares = self.get_monitored_shares()
            
            # 检查是否已存在
            for share in shares:
                if share.get("url") == share_url:
                    self.logger.warning(f"分享链接已存在: {share_url}")
                    return
            
            # 添加新的分享链接
            new_share = {
                "url": share_url,
                "enabled": enabled,
                "target_folder_id": target_folder_id,
                "preserve_path": preserve_path,  # 添加保留路径开关
                "password": password  # 添加用户单独提供的提取码
            }
            shares.append(new_share)
            
            self.config["monitored_shares"] = shares
            self._save_config(self.config)
            self.logger.info(f"已添加新的监控分享链接: {share_url}")
        except Exception as e:
            self.logger.error(f"添加监控分享链接失败: {share_url}, {e}")
            raise ConfigError(f"添加监控分享失败: {e}")
    
    def remove_monitored_share(self, share_url: str) -> None:
        """移除监控分享链接"""
        try:
            shares = self.get_monitored_shares()
            new_shares = [share for share in shares if share.get("url") != share_url]
            
            if len(new_shares) != len(shares):
                self.config["monitored_shares"] = new_shares
                self._save_config(self.config)
                self.logger.info(f"已移除监控分享链接: {share_url}")
            else:
                self.logger.warning(f"未找到要移除的分享链接: {share_url}")
        except Exception as e:
            self.logger.error(f"移除监控分享链接失败: {share_url}, {e}")
            raise ConfigError(f"移除监控分享失败: {e}")
























