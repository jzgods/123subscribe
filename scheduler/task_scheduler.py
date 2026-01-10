import schedule
import time
import logging
import threading
from typing import Callable, Dict, Any, Optional

class TaskScheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scheduler_thread = None
        self.running = False
        self.jobs = []
    
    def add_interval_task(self, task_func: Callable, interval_seconds: int, task_id: str = None, **kwargs) -> str:
        """添加一个定期执行的任务
        
        Args:
            task_func: 任务函数
            interval_seconds: 执行间隔（秒）
            task_id: 任务ID（可选，不提供则自动生成）
            **kwargs: 传递给任务函数的参数
            
        Returns:
            任务ID
        """
        if task_id is None:
            task_id = f"task_{int(time.time())}"
        
        # 创建包装函数，处理异常
        def task_wrapper():
            try:
                self.logger.info(f"执行任务: {task_id}")
                task_func(**kwargs)
                self.logger.info(f"任务执行完成: {task_id}")
            except Exception as e:
                self.logger.error(f"任务执行失败: {task_id}, 错误: {str(e)}")
        
        # 添加任务到schedule并保存返回的Job对象
        job = schedule.every(interval_seconds).seconds.do(task_wrapper)
        
        # 记录任务信息，包括schedule返回的Job对象
        job_info = {
            'id': task_id,
            'func': task_func,
            'interval': interval_seconds,
            'kwargs': kwargs,
            'schedule_job': job  # 保存schedule返回的Job对象
        }
        self.jobs.append(job_info)
        
        self.logger.info(f"已添加定时任务: {task_id}, 间隔: {interval_seconds}秒")
        
        return task_id
    
    def start(self) -> None:
        """启动调度器"""
        if self.running:
            self.logger.warning("调度器已经在运行中")
            return
        
        self.running = True
        
        # 创建并启动调度器线程
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("调度器已启动")
    
    def stop(self) -> None:
        """停止调度器"""
        if not self.running:
            self.logger.warning("调度器未在运行")
            return
        
        self.running = False
        
        # 等待调度器线程结束
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)  # 最多等待5秒
        
        # 清除所有任务
        schedule.clear()
        self.jobs.clear()
        
        self.logger.info("调度器已停止")
    
    def _run_scheduler(self) -> None:
        """调度器线程函数"""
        self.logger.info("调度器线程已启动")
        
        while self.running:
            try:
                # 运行所有已到期的任务
                schedule.run_pending()
            except Exception as e:
                self.logger.error(f"调度器执行过程中发生异常: {str(e)}")
            
            # 短暂休眠，减少CPU占用
            time.sleep(1)
    
    def get_job_count(self) -> int:
        """获取任务数量
        
        Returns:
            任务数量
        """
        return len(self.jobs)
    
    def get_jobs(self) -> list:
        """获取所有任务信息
        
        Returns:
            任务信息列表
        """
        return self.jobs.copy()
    
    def remove_job(self, task_id: str) -> bool:
        """移除指定ID的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功移除
        """
        # 查找任务
        job_to_remove = None
        schedule_job = None
        for i, job in enumerate(self.jobs):
            if job['id'] == task_id:
                job_to_remove = i
                schedule_job = job.get('schedule_job')
                break
        
        if job_to_remove is not None:
            # 从列表中移除
            self.jobs.pop(job_to_remove)
            
            # 从schedule库中移除任务
            if schedule_job:
                schedule.cancel_job(schedule_job)
                self.logger.info(f"已从schedule库移除任务: {task_id}")
            
            self.logger.info(f"已移除任务: {task_id}")
            return True
        else:
            self.logger.warning(f"未找到任务: {task_id}")
            return False
    
    def run_all_jobs_now(self) -> None:
        """立即运行所有任务"""
        self.logger.info("立即运行所有任务...")
        
        # 运行所有等待中的任务
        schedule.run_all(delay_seconds=0)
        
        self.logger.info("所有任务执行完成")
    
    def update_task_interval(self, task_id: str, new_interval_seconds: int) -> bool:
        """更新指定ID任务的执行间隔
        
        Args:
            task_id: 任务ID
            new_interval_seconds: 新的执行间隔（秒）
            
        Returns:
            是否成功更新
        """
        # 查找任务
        job_to_update = None
        for job_info in self.jobs:
            if job_info['id'] == task_id:
                job_to_update = job_info
                break
        
        if job_to_update is None:
            self.logger.warning(f"未找到任务: {task_id}")
            return False
        
        # 保存任务信息
        task_func = job_to_update['func']
        kwargs = job_to_update['kwargs']
        
        # 移除旧任务
        self.remove_job(task_id)
        
        # 使用新间隔重新添加任务
        self.add_interval_task(task_func, new_interval_seconds, task_id, **kwargs)
        
        self.logger.info(f"已更新任务间隔并立即生效: {task_id}, 新间隔: {new_interval_seconds}秒")
        return True
