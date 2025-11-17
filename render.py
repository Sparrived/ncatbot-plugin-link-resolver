from typing import List
from PIL import Image
from pathlib import Path

import pillowmd

try:
    from .resolvers.base_resolver import ParseResult
except ImportError:
    from resolvers.base_resolver import ParseResult


async def render_link_result(
    parse_result: ParseResult,
    plugin_version: str,
    resources_path: Path = Path("data/LinkResolver/resources")
) -> List[Image.Image]:
    """
    将链接解析结果渲染为图片,使用 pillowmd 渲染 Markdown 格式
    
    Args:
        parse_result: 链接解析结果
        plugin_version: 插件版本信息(这里用于显示平台信息)
        resources_path: 资源文件夹路径(包含 mdstyle 文件夹)
        
    Returns:
        渲染后的图片列表
    """
    
    # 确保临时文件夹存在
    temp_dir = resources_path.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    pillowmd.Setting.QUICK_IMAGE_PATH = temp_dir
    temp_pics: list[Path] = []
    
    # 使用ParseResult的方法生成卡片
    card_bytes = parse_result.generate_card_image()
    card_path = temp_dir / f"card_{hash(parse_result.url)}.png"
    card_path.write_bytes(card_bytes)
    temp_pics.append(card_path)
    
    # 构建 Markdown 文本
    markdown_parts = []
    
    # 标题（使用Markdown渲染）
    markdown_parts.append("# 聚合链接解析结果\n")
    
    markdown_parts.append(f"###   {parse_result.title}")
    # 添加卡片图片
    markdown_parts.append(f"!sgm[{card_path.name}|1.0]\n")
    
    # 添加描述和其他信息
    if parse_result.description:
        markdown_parts.append(f"\n **简介:** {parse_result.description}\n")
    
    markdown_parts.append(f"平台: {parse_result.platform}\n")
    markdown_parts.append(f"**原链接:** {parse_result.url}\n")
    
    markdown_parts.append(f"\n LinkResolver v{plugin_version} \n")
    # 组合完整的 Markdown 文本
    markdown_text = "".join(markdown_parts)
    
    # 加载样式并渲染
    style_path = resources_path / "mdstyle"
    style = pillowmd.LoadMarkdownStyles(str(style_path))
    
    result = await pillowmd.MdToImage(
        text=markdown_text,
        style=style,
        sgm=True,
        sgexter=True
    )
    
    # 从渲染结果中获取图片
    if result.imageType == 'gif':
        base_images = result.images
    else:
        base_images = [result.image]
    
    # 删除临时图片文件
    for temp_pic in temp_pics:
        temp_pic.unlink(missing_ok=True)
    
    return base_images


async def render_multiple_results(
    parse_results: List[ParseResult],
    plugin_version: str,
    resources_path: Path = Path("data/LinkResolver/resources")
) -> List[Image.Image]:
    """
    渲染多个链接解析结果
    
    Args:
        parse_results: 链接解析结果列表
        plugin_version: 插件版本信息
        resources_path: 资源文件夹路径
        
    Returns:
        渲染后的图片列表
    """
    all_images = []
    for result in parse_results:
        images = await render_link_result(result, plugin_version, resources_path)
        all_images.extend(images)
    return all_images


if __name__ == "__main__":
    import asyncio
    from resolvers.bilibili import BilibiliResolver
    
    async def test():
        print("开始测试链接解析渲染...")
        
        # 测试B站链接
        url = "https://www.bilibili.com/video/BV17vCXBHECZ/?spm_id_from=333.1007.tianma.1-1-1.click"
        resolver = BilibiliResolver()
        result = await resolver.parse(url)
        
        print(f"标题: {result.title}")
        print(f"平台: {result.platform}")
        
        # 渲染结果
        images = await render_link_result(result, "1.0.0")
        
        print(f"渲染完成, 图片数量: {len(images)}")
        
        # 保存第一张图片
        output_path = Path("d:/Code/SiriusBot-Neko/test_link_render.png")
        images[0].save(output_path)
        print(f"测试图片已保存到: {output_path}")
        
        # 如果是多帧,保存为GIF
        if len(images) > 1:
            gif_path = Path("d:/Code/SiriusBot-Neko/test_link_render.gif")
            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                duration=100,
                loop=0
            )
            print(f"GIF已保存到: {gif_path}")
        
        print("\n✅ 测试完成!")
    
    asyncio.run(test())
