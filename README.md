# 📅 DaysHub · 时光看板 v1.2.0

> 农历 + 公历双轨倒数日 / 纪念日 / 累计日管理中心
> Docker 一键部署 · 密码认证 · 多通道推送 · iCal 日历订阅 · 事件级提醒

## ✨ 功能一览

| 模块 | 功能 |
|:---|:---|
| **日期引擎** | 公历/农历双向换算、倒数日、累计日、100/1000天里程碑、年/月进度条、24节气(2024-2035)、生肖天干地支 |
| **事件管理** | 7大分类、备注备忘、置顶、搜索筛选、事件历史时间线、Web端增删改查、**每事件单独提前提醒天数(默认3天)** |
| **通知推送** | 企业微信Webhook、SMTP邮件(HTML+纯文本回退)、TelegramBot、通用自定义Webhook、推送失败重试 |
| **认证安全** | **全站密码认证**(登录页)、密码本地存一年、退出登录、WebUI修改密码、所有API均需认证 |
| **设置页面** | **WebUI内配置推送通道**、修改密码，无需改配置文件重启 |
| **日历集成** | iCal订阅链接一键导入Google/Apple Calendar、农历自动转公历 |
| **前端** | 彩色卡片UI、暗色模式、搜索筛选、排序按钮、统计仪表盘、响应式、公历农历双向同步 |
| **部署** | Docker多阶段构建、HEALTHCHECK、环境变量配置、tzdata时区 |

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

## 🔌 API 速查

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/api/login` | 密码验证登录 |
| GET | `/api/dashboard` | 完整看板数据 |
| GET | `/api/events` | 所有事件（含计算字段） |
| GET | `/api/events/search?q=xx&category=xx` | 搜索事件 |
| POST | `/api/events` | 创建事件 |
| PUT | `/api/events/:id` | 更新事件 |
| DELETE | `/api/events/:id` | 删除事件 |
| GET | `/api/events/:id/timeline` | 事件历史时间线 |
| GET | `/api/lunar/:date` | 公历转农历 |
| GET | `/api/lunar_to_solar/:y/:m/:d` | 农历转公历 |
| GET | `/api/calendar.ics` | iCal订阅源 |
| GET | `/api/export` | 导出JSON |
| POST | `/api/import?replace=true` | 导入JSON |
| GET | `/api/settings/push` | 获取推送设置 |
| PUT | `/api/settings/push` | 保存推送设置 |
| PUT | `/api/settings/password` | 修改密码 |
| POST | `/api/notify/test` | 测试推送 |
| GET | `/health` | 健康检查（免认证） |

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