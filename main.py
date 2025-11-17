from ncatbot.plugin_system import NcatBotPlugin, command_registry, param, admin_filter, on_message
from ncatbot.plugin_system.builtin_plugin.unified_registry.command_system.registry.help_system import HelpGenerator
from ncatbot.utils import get_log
from ncatbot.core import BaseMessageEvent, GroupMessageEvent, MessageSentEvent, Reply

from .resolvers.base_resolver import resolve_link
from .render import render_link_result
from pathlib import Path
from io import BytesIO
import base64
from .utils import extract_urls, require_subscription



class LinkResolver(NcatBotPlugin):
    """链接解析器插件 - 自动解析和展示各类链接内容"""
    
    name = "LinkResolver"
    version = "1.0.0"
    author = "Sparrived"
    description = "自动解析消息中的链接，提供内容预览和信息提取功能"
    
    log = get_log(name)

    def init_config(self):
        """初始化配置项"""
        self.register_config("subscribed_groups", [], value_type=list)
        self.register_config("subscribed_privates", [], value_type=list)
        self.register_config("auto_parse", True, value_type=bool)

    async def on_load(self):
        """插件加载时执行"""
        self.init_config()
        self.log.info(f"{self.name} v{self.version} 加载成功")
        self.log.info(f"已订阅群聊: {self.config['subscribed_groups']}")

    # ======== 命令注册 ========
    link_group = command_registry.group("link", description="链接解析相关命令")

    @link_group.command("parse", description="手动解析指定链接")
    @param("url", "要解析的链接URL")
    @require_subscription
    async def cmd_parse_link(self, event: BaseMessageEvent, url: str):
        """手动解析链接命令"""
        await self._resolve_link(event, url)


    @on_message
    @require_subscription
    async def handle_message(self, event: BaseMessageEvent):
        if isinstance(event, MessageSentEvent):
            return  # 忽略自身上报消息，此问题已在ncatbot4.3.0修复
        if not self.config["auto_parse"]:
            return
        texts = event.message.filter_text()
        if texts and texts[0].text.startswith("/"):
            return
        if event.message.filter(Reply):
            return
        raw_message = event.raw_message.replace("\\", "")
        urls = extract_urls(raw_message)
        if len(urls) == 0:
            return
        for url in urls:
            
            await self._resolve_link(event, url)


    # ======== 订阅功能 ========
    @admin_filter
    @link_group.command("subscribe", description="订阅聚合链接解析功能")
    async def cmd_subscribe(self, event: BaseMessageEvent):
        """订阅聚合链接解析功能"""
        if isinstance(event, GroupMessageEvent):
            subscribed_groups = self.config["subscribed_groups"]
            if str(event.group_id) in subscribed_groups:
                await event.reply("本群组已订阅聚合链接解析功能喵~")
                return
            self.config["subscribed_groups"].append(str(event.group_id))
        else:
            subscribed_privates = self.config["subscribed_privates"]
            if str(event.user_id) in subscribed_privates:
                await event.reply("您已订阅聚合链接解析功能喵~")
                return
            self.config["subscribed_privates"].append(str(event.user_id))
        await event.reply("订阅了聚合链接解析功能喵~")


    @admin_filter
    @link_group.command("unsubscribe", description="取消订阅聚合链接解析功能")
    async def cmd_unsubscribe(self, event: BaseMessageEvent):
        """取消订阅聚合链接解析功能"""
        if isinstance(event, GroupMessageEvent):
            subscribed_groups = self.config["subscribed_groups"]
            if str(event.group_id) not in subscribed_groups:
                await event.reply("本群组未订阅聚合链接解析功能喵~")
                return
            self.config["subscribed_groups"].remove(str(event.group_id))
        else:
            subscribed_privates = self.config["subscribed_privates"]
            if str(event.user_id) not in subscribed_privates:
                await event.reply("您未订阅聚合链接解析功能喵~")
                return
            self.config["subscribed_privates"].remove(str(event.user_id))
        await event.reply("取消订阅了聚合链接解析功能喵~")


    @link_group.command("help", description="获取聚合链接解析帮助信息")
    @param("command", default="", help="指令名称", required=False)
    @require_subscription
    async def cmd_help(self, event: BaseMessageEvent, command: str = ""):
        """获取群管理帮助信息"""
        help_message = f"插件版本：{self.version}\n"
        help_generator = HelpGenerator()
        try:
            if not command:
                help_message += help_generator.generate_group_help(self.link_group)
            else:
                command_obj = self.link_group.commands.get(command, None)  # type: ignore
                if not command_obj:
                    await event.reply(f"未找到指令 {command} 喵，请确认指令名称是否正确喵~")
                    return
                help_message += help_generator.generate_command_help(command_obj)
            await event.reply(help_message)
        except Exception as e:
            await event.reply(f"生成帮助信息时出错了喵：\n{e}")
    
    # ===== 内部方法 =====
    async def _resolve_link(self, event: BaseMessageEvent, url: str):
        try:
            # 使用resolver解析链接
            results = await resolve_link(url)
            
            if not results:
                return
            
            # 渲染第一个结果
            result = results[0]
            resources_path = Path(self.workspace) / "resources"
            images = await render_link_result(result, self.version, resources_path)
            
            if not images:
                return
            
            # 将图片转换为base64并发送
            img_bytes = BytesIO()
            images[0].save(img_bytes, format='PNG')
            img_b64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
            
            # 使用api发送图片
            group_id = getattr(event, 'group_id', None)
            if group_id:
                await self.api.post_group_msg(group_id, image=f"base64://{img_b64}")
            else:
                await self.api.post_private_msg(event.user_id, image=f"base64://{img_b64}")
            
        except Exception as e:
            self.log.error(f"解析链接失败: {e}", exc_info=True)
            await event.reply(f"解析失败了喵……\n{str(e)}")