# 📱 DaysHub 桌面小组件集成指南

DaysHub 提供专属极简小组件接口 `/api/widget/summary`，可无缝对接 iOS Scriptable、Widgy 以及 Android KWGT 桌面卡片。

---

## 1. iOS Scriptable 小组件安装指南 (推荐)

Scriptable 是 iOS 平台极佳的轻量桌面小组件工具，无需编译，原生运行 JavaScript。

### 步骤 1：下载应用
在 App Store 免费搜索并安装 **Scriptable**。

### 步骤 2：导入脚本
1. 打开 Scriptable，点击右上角的 **「+」** 新建脚本；
2. 打开并复制本目录下的 [dayshub_scriptable.js](dayshub_scriptable.js) 全部源码；
3. 将代码完全粘贴到 Scriptable 编辑器中；
4. 顶部标题命名为 `DaysHub`。

### 步骤 3：填写配置
修改脚本开头的 `CONFIG` 对象：
```javascript
const CONFIG = {
  // 你的 DaysHub 服务内网或外网地址 (末尾不要带斜杠)
  baseUrl: "http://100.64.0.5:5217",

  // 认证 Token (可以在 DaysHub 网页端设置中查看，或直接填你的登录密码)
  token: "your_password_or_token",

  // 点击卡片后跳转打开的链接
  openUrl: "http://100.64.0.5:5217",

  // 刷新缓存间隔 (默认 30 分钟)
  refreshMinutes: 30
};
```

### 步骤 4：添加到桌面
1. 返回 iPhone 桌面，长按空白处进入编辑模式，点击左上角 **「+」**；
2. 搜索并选择 **Scriptable**；
3. 选择 **中号 (Medium)** 或 **小号 (Small)** 小组件并添加；
4. 长按桌面上的小组件，点击 **「编辑小组件」**；
5. 在 **Script** 选项中选择刚才创建的 `DaysHub`；
6. 退出编辑，桌面即刻呈现优雅的农历公历倒数日与时间进度卡片！

---

## 2. Widgy 小组件数据源配置

在 Widgy 中：
1. 添加 **JSON (HTTP Request)** 数据源；
2. 请求地址填入：`http://<YOUR_IP>:5217/api/widget/summary?token=<YOUR_TOKEN>`；
3. 绑定所需字段：
   - `date`：公历日期
   - `weekday`：星期几
   - `lunar`：农历日期（如 `农历2026年8月24日`）
   - `progress.year_percent`：年进度百分比
   - `next_event.title`：下一个焦点事件名称
   - `next_event.days`：倒数天数
   - `next_event.sub`：农历或副标题
