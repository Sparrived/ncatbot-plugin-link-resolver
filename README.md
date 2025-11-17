# Link Resolver Plugin

一个用于 NcatBot 的链接解析插件，可以自动识别并解析消息中的各类链接，提供内容预览和信息提取功能。

## 功能特性

- 🔗 自动识别消息中的链接
- 📱 支持多平台链接解析（B站、抖音、Twitter 等）
- ⚙️ 灵活的配置选项
- 👥 群组订阅管理

## 安装

1. 将本插件作为 submodule 添加到 plugins 目录
2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 配置

插件配置文件位于 `data/LinkResolver/LinkResolver.yaml`

```yaml
enabled: true                    # 是否启用插件
subscribed_groups: []           # 订阅的群聊列表
auto_parse: true                # 是否自动解析链接
supported_platforms:            # 支持的平台
  - bilibili
  - douyin
  - twitter
```

## 使用方法

### 命令列表

- `/link <url>` 或 `/解析链接 <url>` - 手动解析指定链接
- `/linksub` 或 `/订阅解析` - 订阅/取消订阅本群的链接自动解析

### 示例

```
/link https://www.bilibili.com/video/BV1xx411c7mD
```

## 开发

### 添加新的解析器

在 `resolvers/` 目录下创建新的解析器模块：

```python
# resolvers/example.py
async def parse(url: str) -> dict:
    """解析示例平台的链接"""
    return {
        "title": "标题",
        "description": "描述",
        "url": url
    }
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 作者

Sparrived
