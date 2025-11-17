from .base_resolver import BaseResolver, ParseResult, resolve_link

__all__ = [
    "BaseResolver",
    "ParseResult",
    "resolve_link"
]

# 激活解析器
from .bilibili import BilibiliResolver