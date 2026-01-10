import os
import logging
import logging.handlers
from typing import Dict, Any
from errors import ConfigError

class LoggingConfig:
    @staticmethod
    def setup_logging(config: Dict[str, Any]) -> None:
        """根据配置设置日志系统"""
        try:
            # 获取日志配置
            log_level = config.get('level', 'INFO').upper()
            log_file = config.get('log_file', './logs/123subscrib.log')
            max_bytes = config.get('max_bytes', 10485760)  # 默认10MB
            backup_count = config.get('backup_count', 5)
            
            # 确保日志目录存在
            log_dir = os.path.dirname(os.path.abspath(log_file))
            os.makedirs(log_dir, exist_ok=True)
            
            # 创建logger
            logger = logging.getLogger()
            logger.setLevel(log_level)
            
            # 清理现有handler
            if logger.handlers:
                for handler in logger.handlers:
                    handler.close()
                logger.handlers.clear()
            
            # 创建格式化器
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # 创建文件handler (使用RotatingFileHandler进行日志轮转)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # 创建控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            # 设置第三方库的日志级别
            LoggingConfig._setup_third_party_loggers()
            
            # 记录初始化信息
            logging.info(f"日志系统初始化完成，日志文件: {log_file}")
            logging.info(f"日志级别: {log_level}")
            
        except Exception as e:
            # 如果日志系统初始化失败，使用基础的打印方式通知
            print(f"日志系统初始化失败: {e}")
            raise ConfigError(f"日志配置失败: {e}")
    
    @staticmethod
    def _setup_third_party_loggers() -> None:
        """设置第三方库的日志级别"""
        # 降低一些第三方库的日志级别，避免日志过于冗长
        quiet_loggers = [
            'urllib3',
            'requests',
            'aiohttp',
            'asyncio',
            'schedule'
        ]
        
        for logger_name in quiet_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
    
    @staticmethod
    def get_logger(module_name: str = None) -> logging.Logger:
        """获取一个logger实例"""
        if module_name:
            return logging.getLogger(module_name)
        return logging.getLogger()
    
    @staticmethod
    def log_error(error: Exception, message: str = None) -> None:
        """记录错误信息，自动捕获异常类型和堆栈"""
        logger = logging.getLogger()
        if message:
            logger.error(f"{message}: {str(error)}", exc_info=True)
        else:
            logger.error(f"错误: {str(error)}", exc_info=True)
    
    @staticmethod
    def log_warning(message: str) -> None:
        """记录警告信息"""
        logging.getLogger().warning(message)
    
    @staticmethod
    def log_info(message: str) -> None:
        """记录信息"""
        logging.getLogger().info(message)
    
    @staticmethod
    def log_debug(message: str) -> None:
        """记录调试信息"""
        logging.getLogger().debug(message)