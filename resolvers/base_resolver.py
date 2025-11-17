from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Type
from ncatbot.utils import get_log

LOG = get_log("LinkResolver")

@dataclass
class ParseResult:
    title: str
    banner_b64: str
    description: str
    url: str
    platform: str
    metadata: Optional[dict[str, dict[str, Any]]] = None
    pre_init_images: Optional[list[str]] = field(default_factory=list)
    card_color: tuple[int, int, int] = (255, 255, 255)  # 卡片背景颜色 RGB
    
    def generate_card_image(self, target_width: int = 1200) -> bytes:
        """生成整合了banner和信息图的卡片图片
        
        Args:
            target_width: 目标宽度
            
        Returns:
            PNG图片的bytes数据
        """
        import base64
        from io import BytesIO
        from PIL import Image, ImageFilter
        
        padding = 24
        border_width = 1
        border_color = (200, 200, 200, 255)
        elevation = 4
        
        # 图片最大宽度（直接使用目标宽度，不留padding）
        img_max_width = target_width
        
        # 准备所有图片组件
        images = []
        
        # 添加封面
        if self.banner_b64:
            banner_data = base64.b64decode(self.banner_b64)
            banner_img = Image.open(BytesIO(banner_data)).convert('RGBA')
            if banner_img.width != img_max_width:
                scale = img_max_width / banner_img.width
                new_height = int(banner_img.height * scale)
                banner_img = banner_img.resize((img_max_width, new_height), Image.Resampling.LANCZOS)
            images.append(banner_img)
        
        # 添加信息图
        if self.pre_init_images:
            for img_b64 in self.pre_init_images:
                img_data = base64.b64decode(img_b64)
                info_img = Image.open(BytesIO(img_data)).convert('RGBA')
                if info_img.width != img_max_width:
                    scale = img_max_width / info_img.width
                    new_height = int(info_img.height * scale)
                    info_img = info_img.resize((img_max_width, new_height), Image.Resampling.LANCZOS)
                images.append(info_img)
        
        # 计算总高度
        total_height = 0
        for img in images:
            total_height += img.height + border_width * 2
        
        # 直接创建画布，不添加padding和阴影
        canvas = Image.new('RGBA', (target_width, total_height), (0, 0, 0, 0))
        
        # 粘贴所有图片
        current_y = 0
        for img in images:
            # 添加边框
            bordered_img = Image.new('RGBA', (img.width + border_width * 2, img.height + border_width * 2), border_color)
            bordered_img.paste(img, (border_width, border_width))
            
            # 居中粘贴
            x_offset = (target_width - bordered_img.width) // 2
            canvas.paste(bordered_img, (x_offset, current_y), bordered_img if bordered_img.mode == 'RGBA' else None)
            current_y += bordered_img.height
        
        # 转换为bytes
        output = BytesIO()
        canvas.save(output, format='PNG')
        return output.getvalue()

_resolvers_registry: list["BaseResolver"] = []

def register_resolver(cls: Type["BaseResolver"]) -> Type["BaseResolver"]:
    """装饰器：注册解析器到全局注册表"""
    # 检查是否已注册同类型的解析器
    for resolver in _resolvers_registry:
        if isinstance(resolver, cls):
            return cls
    # 创建实例并注册
    _resolvers_registry.append(cls())
    return cls

class BaseResolver(ABC):
    """解析器基类"""

    _default_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

    @property
    def headers(self) -> dict[str, str]:
        """返回请求头，子类可以重写此方法自定义headers"""
        return {
            'User-Agent': self._default_user_agent
        }

    async def expand_short_url(self, url: str, session, timeout) -> str:
        """尝试还原短链接（例如 b23.tv），跟随重定向返回最终 URL。

        Args:
            url: 原始可能为短链的 URL
            session: aiohttp.ClientSession 实例
            timeout: aiohttp.ClientTimeout 实例

        Returns:
            最终跳转后的 URL（出错时返回原始 url）
        """
        try:
            # 使用 allow_redirects=True 跟随重定向
            async with session.get(url, allow_redirects=True, timeout=timeout) as resp:
                return str(resp.url)
        except Exception:
            return url

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断是否能处理该链接
        
        Args:
            url: 待检测的链接
            
        Returns:
            是否能够处理
        """
        pass
    
    @abstractmethod
    async def parse(self, url: str) -> ParseResult:
        """解析链接
        
        Args:
            url: 待解析的链接
            
        Returns:
            解析结果字典
        """
        pass

async def resolve_link(url: str) -> list[ParseResult]:
    """使用注册的解析器解析链接"""
    results = []
    for resolver in _resolvers_registry:
        if resolver.can_handle(url):
            LOG.info(f"Detected URL: {url}")
            results.append(await resolver.parse(url))
    return results