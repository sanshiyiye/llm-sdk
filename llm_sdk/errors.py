"""
LLM SDK 错误体系
所有错误继承自 LLMError，业务层可以只 catch LLMError
"""


class LLMError(Exception):
    """SDK 基础错误"""
    def __init__(self, message: str, status_code: int = 0, raw: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw


class RateLimitError(LLMError):
    """429 限流，应指数退避重试"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: float = 5.0, **kw):
        super().__init__(message, status_code=429, **kw)
        self.retry_after = retry_after


class TimeoutError(LLMError):
    """请求超时"""
    def __init__(self, message: str = "Request timed out", **kw):
        super().__init__(message, status_code=408, **kw)


class ModelError(LLMError):
    """400/422 模型拒绝，不应重试"""
    def __init__(self, message: str, **kw):
        super().__init__(message, **kw)


class ProxyError(LLMError):
    """500/503 Proxy 内部错误，可重试"""
    def __init__(self, message: str, **kw):
        super().__init__(message, **kw)


class AuthError(LLMError):
    """401/403 鉴权失败，不应重试"""
    def __init__(self, message: str = "Authentication failed", **kw):
        super().__init__(message, **kw)


class NetworkError(LLMError):
    """网络连接错误，可重试"""
    def __init__(self, message: str, **kw):
        super().__init__(message, **kw)


class StructuredOutputError(LLMError):
    """结构化输出解析失败"""
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


class TemplateNotFoundError(LLMError):
    """Prompt 模板未找到"""
    def __init__(self, name: str):
        super().__init__(f"模板未找到: '{name}'")
        self.template_name = name
