import logging
import time
from typing import Callable, Dict, Any, List, Optional, Union
import uuid

from .task_scheduler import TaskScheduler
from .monitor import TaskMonitor

class SchedulerManager:
    """调度管理器，集成调度器和监控器"""
    
    def __init__(self):
        """初始化调度管理器"""
        self.logger = logging.getLogger(__name__)
        self.scheduler = TaskScheduler()
        self.monitor = TaskMonitor()
        self.task_mapping = {}  # 映射scheduler任务ID到我们的任务信息
        self.running = False
        
    def start(self) -> None:
        """启动调度管理器"""
        if self.running:
            self.logger.warning("调度管理器已经在运行中")
            return
            
        self.scheduler.start()
        self.running = True
        self.logger.info("调度管理器已启动")
    
    def stop(self) -> None:
        """停止调度管理器"""
        if not self.running:
            self.logger.warning("调度管理器未在运行")
            return
            
        self.scheduler.stop()
        self.running = False
        self.task_mapping.clear()
        self.logger.info("调度管理器已停止")
    
    def add_task(self, 
                task_func: Callable,
                interval_seconds: int,
                task_name: str,
                task_id: Optional[str] = None,
                **kwargs) -> str:
        """添加一个监控任务
        
        Args:
            task_func: 任务函数
            interval_seconds: 执行间隔（秒）
            task_name: 任务名称
            task_id: 任务ID（可选，不提供则自动生成）
            **kwargs: 传递给任务函数的参数
            
        Returns:
            任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
            
        # 创建包装函数，添加监控逻辑
        def monitored_task():
            # 记录任务开始
            self.monitor.start_task(task_id, task_name)
            
            success = True
            error = None
            details = {}
            
            try:
                # 执行任务函数
                result = task_func(**kwargs)
                
                # 如果任务有返回值，则添加到details中
                if result is not None:
                    if isinstance(result, dict):
                        details.update(result)
                    else:
                        details['result'] = result
                        
            except Exception as e:
                success = False
                error = str(e)
                self.logger.error(f"任务执行异常: {task_name} ({task_id}), 错误: {error}")
                
            # 记录任务完成
            self.monitor.complete_task(task_id, success, error, details)
            
        # 添加到调度器
        scheduler_task_id = self.scheduler.add_interval_task(
            monitored_task,
            interval_seconds,
            task_id=task_id
        )
        
        # 记录映射关系
        self.task_mapping[scheduler_task_id] = task_id
        
        return task_id
    
    def remove_task(self, task_id: str) -> bool:
        """移除指定ID的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功移除
        """
        return self.scheduler.remove_job(task_id)
    
    def update_task_interval(self, task_id: str, new_interval_seconds: int) -> bool:
        """更新指定ID任务的执行间隔
        
        Args:
            task_id: 任务ID
            new_interval_seconds: 新的执行间隔（秒）
            
        Returns:
            是否成功更新
        """
        return self.scheduler.update_task_interval(task_id, new_interval_seconds)
    
    def run_all_tasks_now(self) -> None:
        """立即运行所有任务"""
        self.scheduler.run_all_jobs_now()
    
    def get_task_count(self) -> int:
        """获取任务数量
        
        Returns:
            任务数量
        """
        return self.scheduler.get_job_count()
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定任务的状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息，如果任务不存在则返回None
        """
        return self.monitor.get_task_status(task_id)
    
    def get_all_tasks_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务的状态
        
        Returns:
            所有任务状态字典
        """
        return self.monitor.get_all_tasks()
    
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的任务执行历史
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            任务执行历史记录
        """
        return self.monitor.get_recent_history(limit)
    
    def get_statistics(self) -> Dict[str, int]:
        """获取任务统计信息
        
        Returns:
            统计信息字典
        """
        return self.monitor.get_statistics()
    
    def clear_history(self) -> None:
        """清除历史记录"""
        self.monitor.clear_history()
