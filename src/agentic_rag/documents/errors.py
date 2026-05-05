class UnsupportedFormatError(ValueError):
    """不支持的文件扩展名。"""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        super().__init__(f"不支持的文件类型: {suffix or '（无扩展名）'}")
