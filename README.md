# 📅 DaysHub · 时光看板 v1.4.0

> 农历 + 公历双轨倒数日 / 纪念日 / 累计日管理中心
> Docker 一键部署 · 多用户与后台管理 · 独立反代支持 (127.0.0.1) · 独立 iCal 订阅 · Waitress 生产 WSGI

## ✨ 功能一览

| 模块 | 功能 |
|:---|:---|
| **多用户与权限** | **多用户登录、管理员与普通用户角色分离、用户增删改查、密码安全重置、Token 鉴权** |
| **日期引擎** | 公历/农历双向换算、小月30日平滑容错、倒数日、累计日、100/1000天里程碑、年/月进度条、24节气(2024-2035)、生肖天干地支 |
| **事件管理** | 7大分类、备注备忘、置顶、搜索防抖(250ms)、事件历史时间线、Web端增删改查、**每事件单独提前提醒天数(默认3天)**、农历/公历状态彻底解耦 |
| **通知推送** | 企业微信Webhook、SMTP邮件(HTML+纯文本回退)、TelegramBot、通用自定义Webhook、推送失败重试与实时反馈 |
| **认证与安全** | **全站登录认证**、**登录防爆破(5次失败锁定10分钟)**、**iCal 独立只读 Token(与主密码解耦)**、PBKDF2-SHA256 安全哈希 |
| **设置中心** | **多选项卡分页设置面板**(推送通知 / 数据与备份 / 安全密码 / 用户管理)、自动备份策略可配、修改密码 |
| **日历集成** | iCal 独立订阅链接一键导入 Google/Apple Calendar、农历自动转公历、全设备安全同步 |
| **现代前端** | 纯单色矢量 SVG 导航栏、毛玻璃悬浮交互、轻量 Toast 提示、暗色模式、PWA 原生支持(添加到主屏幕) |
| **部署与反代** | **默认绑定 127.0.0.1:5217 (便于 Nginx/1Panel/Caddy 等直接反向代理)**、Waitress 多线程生产 WSGI、HEALTHCHECK |

## 🏗️ 架构

```
┌──────────────────────────────────────────────────┐
│                  DaysHub v1.2.0                  │
├────────────┬────────────┬───────────┬────────────┤
│  日期引擎   │  事件管理   │  推送中心  │  认证/设置  │
├────────────┼────────────┼───────────┼────────────┤
│ lunar_engine│  models    │ notifier  │  config    │
│ ·公历农历   │ ·SQLite    │ ·企微Webhook│ ·密码认证  │
│ ·24节气     │ ·CRUD      │ ·SMTP邮件 │ ·密码修改  │
│ ·里程碑     │ ·历史记录   │ ·TG Bot   │ ·推送配置  │
│ ·进度条     │ ·搜索筛选   │ ·通用Webhook│           │
│ ·生肖干支   │ ·事件提醒   │ ·重试+告警 │            │
├────────────┴────────────┴───────────┴────────────┤
│            Flask (app.py) + APScheduler          │
├──────────────────────────────────────────────────┤
│     Docker (多阶段构建 + HEALTHCHECK) · 5217     │
└──────────────────────────────────────────────────┘
```

## 🚀 Docker 部署

```bash
# 1. 克隆
git clone https://github.com/YOUR_USERNAME/dayshub.git
cd dayshub

# 2. 配置密码（创建 .env）
cat > .env << 'EOF'
DAYSHUB_SECRET_KEY=your-random-secret-key
DAYSHUB_API_TOKEN=your-password
DAYSHUB_TZ=Asia/Shanghai
DAYSHUB_BASE_URL=http://localhost:5217
EOF

# 3. 启动
docker compose up -d

# 4. 访问
# http://localhost:5217
# 输入你设置的 DAYSHUB_API_TOKEN 作为密码
```

## 🔒 认证机制

- **全站密码认证**：未登录看不到任何内容，所有 API 均需密码
- 密码保存在浏览器 localStorage，有效期一年
- 底栏 🚪 退出 按钮可清除密码回到登录页
- **WebUI 内修改密码**：设置 → 修改密码（验证旧密码后设置新密码，存 DB）
- 登录端点 `POST /api/login` 验证密码并返回 token
- 所有 API 请求需在 Header 中携带 `Authorization: Bearer <密码>` 或 iCal 订阅用 `?token=<密码>`

## 🔔 推送设置

所有推送通道在 **WebUI 设置页面** 配置，保存到数据库，无需重启：

| 通道 | 配置项 |
|:---|:---|
| 企业微信 | Webhook URL |
| 邮件 SMTP | 主机/端口/账号/密码/发件人/收件人/SSL |
| Telegram | Bot Token / Chat ID |

- **每事件单独提前提醒**：创建/编辑事件时可设置"提前提醒天数"，默认 3 天
- 设置页面的「测试推送」按钮可验证各通道是否正常，返回各通道成功/失败状态
- 提醒消息格式：分隔线 + emoji + 农历/公历双显示

## 📅 Google Calendar 订阅

1. 登录 DaysHub → 底部点击「📅 日历」
2. 复制订阅链接（已自动附带密码参数）
3. Google Calendar → 左侧「其他日历 +」→「通过网址添加」→ 粘贴链接
4. 农历生日/纪念日自动转公历，全设备同步

## 🌐 Nginx 反向代理配置参考

由于 DaysHub 默认绑定本机 `127.0.0.1:5217`，可直接在宿主机 Nginx / 1Panel / OpenResty 中添加反代配置：

```nginx
server {
    listen 80;
    server_name days.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5217;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔌 API 速查

| 方法 | 路径 | 权限 | 说明 |
|:---|:---|:---:|:---|
| POST | `/api/login` | 公开 | 用户名密码登录 / Token 颁发 |
| GET | `/api/user/profile` | 登录用户 | 获取当前登录用户信息 |
| GET | `/api/admin/users` | 管理员 | 用户列表管理 |
| POST | `/api/admin/users` | 管理员 | 创建新系统用户 |
| PUT | `/api/admin/users/:id` | 管理员 | 修改用户信息 / 重置密码 |
| DELETE | `/api/admin/users/:id` | 管理员 | 删除指定用户 |
| GET | `/api/dashboard` | 登录用户 | 完整看板数据 |
| GET | `/api/events` | 登录用户 | 事件列表 |
| POST | `/api/events` | 登录用户 | 创建事件 |
| PUT | `/api/events/:id` | 登录用户 | 更新事件 |
| DELETE | `/api/events/:id` | 登录用户 | 删除事件 |
| GET | `/api/calendar.ics` | 独立 Token | iCal 只读订阅源 |
| GET | `/api/settings/backup` | 登录用户 | 获取自动备份配置 |
| PUT | `/api/settings/backup` | 登录用户 | 保存自动备份配置（热重载调度） |
| POST | `/api/backup` | 登录用户 | 立即创建全量备份 |
| GET | `/api/settings/push` | 登录用户 | 获取推送设置 |
| PUT | `/api/settings/push` | 登录用户 | 保存推送设置 |
| PUT | `/api/settings/password` | 登录用户 | 用户修改密码 |
| GET | `/health` | 公开 | 健康检查（Waitress 状态） |

> 所有 API 除 `/api/login` 和 `/health` 外均需密码认证。

## 📁 项目结构

```
dayshub/
├── app.py              # Flask主应用 (路由+认证+API)
├── config.py           # 配置 + 推送配置DB读写 + 密码修改
├── lunar_engine.py     # 农历引擎 (换算+节气+里程碑+进度)
├── models.py           # SQLite CRUD + 事件历史 + advance_days
├── calendar_gen.py     # iCal生成器
├── notifier.py         # 推送 (企微+邮件+TG+Webhook+重试+测试)
├── scheduler.py        # 定时任务 (每小时提醒检查)
├── logger.py           # 日志框架
├── requirements.txt
├── Dockerfile          # 多阶段构建 + tzdata + HEALTHCHECK
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── LICENSE             # MIT
├── examples/
│   └── sample-events.json
├── templates/
│   └── index.html      # WebUI (登录页+看板+设置页)
├── static/
│   ├── style.css
│   └── app.js
└── data/               # SQLite数据库（运行时生成）
```

## 🏗️ 技术栈

- Python 3.12 + Flask 3.0 + SQLite + APScheduler
- zhdate (农历) + requests (推送)
- 原生 HTML/CSS/JS (无框架)
- Docker 多阶段构建

## 📝 Changelog

### v1.4.0 (多用户与后台管理系统)
- 👥 **多用户管理系统**：新增 users / user_tokens 表，支持管理员与普通用户角色分离
- 🛡️ **反向代理适配**：默认绑定 `127.0.0.1:5217`，配合宿主机 Nginx/1Panel/Caddy 安全反代与 SSL 证书
- 🔐 **PBKDF2-SHA256 安全哈希**：所有用户密码均采用强哈希算法加密存储
- ⚙️ **分页式后台管理面板**：设置中心集成「用户管理」分页，支持一键创建、编辑、重置密码及停用
- 🔄 **事件归属绑定**：所有创建事件自动关联创建用户，支持平滑迁移已有数据

### v1.3.0 (安全加固与工程优化)
- 🛡️ **内网端口绑定**：`docker-compose.yml` 默认绑定 `100.64.0.1:5217:5217`，阻断公网暴露隐患
- 🔒 **登录防爆破机制**：`/api/login` 引入 IP 频控，连续 5 次失败自动锁定 10 分钟 (429)
- 🔑 **iCal 订阅 Token 解耦**：独立生成只读 `ical_token`，与后台管理主密码彻底分离，且支持在 UI 中一键安全重置
- 🐛 **取消农历残留 Bug 修复**：编辑事件取消农历时显式清空数据库 `lunar_month` / `lunar_day`
- 📅 **农历小月 30 日平滑容错**：`lunar_to_solar` 遇小月无 30 日时自动平滑降级至 29 日
- 🚀 **Waitress 生产 WSGI**：引入多线程生产级 WSGI 服务器，替代 Flask 内置开发服务器
- 🧹 **死代码与冗余清理**：彻底移除 `notifier.py` 中已废弃的旧晨报生成函数及孤儿代码
- 🔍 **前端搜索防抖**：添加 250ms 输入防抖，避免高频请求
- ⚠️ **数据导入安全确认**：导入 JSON 前增加破坏性覆盖确认弹窗

### v1.2.0
- 🔑 全站密码认证（登录页 + 一年有效期 + 退出按钮）
- ⚙️ 独立设置页面（推送配置 + 密码修改）
- 🔔 每事件单独提前提醒天数（默认3天）
- 📅 公历农历双向直接同步表单值
- 🔄 四个列表标签增加排序按钮
- 📋 全部标签移到最前面
- ❌ 去掉晨报功能，只保留事件提醒
- 🎨 推送内容美化（分隔线 + emoji）
- ✅ 推送测试返回各通道成功/失败详情
- 🎨 统一所有输入框样式

### v1.1.0 (鲁班打磨)
- API Token 认证中间件
- Dockerfile 多阶段构建 + HEALTHCHECK
- 前端搜索/筛选栏 + 自定义确认弹窗
- 事件历史时间线
- 推送失败重试机制
- 节气表扩展 2024-2035
- logging框架替换print

### v1.0.0 (初始版本)
- 农历引擎+倒数/累计/循环+里程碑+进度条
- 多通道推送 (邮件+企微+TG+Webhook)
- iCal日历订阅
- RESTful API
- 彩色卡片UI+暗色模式

## License

MIT