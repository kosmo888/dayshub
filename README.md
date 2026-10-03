# 📅 DaysHub · 时光看板 v2.0.0

[English](README_EN.md) | **简体中文**

[![Release](https://img.shields.io/badge/release-v2.0.0-6366f1.svg?style=flat-square)](https://github.com/kosmo888/dayshub)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg?style=flat-square)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ed.svg?style=flat-square)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-37%2F37%20passing-success.svg?style=flat-square)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

> **农历 + 公历双轨倒数日 / 纪念日 / 累计日时光中枢**  
> 专为极客家庭、自托管玩家打造。支持农历闰月双向换算、iOS/Android 极简小组件、Home Assistant 智能家居中枢、多用户强数据隔离、双通道操作审计流水与 Waitress 高性能多线程生产驱动。

---

## ✨ 核心特性与套件生态

| 核心套件 | 详细功能说明 |
| :--- | :--- |
| **🌙 双轨农历引擎** | 支持中国传统农历与公历双轨并行；**独创闰月精准识别与双向联动**（表单自适应闰月、换算 API 带 `is_leap`、卡片高亮标注“农历闰X月Y日”）；支持小月 30 日平滑容错、生肖干支、24 节气实时解析。 |
| **📱 极简小组件生态** | 开箱即用提供 `/api/widget/summary` 极简 JSON 接口；配套开源 **iOS Scriptable 原生桌面小组件源码**（支持 Small/Medium 尺寸与深浅色模式）及 **Widgy 配置规范**，秒级打造手机桌面时光卡片。 |
| **🏠 Home Assistant 中控** | 专属智能家居集成套件；提供 RESTful 传感器声明与 Lovelace 仪表盘卡片 YAML，家庭中控平板、墙面屏或桌面墨水屏直接常驻展示倒数日与年/月流逝进度。 |
| **📋 双通道日志系统** | **通道 A**：全链路业务操作审计流水（登录/登出、注册、事件增删改、系统配置变更、数据导入备份）；<br>**通道 B**：后端服务实时运行日志（`data/dayshub.log` 自动 5MB 轮转，后台支持免 SSH 直接调阅最新输出）。 |
| **🔒 多用户与安全防御** | 支持管理员与普通用户角色分离；访客自主注册策略控制；事件与个人操作流水**物理级隔离**；密码强 PBKDF2-SHA256 哈希存储；登录接口集成 IP 防暴力破解频控（5次失败锁定10分钟）；免密 iCal 独立只读 Token。 |
| **🏮 传统节日预置包** | 内置中国传统主要农历节日（春节、元宵、端午、中秋、重阳、小年、除夕等）与二十四节气标准数据包，支持网页端一键增量或全量导入。 |
| **⚙️ 生产级微架构** | **基于 Flask Blueprint 模块化解耦重构**（auth, events, widget, admin, system）；内置 Waitress 多线程生产 WSGI；支持 SQLite 在线热快照备份与一键下载。 |

---

## 🏗️ 系统微架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DaysHub v2.0.0 架构全景                         │
├───────────────────┬───────────────────┬────────────────────────────────┤
│    认证与用户     │    事件与历史     │         小组件与数据流         │
│  blueprints/auth  │ blueprints/events │       blueprints/widget        │
│  · 自主注册/登录   │  · 事件全生命CRUD │  · /api/widget/summary 极简接口│
│  · PBKDF2-SHA256  │  · 搜索防抖/分类  │  · 看板主页数据聚合/今日信息   │
│  · 个人资料与改密 │  · 导入导出/里程碑│  · 年/月流逝进度条计算         │
├───────────────────┼───────────────────┼────────────────────────────────┤
│    后台与审计     │    系统与外设     │            基础引擎            │
│  blueprints/admin │ blueprints/system │      lunar_engine / models     │
│  · 多用户管控面板 │  · 企微/邮件/TG推 │  · 农历闰月算法/小月平滑容错   │
│  · 审计多维过滤   │  · iCal 订阅生成  │  · SQLite WAL + 自动热备份     │
│  · 运行日志实时看 │  · 在线备份下载   │  · APScheduler 提醒巡检        │
├───────────────────┴───────────────────┴────────────────────────────────┤
│            Waitress 多线程生产级 WSGI (Python 3.12-slim)               │
├────────────────────────────────────────────────────────────────────────┤
│     Docker 容器化 (端口 5217 · 支持 Tailscale 内网穿透与外网反代)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速启动 (Docker 一键部署)

### 推荐：Docker Compose
```bash
# 1. 克隆代码仓库
git clone https://github.com/kosmo888/dayshub.git
cd dayshub

# 2. 复制并调整环境变量 (可选设置你的独立端口或密钥)
cat > .env << 'EOF'
DAYSHUB_SECRET_KEY=dayshub-prod-secret-2026
DAYSHUB_API_TOKEN=your-admin-password
DAYSHUB_TZ=Asia/Shanghai
DAYSHUB_PORT=5217
EOF

# 3. 启动生产容器
docker compose up -d

# 4. 访问服务
# 局域网/Tailscale: http://<你的IP>:5217/
# 默认初始管理员账号: admin，密码为你设置的 DAYSHUB_API_TOKEN
```

---

## 📱 桌面小组件与智能中控生态

DaysHub 专为移动端与智能家居生态提供了完整的现成配置模板，位于 [`examples/`](examples/) 目录：

### 1. iOS Scriptable 极简桌面小组件
* 源码文件：[`examples/widgets/dayshub_scriptable.js`](examples/widgets/dayshub_scriptable.js)
* 安装指南：[`examples/widgets/README.md`](examples/widgets/README.md)
* 特性：支持 iPhone / iPad 桌面 Small 与 Medium 尺寸，自适应深浅色模式，显示农历、年进度及下一焦点事件。

### 2. Home Assistant 智能家居集成
* 传感器配置：[`examples/homeassistant/sensor_dayshub.yaml`](examples/homeassistant/sensor_dayshub.yaml)
* 仪表盘卡片：[`examples/homeassistant/lovelace_card.yaml`](examples/homeassistant/lovelace_card.yaml)
* 接入指南：[`examples/homeassistant/README.md`](examples/homeassistant/README.md)

### 3. 中国传统节日与二十四节气预置包
* 传统主要农历节日：[`examples/presets/chinese_traditional_holidays.json`](examples/presets/chinese_traditional_holidays.json)
* 二十四节气数据包：[`examples/presets/chinese_solar_terms.json`](examples/presets/chinese_solar_terms.json)
* 使用方式：进入 DaysHub 设置 ➔ 数据与备份 ➔ 导入数据，选中 JSON 文件即可一键灌入。

---

## 🔌 API 核心端点速查

| 蓝图模块 | 请求方法 | 接口路径 | 鉴权级别 | 说明 |
| :--- | :---: | :---| :---: | :---|
| **Auth** | `POST` | `/api/login` | 公开 | 用户密码登录并颁发专属 Token |
| **Auth** | `POST` | `/api/register` | 公开 (受控) | 访客自主注册新账号 |
| **Auth** | `POST` | `/api/logout` | 登录用户 | 安全退出登录并记录审计日志 |
| **Auth** | `GET` | `/api/user/profile` | 登录用户 | 获取当前登录用户画像与角色 |
| **Auth** | `PUT` | `/api/settings/password` | 登录用户 | 修改当前用户密码 |
| **Widget** | `GET` | `/api/widget/summary` | Token (Header/Query) | **桌面小组件专属一站式极简 JSON 接口** |
| **Widget** | `GET` | `/api/dashboard` | 登录用户 | 看板主数据（倒数、累计、重复、进度） |
| **Widget** | `GET` | `/api/today` | 登录用户 | 今日到期事件与日历状态 |
| **Widget** | `GET` | `/api/progress` | 登录用户 | 年月流逝百分比与剩余天数 |
| **Widget** | `GET` | `/api/lunar_to_solar/:y/:m/:d` | 登录用户 | 农历转公历（带 `?is_leap=1` 闰月支持） |
| **Events** | `GET` | `/api/events` | 登录用户 | 事件列表（严格多用户数据隔离） |
| **Events** | `POST` | `/api/events` | 登录用户 | 创建倒计时 / 累计日 / 周期事件 |
| **Events** | `PUT` | `/api/events/:id` | 登录用户 | 更新事件（属性、置顶、提前提醒等） |
| **Events** | `DELETE`| `/api/events/:id` | 登录用户 | 删除事件（防越权拦截） |
| **Events** | `GET` | `/api/events/:id/timeline` | 登录用户 | 查询事件时间线与百日/千日里程碑 |
| **Events** | `GET` | `/api/export` | 登录用户 | 导出当前用户名下所有事件 JSON |
| **Events** | `POST` | `/api/import` | 登录用户 | 导入事件（支持纯列表与标准结构） |
| **Admin** | `GET` | `/api/admin/users` | 管理员 | 系统全量用户列表 |
| **Admin** | `PUT` | `/api/admin/system` | 管理员 | 控制是否允许访客自主注册 |
| **Admin** | `GET` | `/api/admin/logs` | 管理员 | **系统全量审计流水（支持模块/关键字过滤）** |
| **Admin** | `GET` | `/api/user/logs` | 登录用户 | **普通用户个人操作审计日志** |
| **Admin** | `GET` | `/api/admin/runtime_logs` | 管理员 | **后端服务运行日志实时抽取 (dayshub.log)** |
| **System**| `POST` | `/api/backup` | 登录用户 | 触发数据库热快照与 JSON 导出备份 |
| **System**| `GET` | `/api/backup/download/:file`| 管理员 | 下载历史备份快照文件 |
| **System**| `GET` | `/api/calendar.ics` | 独立 Token | 标准 RFC-5545 iCal 订阅源 |

---

## 📁 目录结构

```text
dayshub/
├── app.py                     # Flask 应用工厂入口 (轻量化初始化与调度挂载)
├── auth_middleware.py         # 认证中间件、管理员守门器与审计日志记录器
├── config.py                  # 系统配置与环境变量映射
├── lunar_engine.py            # 农历核心引擎 (双向转换、节气、生肖、里程碑)
├── models.py                  # SQLite 数据模型与 CRUD
├── calendar_gen.py            # RFC-5545 iCal 日历订阅流生成器
├── notifier.py                # 多通道通知中心 (企业微信、SMTP、Telegram、Webhook)
├── scheduler.py               # APScheduler 定时任务引擎
├── logger.py                  # 双通道日志轮转处理器 (data/dayshub.log)
├── blueprints/                # 模块化解耦业务蓝图
│   ├── __init__.py
│   ├── auth.py                # 登录、注册、鉴权、个人资料
│   ├── events.py              # 事件管理 CRUD、导入导出
│   ├── widget.py              # 极简小组件、聚合看板、农历转换
│   ├── admin.py               # 用户管理、审计日志、服务日志
│   └── system.py              # 页面入口、推送测试、备份下载、iCal
├── examples/                  # 生态套件包
│   ├── sample-events.json     # 示例数据
│   ├── widgets/               # 桌面小组件源码 (iOS Scriptable 脚本)
│   ├── homeassistant/         # 智能家居配置 (REST 传感器与 Lovelace 卡片)
│   └── presets/               # 节日与二十四节气预置数据包
├── templates/
│   └── index.html             # 现代化单页看板与多选项卡管理面板
├── static/
│   ├── style.css              # 现代极简 CSS 变量规范
│   └── app.js                 # 原生 JavaScript (0 第三方框架依赖)
├── tests/                     # 自动化测试套件 (37 项 E2E 测试全覆盖)
│   ├── test_dayshub.py        # 算法与数据模型单元测试
│   └── test_e2e_full.py       # 全系统链路集成验收测试
├── Dockerfile                 # 多阶段精简镜像构建
└── docker-compose.yml         # 容器编排定义
```

---

## 📝 版本更新历史 (Changelog)

### v2.0.0 (架构微服务化与生态扩展套件)
- 🚀 **微架构蓝图模块化**：将单体路由全面重构解耦为 Flask Blueprint（auth, events, widget, admin, system），大幅提升工程健壮性与可维护性；
- 📱 **iOS Scriptable 桌面小组件包**：开源首发开箱即用的 Scriptable 脚本（支持小号/中号卡片、深浅色模式）；
- 🏠 **Home Assistant 智能家居中枢支持**：提供 REST 传感器及 Lovelace 仪表盘配置包，支持家庭中控大屏与桌面副屏；
- 🏮 **传统农历节日与二十四节气预置包**：内置主要传统农历节日及二十四节气标准数据，支持一键灌入；
- 🛡️ **安全加固与 XSS 防御**：前端全面加入 `escapeHtml` 机制，修复里程碑时间序列化与严格多用户数据隔离；
- 🧪 **自动化测试扩充**：E2E 深度集成测试用例扩展至 37 项，通过率保持 100%。

### v1.7.0 (系统操作与审计日志系统)
- 📋 **双通道日志体系**：新增 `system_logs` 表记录全链路操作流水，新增 `dayshub.log` 服务运行日志自动 5MB 轮转写入；
- 🔍 **管理后台日志控制台**：提供操作审计检索与服务运行日志直接查看双视图。

### v1.6.0 (农历闰月适配与极简小组件接口)
- 🌙 **农历“闰月”精准标识**：表单新增“闰月”勾选与双向换算，卡片标识“农历闰X月Y日”；
- 📱 **专属极简小组件接口 (`/api/widget/summary`)**：面向第三方桌面组件输出精简结构化 JSON。

---

## 📄 开源许可证

本项目采用 [MIT License](LICENSE) 开源协议。
