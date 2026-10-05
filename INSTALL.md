# 安装教程

本项目需要 **Home Assistant OS（HAOS）**。先安装浏览器加载项，再安装 HA 集成。

## 1. 安装浏览器加载项

1. 在 HAOS 安装并启动 **Samba share**，启用 `local_apps` 共享。
2. 下载并解压[浏览器加载项 ZIP](https://github.com/cumtwjq/china-mobile-10086-ha/releases/download/v0.3.2/china_mobile_10086-haos-app.zip)。在 Windows 文件资源管理器打开 `\\HA的IP地址\local_apps`，把解压得到的 `china_mobile_browser` 文件夹复制进去。
3. 确认文件位于 `\\HA的IP地址\local_apps\china_mobile_browser\config.yaml`。如果 Samba 显示的是 `addons` 共享，可用 `\\HA的IP地址\addons\china_mobile_browser\config.yaml`。
4. 在 HA 中打开“设置 → 应用 → 应用商店”，点右上角“检查更新”，安装并启动“中国移动10086浏览器”。首次安装需要构建镜像，可能较慢。

## 2. 安装 HA 集成

下载并解压[HA 集成 ZIP](https://github.com/cumtwjq/china-mobile-10086-ha/releases/download/v0.3.0/china_mobile_10086-experimental.zip)，把 `custom_components/china_mobile_10086` 文件夹复制到 HA 配置目录的 `custom_components` 中，然后重启 Home Assistant。

## 3. 登录账号

在“设置 → 设备与服务 → 添加集成”中搜索“中国移动10086”。输入手机号，收到短信后在下一步输入验证码。若网页要求滑块验证，打开加载项界面手动完成。请勿分享验证码或浏览器登录数据。

添加第二个手机号时，重复“添加集成”；不要在已有账号的“重新认证”中更换手机号。每个账号会显示为单独的集成和设备。

## 更新与排查

- **只更新加载项到 0.3.2：**覆盖 `local_apps` 中的加载项文件，在应用商店检查更新并更新加载项；不用重装集成或重启 HA。
- **从更早版本升级两个包：**先更新并启动加载项，再覆盖集成文件、重启 HA。原浏览器登录状态通常会保留。
- **传感器不可用：**先确认加载项正在运行，再看“浏览器登录状态”。显示 `login_required` 时，在对应集成卡片选择“重新认证”；显示 `query_failed` 时，查看加载项界面和日志。
- 加载项约每 **30 分钟**查询中国移动网页；集成每 **5 分钟**读取本地结果。网页登录状态失效后可能需要重新收取短信验证码。
