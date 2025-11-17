from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import aiohttp
import asyncio
import base64
import re

try:
    from .base_resolver import BaseResolver, ParseResult, register_resolver
except ImportError:
    from base_resolver import BaseResolver, ParseResult, register_resolver


@register_resolver
class BilibiliResolver(BaseResolver):
    """Bilibili链接解析器"""

    @property
    def headers(self) -> dict[str, str]:
        """B站请求头"""
        return {
            'User-Agent': self._default_user_agent,
            'Referer': 'https://www.bilibili.com/'
        }

    def can_handle(self, url: str) -> bool:
        return "bilibili.com" in url or "b23.tv" in url
    
    def _extract_bvid(self, url: str) -> str:
        """从URL中提取BV号"""
        # 匹配 BV 号
        match = re.search(r'BV[a-zA-Z0-9]+', url)
        if match:
            return match.group(0)
        raise Exception("无法从URL中提取BV号")

    async def _expand_short_url(self, url: str, session: aiohttp.ClientSession, timeout: aiohttp.ClientTimeout) -> str:
        """还原短链（例如 b23.tv）为最终跳转URL。

        使用 session 发起请求并跟随重定向，返回最终的 URL 字符串。
        如果还原失败，则返回原始 URL。
        """
        try:
            # allow_redirects=True 会让 aiohttp 跟随重定向并最终得到目标 URL
            async with session.get(url, allow_redirects=True, timeout=timeout) as resp:
                return str(resp.url)
        except Exception:
            return url

    async def parse(self, url: str) -> ParseResult:
        """解析Bilibili链接"""
        try:
            # 使用B站API获取视频信息
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                # 如果是 b23.tv 短链，先还原为长链再提取 BV 号
                expanded_url = url
                if 'b23.tv' in url:
                    expanded_url = await self._expand_short_url(url, session, timeout)

                # 提取BV号
                bvid = self._extract_bvid(expanded_url)

                api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
                async with session.get(api_url, headers=self.headers, timeout=timeout) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    data = await response.json()
                    
                    # 检查API返回状态
                    if data.get('code') != 0:
                        raise Exception(f"API错误: {data.get('message', '未知错误')}")
                    
                    video_data = data.get('data', {})
                    
                    # 获取视频封面图片并转换为base64
                    pic_url = video_data.get('pic', '')
                    banner_b64 = ''
                    if pic_url:
                        try:
                            async with session.get(pic_url, timeout=timeout) as pic_response:
                                if pic_response.status == 200:
                                    pic_data = await pic_response.read()
                                    banner_b64 = base64.b64encode(pic_data).decode('utf-8')
                        except Exception:
                            pass  # 如果获取封面失败,使用空字符串
                    
                    # 提取数据
                    owner = video_data.get('owner', {})
                    stat = video_data.get('stat', {})
                    
                    # 构建详细的描述信息
                    author_name = owner.get('name', '未知作者')
                    view_count = stat.get('view', 0)
                    like_count = stat.get('like', 0)
                    coin_count = stat.get('coin', 0)
                    favorite_count = stat.get('favorite', 0)
                    share_count = stat.get('share', 0)
                    danmaku_count = stat.get('danmaku', 0)
                    reply_count = stat.get('reply', 0)
                    
                    description = video_data.get('desc', '')
                    
                    # 获取作者头像数据用于绘制信息图
                    face_url = owner.get('face', '')
                    face_data = None
                    if face_url:
                        try:
                            async with session.get(face_url, timeout=timeout) as face_response:
                                if face_response.status == 200:
                                    face_data = await face_response.read()
                        except Exception:
                            pass
                    
                    # 构建metadata（不包含二进制数据）
                    metadata = {
                        'author': {
                            'name': author_name,
                            'mid': owner.get('mid', ''),
                            'face': face_url,
                            'face_data': face_data  # 临时保存用于绘图
                        },
                        'stats': {
                            'view': view_count,
                            'like': like_count,
                            'coin': coin_count,
                            'favorite': favorite_count,
                            'share': share_count,
                            'danmaku': danmaku_count,
                            'reply': reply_count
                        },
                        'video_info': {
                            'bvid': video_data.get('bvid', ''),
                            'aid': video_data.get('aid', ''),
                            'duration': video_data.get('duration', 0),
                            'pubdate': video_data.get('pubdate', 0),
                            'tname': video_data.get('tname', '')
                        }
                    }
                    
                    # 生成信息图
                    info_pic_b64 = self.draw_info_pic(metadata)
                    
                    # 从metadata中移除临时的face_data
                    del metadata['author']['face_data']
                    
                    return ParseResult(
                        title=video_data.get('title', ''),
                        banner_b64=banner_b64,
                        description=description,
                        url=url,
                        platform='bilibili',
                        metadata=metadata,
                        pre_init_images=[info_pic_b64],
                        card_color=(251, 239, 243)  # B站粉色主题色
                    )
        except aiohttp.ClientError as e:
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            raise Exception(f"解析失败: {str(e)}")
        
    def draw_info_pic(self, metadata: dict) -> str:
        """绘制视频信息图片
        
        Args:
            metadata: 视频元数据(包含author.face_data字段)
            
        Returns:
            PNG图片的base64编码字符串
        """
        # 图片尺寸和边距
        width = 900
        height = 120
        padding = 15
        col_spacing = 20
        
        # 创建白色背景图片
        img = Image.new('RGBA', (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # 加载字体(尝试使用系统字体,失败则使用默认字体)
        try:
            font_large = ImageFont.truetype("msyh.ttc", 24)  # 微软雅黑
            font_medium = ImageFont.truetype("msyh.ttc", 18)
            font_small = ImageFont.truetype("msyh.ttc", 14)
            font_small_bold = ImageFont.truetype("msyhbd.ttc", 14)  # 微软雅黑粗体
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_small_bold = ImageFont.load_default()
        
        # 尝试加载emoji字体 - 使用较大尺寸以显示彩色emoji
        try:
            # Windows 10/11 自带的emoji字体,使用更大尺寸
            font_emoji = ImageFont.truetype("seguiemj.ttf", 16)
        except:
            try:
                # 备用: Segoe UI Symbol
                font_emoji = ImageFont.truetype("seguisym.ttf", 16)
            except:
                font_emoji = font_small  # 如果加载失败,使用普通字体
        
        # 获取数据
        author = metadata.get('author', {})
        stats = metadata.get('stats', {})
        
        author_name = author.get('name', '未知')
        mid = author.get('mid', '')
        avatar_data = author.get('face_data', None)  # 从metadata中获取头像数据
        view = stats.get('view', 0)
        like = stats.get('like', 0)
        coin = stats.get('coin', 0)
        favorite = stats.get('favorite', 0)
        danmaku = stats.get('danmaku', 0)
        reply = stats.get('reply', 0)
        
        # 第一列: 头像和作者信息
        avatar_size = 80
        avatar_x = padding
        avatar_y = (height - avatar_size) // 2
        
        if avatar_data:
            try:
                # 加载头像
                avatar_img = Image.open(BytesIO(avatar_data)).convert('RGBA')
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                
                # 创建圆形遮罩
                mask = Image.new('L', (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                
                # 创建圆形头像
                circle_avatar = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
                circle_avatar.paste(avatar_img, (0, 0))
                circle_avatar.putalpha(mask)
                
                # 添加阴影效果
                shadow_offset = 2
                shadow = Image.new('RGBA', (avatar_size + shadow_offset * 2, avatar_size + shadow_offset * 2), (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow)
                shadow_draw.ellipse(
                    [(shadow_offset, shadow_offset), (avatar_size + shadow_offset, avatar_size + shadow_offset)],
                    fill=(0, 0, 0, 30)
                )
                shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3))
                img.paste(shadow, (avatar_x - shadow_offset, avatar_y - shadow_offset), shadow)
                
                # 粘贴圆形头像
                img.paste(circle_avatar, (avatar_x, avatar_y), circle_avatar)
                
                # 添加边框
                draw.ellipse(
                    [(avatar_x, avatar_y), (avatar_x + avatar_size, avatar_y + avatar_size)],
                    outline=(255, 255, 255, 255),
                    width=3
                )
            except:
                # 头像加载失败,绘制占位圆
                draw.ellipse(
                    [(avatar_x, avatar_y), (avatar_x + avatar_size, avatar_y + avatar_size)],
                    fill=(200, 200, 200, 255),
                    outline=(150, 150, 150, 255),
                    width=2
                )
        else:
            # 无头像,绘制占位圆
            draw.ellipse(
                [(avatar_x, avatar_y), (avatar_x + avatar_size, avatar_y + avatar_size)],
                fill=(200, 200, 200, 255),
                outline=(150, 150, 150, 255),
                width=2
            )
        
        # 作者名和UID
        text_x = avatar_x + avatar_size + 15
        name_y = avatar_y + 15
        uid_y = avatar_y + 50
        
        draw.text((text_x, name_y), author_name, fill=(0, 0, 0, 255), font=font_large)
        draw.text((text_x, uid_y), f"UID: {mid}", fill=(128, 128, 128, 255), font=font_small)
        
        # 第二列: 点赞、投币、收藏
        col2_x = 340
        col_width = 160
        
        row_height = 26
        # 让数据列垂直居中对齐头像区域
        start_y = avatar_y + 10
        
        # 绘制图标和文字 - 使用embedded_color支持彩色emoji
        icon_offset = 25  # 图标后文字的偏移
        text_offset = -4  # 文字垂直偏移,使其与emoji中心对齐
        
        # 点赞
        draw.text((col2_x, start_y), "👍", font=font_emoji, embedded_color=True)
        self._draw_text_with_bold_numbers((col2_x + icon_offset, start_y + text_offset), f"点赞 {self._format_number_with_comma(like)}", draw, font_small, font_small_bold)
        
        # 投币
        draw.text((col2_x, start_y + row_height), "🪙", font=font_emoji, embedded_color=True)
        self._draw_text_with_bold_numbers((col2_x + icon_offset, start_y + row_height + text_offset), f"投币 {self._format_number_with_comma(coin)}", draw, font_small, font_small_bold)
        
        # 收藏
        draw.text((col2_x, start_y + row_height * 2), "⭐", font=font_emoji, embedded_color=True)
        self._draw_text_with_bold_numbers((col2_x + icon_offset, start_y + row_height * 2 + text_offset), f"收藏 {self._format_number_with_comma(favorite)}", draw, font_small, font_small_bold)
        
        # 第三列: 播放、弹幕、评论
        col3_x = col2_x + col_width + col_spacing
        
        # 播放
        draw.text((col3_x, start_y), "▶️", font=font_emoji, embedded_color=True)
        self._draw_text_with_bold_numbers((col3_x + icon_offset, start_y + text_offset), f"播放 {self._format_number_with_comma(view)}", draw, font_small, font_small_bold)
        
        # 弹幕
        draw.text((col3_x, start_y + row_height), "💬", font=font_emoji, embedded_color=True)
        self._draw_text_with_bold_numbers((col3_x + icon_offset, start_y + row_height + text_offset), f"弹幕 {self._format_number_with_comma(danmaku)}", draw, font_small, font_small_bold)
        
        # 评论
        draw.text((col3_x, start_y + row_height * 2), "💭", font=font_emoji, embedded_color=True)
        self._draw_text_with_bold_numbers((col3_x + icon_offset, start_y + row_height * 2 + text_offset), f"评论 {self._format_number_with_comma(reply)}", draw, font_small, font_small_bold)
        
        # 计算实际使用的宽度并裁剪图片
        # 第三列的最右侧位置 + 一些文字的估计宽度 + 右边距
        max_text_width = 120  # 估计"播放 999,999"这类文本的最大宽度
        actual_width = col3_x + icon_offset + max_text_width + padding
        
        # 裁剪图片到实际使用的宽度
        img = img.crop((0, 0, actual_width, height))
        
        # 转换为base64
        output = BytesIO()
        img.save(output, format='PNG')
        img_bytes = output.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def _format_number_with_comma(self, num: int) -> str:
        """格式化数字显示为带千位分隔符的格式"""
        return f"{num:,}"
    
    def _draw_text_with_bold_numbers(self, pos: tuple, text: str, draw, font_normal, font_bold):
        """绘制文本,其中数字使用粗体字体"""
        x, y = pos
        
        # 使用正则表达式分割文本为文字和数字部分
        parts = re.split(r'(\d+(?:,\d{3})*)', text)
        
        for part in parts:
            if not part:
                continue
            
            # 判断是否为数字(包含逗号的数字)
            if re.match(r'^\d+(?:,\d{3})*$', part):
                # 数字部分使用粗体
                draw.text((x, y), part, fill=(0, 0, 0, 255), font=font_bold)
            else:
                # 文字部分使用普通字体
                draw.text((x, y), part, fill=(0, 0, 0, 255), font=font_normal)
            
            # 计算当前部分的宽度,更新x坐标
            bbox = draw.textbbox((0, 0), part, font=font_bold if re.match(r'^\d+(?:,\d{3})*$', part) else font_normal)
            x += bbox[2] - bbox[0]
    
if __name__ == "__main__":
    async def test():
        url = "https://www.bilibili.com/video/BV1n2y2BCENY"
        resolver: BilibiliResolver = BilibiliResolver()
        result = await resolver.parse(url)
        
        print(f"标题: {result.title}")
        print(f"平台: {result.platform}")
        print(f"描述:\n{result.description}")
        print(f"\nMetadata: {result.metadata}")
        
        # 检查生成的信息图
        if result.pre_init_images:
            print(f"\n信息图已生成: {len(result.pre_init_images)} 张")
            print(f"信息图base64长度: {len(result.pre_init_images[0])} 字符")
            
            # 可选：显示图片
            try:
                img_data = base64.b64decode(result.pre_init_images[0])
                img = Image.open(BytesIO(img_data))
                img.show()
                print("图片已在默认查看器中打开")
            except Exception as e:
                print(f"显示图片失败: {e}")
    
    asyncio.run(test())
