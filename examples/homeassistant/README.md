# 🏠 DaysHub · Home Assistant 智能家居中控集成指南

利用 DaysHub 专为桌面小组件与智能中枢打造的极简 JSON 接口 `/api/widget/summary`，可以轻松将农历信息、时间流逝进度与重要倒数日接入 Home Assistant，在家庭中控平板、墙面屏或桌面副屏上常驻呈现。

---

## 接入三步走

### 1. 配置 REST 传感器
将本目录下的 [sensor_dayshub.yaml](sensor_dayshub.yaml) 内容添加到你的 Home Assistant `configuration.yaml` 中。

> **注意**：
> 将其中的 `http://100.64.0.5:5217` 替换为你 DaysHub 的内网 IP（如 Tailscale IP 或局域网 IP），`token` 替换为你的登录密码或专属 Token。

保存后，在 Home Assistant 中点击 **「配置」->「系统」->「开发者工具」->「重新加载全部 YAML 配置」**。

### 2. 检查传感器实体
在「开发者工具」->「状态」中搜索 `dayshub`，确认以下 4 个实体已正常上线：
* `sensor.dayshub_lunar_info`：农历日期、干支、生肖与二十四节气
* `sensor.dayshub_year_progress`：年度流逝进度百分比及剩余天数
* `sensor.dayshub_next_event`：下一个焦点倒数日标题与天数属性
* `sensor.dayshub_today_count`：今日纪念日到期数及明细

### 3. 添加到 Lovelace 仪表盘
打开 Home Assistant 概览仪表盘，点击右上角菜单 -> **「编辑仪表盘」** -> **「添加卡片」** -> 滑动至底部选择 **「手动配置」**，将 [lovelace_card.yaml](lovelace_card.yaml) 的内容粘贴保存即可完成。
