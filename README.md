# 中国移动10086 Home Assistant 集成

在 Home Assistant 中查看中国移动的话费余额、流量和通话余量。适用于 **Home Assistant OS（HAOS）**：浏览器加载项负责登录和查询，集成负责显示传感器。添加账号时，在集成界面输入手机号和短信验证码。

## 下载与安装

需要安装两个包，顺序是**先加载项，后集成**：

1. [浏览器加载项 v0.3.1](https://github.com/cumtwjq/china-mobile-10086-ha/releases/download/v0.3.1/china_mobile_10086-haos-app.zip)
2. [HA 集成 v0.3.0](https://github.com/cumtwjq/china-mobile-10086-ha/releases/download/v0.3.0/china_mobile_10086-experimental.zip)

解压加载项 ZIP，把 `china_mobile_browser` 文件夹放到 HAOS 的 `local_apps` 共享目录，在应用商店检查更新并安装、启动。再把集成 ZIP 中的 `custom_components/china_mobile_10086` 放到 HA 配置目录的 `custom_components`，重启 HA。随后在“设置 → 设备与服务 → 添加集成”中搜索“中国移动10086”，输入手机号和收到的验证码。

路径示例、升级步骤和常见问题见[安装教程](INSTALL.md)。

## 使用说明

- 加载项约每 **30 分钟**查询一次；集成每 **5 分钟**读取一次本地结果。
- 需要多个账号时，再次添加“中国移动10086”集成。各账号使用独立的浏览器登录状态和 HA 设备。
- 登录失效时，在对应账号的集成卡片中选择“重新认证”。如果官方网页要求滑块验证，打开加载项界面手动完成。
- 会话过期后可能需要再次输入短信验证码；多个账号会增加 HAOS 内存占用，多账号长期运行仍需实际验证。

## 来源与鸣谢

浏览器登录与查询方式参考 [ChinaMobileMonitor](https://github.com/shiranzby/ChinaMobileMonitor)（MIT License，许可文本随加载项提供）；集成配置和重新认证流程参考 [Shaobo-Pocket-Carrier](https://github.com/Shaobor/Shaobo-Pocket-Carrier)。本项目代码和文档由 Codex 编写，感谢用户提供实际账号测试。
