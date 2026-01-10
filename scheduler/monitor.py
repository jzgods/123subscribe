import logging
import time
import threading
from typing import Dict, Any, List, Optional

class TaskMonitor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.task_history = []  # 任务执行历史
        self.task_status = {}  # 当前任务状态
        self.lock = threading.Lock()  # 线程锁，保证线程安全
    
    def start_task(self, task_id: str, task_name: str) -> None:
        """记录任务开始执行
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
        """
        with self.lock:
            start_time = time.time()
            self.task_status[task_id] = {
                'task_id': task_id,
                'task_name': task_name,
                'status': 'running',
                'start_time': start_time,
                'end_time': None,
                'duration': None,
                'success': None,
                'error': None,
                'details': {}
            }
            
            self.logger.info(f"任务开始执行: {task_name} ({task_id})")
    
    def update_task(self, task_id: str, details: Dict[str, Any]) -> None:
        """更新任务状态信息
        
        Args:
            task_id: 任务ID
            details: 要更新的详细信息
        """
        with self.lock:
            if task_id in self.task_status:
                self.task_status[task_id]['details'].update(details)
    
    def complete_task(self, task_id: str, success: bool, error: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """记录任务执行完成
        
        Args:
            task_id: 任务ID
            success: 是否成功
            error: 错误信息（如果失败）
            details: 附加详细信息
        """
        with self.lock:
            if task_id in self.task_status:
                end_time = time.time()
                task_info = self.task_status[task_id]
                
                # 更新任务信息
                task_info['status'] = 'completed'
                task_info['end_time'] = end_time
                task_info['duration'] = end_time - task_info['start_time']
                task_info['success'] = success
                task_info['error'] = error
                
                if details:
                    task_info['details'].update(details)
                
                # 添加到历史记录
                self.task_history.append(task_info.copy())
                
                # 限制历史记录数量，防止内存占用过大
                if len(self.task_history) > 1000:  # 保留最近1000条记录
                    self.task_history.pop(0)
                
                # 记录日志
                task_name = task_info['task_name']
                duration = task_info['duration']
                
                if success:
                    self.logger.info(f"任务执行成功: {task_name} ({task_id}), 耗时: {duration:.2f}秒")
                    
                    # 记录详细的成功信息
                    if details:
                        for key, value in details.items():
                            self.logger.debug(f"  {key}: {value}")
                else:
                    self.logger.error(f"任务执行失败: {task_name} ({task_id}), 耗时: {duration:.2f}秒, 错误: {error}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定任务的状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息，如果任务不存在则返回None
        """
        with self.lock:
            return self.task_status.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务的状态
        
        Returns:
            所有任务状态字典
        """
        with self.lock:
            return self.task_status.copy()
    
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的任务执行历史
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            任务执行历史记录
        """
        with self.lock:
            return self.task_history[-limit:].copy()
    
    def get_statistics(self) -> Dict[str, int]:
        """获取任务统计信息
        
        Returns:
            统计信息字典
        """
        with self.lock:
            # 计算统计信息
            total = len(self.task_history)
            success = sum(1 for task in self.task_history if task['success'] is True)
            failed = sum(1 for task in self.task_history if task['success'] is False)
            running = sum(1 for task in self.task_status.values() if task['status'] == 'running')
            
            return {
                'total_executed': total,
                'success_count': success,
                'failed_count': failed,
                'running_count': running
            }
    
    def clear_history(self) -> None:
        """清除历史记录"""
        with self.lock:
            self.task_history.clear()
            self.logger.info("任务历史记录已清空")
