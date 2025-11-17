"""工具函数模块"""

from ncatbot.plugin_system import NcatBotPlugin
from functools import wraps
from typing import Callable
import re

URLPATTERN = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'

def extract_urls(text: str) -> list[str]:
    """从文本中提取所有 URL
    
    Args:
        text: 待提取的文本
        
    Returns:
        URL 列表
    """
    return re.findall(URLPATTERN, text)


def subscribed_check(subscribed_groups: list, group_id: str) -> bool:
    """检查群组是否已订阅
    
    Args:
        subscribed_groups: 已订阅的群组列表
        group_id: 群组ID
        
    Returns:
        是否已订阅
    """
    return str(group_id) in [str(g) for g in subscribed_groups]


def require_subscription(func: Callable):
    """群组和私聊订阅判断装饰器
    
    仅允许已订阅的群组或私聊用户使用该功能
    """
    @wraps(func)
    async def wrapper(self: NcatBotPlugin, event, *args, **kwargs):
        group_id = getattr(event, "group_id", None)
        user_id = getattr(event, "user_id", None)
        
        # 群聊消息
        if group_id is not None:
            if not subscribed_check(self.config.get("subscribed_groups", []), str(group_id)):
                # 未订阅的群组，不执行
                return None
        # 私聊消息
        elif user_id is not None:
            subscribed_privates = self.config.get("subscribed_privates", [])
            if str(user_id) not in [str(u) for u in subscribed_privates]:
                # 未订阅的私聊用户，不执行
                return None
        
        return await func(self, event, *args, **kwargs)
    
    return wrapper
