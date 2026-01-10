class Cloud123Error(Exception):
    """123云盘应用的基础异常类"""
    pass


class AuthError(Cloud123Error):
    """认证相关的错误，如获取或刷新token失败"""
    pass


class ShareLinkError(Cloud123Error):
    """分享链接相关的错误"""
    pass


class FileOperationError(Cloud123Error):
    """文件操作相关的错误"""
    pass


class ConfigError(Cloud123Error):
    """配置相关的错误"""
    pass


class SyncError(Cloud123Error):
    """同步相关的错误"""
    pass


class APIError(Cloud123Error):
    """API调用相关的错误"""
    def __init__(self, message, status_code=None, api_response=None):
        """
        初始化API错误
        
        Args:
            message: 错误消息
            status_code: HTTP状态码（可选）
            api_response: API响应内容（可选）
        """
        super().__init__(message)
        self.status_code = status_code
        self.api_response = api_response


class RateLimitError(APIError):
    """API调用频率限制错误"""
    pass


class RetryExhaustedError(Cloud123Error):
    """重试次数用尽错误"""
    def __init__(self, message, attempts_made, errors=None):
        """
        初始化重试用尽错误
        
        Args:
            message: 错误消息
            attempts_made: 已尝试的次数
            errors: 所有尝试中遇到的错误列表（可选）
        """
        super().__init__(message)
        self.attempts_made = attempts_made
        self.errors = errors or []
