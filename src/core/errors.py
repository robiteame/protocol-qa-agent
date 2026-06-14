# 基础异常
class AppError(Exception):
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code

class ProviderError(AppError):
    def __init__(self, message: str = "模型调用失败"):
        super().__init__(message, code=501)

class ParseError(AppError):
    def __init__(self, message: str = "文档解析失败"):
        super().__init__(message, code=502)

class LLMOutputError(AppError):
    def __init__(self, message: str = "LLM输出异常"):
        super().__init__(message, code=503)

class NotFoundError(AppError):
    def __init__(self, message: str = "文档/会话不存在"):
        super().__init__(message, code=404)