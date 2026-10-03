// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: deep-purple; icon-glyph: calendar-alt;

/**
 * DaysHub · 时光看板 iOS Scriptable 极简桌面小组件
 * 
 * 适用于: iPhone / iPad 桌面小组件 (Small / Medium 尺寸完美支持)
 * 数据源: DaysHub v2.0.0 专属极简小组件接口 (/api/widget/summary)
 *
 * 【快速使用方法】:
 * 1. 在 App Store 下载免费应用「Scriptable」
 * 2. 打开 Scriptable，点击右上角「+」新建脚本，清空原有内容并将本文件代码全部粘贴进去
 * 3. 修改下方的 BASE_URL 为你的 DaysHub 访问地址（例如 Tailscale IP 或域名）
 * 4. 修改下方的 TOKEN 为你的 DaysHub 专属登录 Token 或独立密码
 * 5. 点击右下角运行图标测试预览，确认数据显示正常
 * 6. 返回手机主屏幕长按空白处 -> 添加小组件 -> 选择 Scriptable -> 选择此脚本即可！
 */

// ========== 配置区域 (请填写你的服务地址与Token) ==========
const CONFIG = {
  // DaysHub 服务地址 (末尾不要带斜杠)
  // 支持内网 IP (如 Tailscale 100.64.0.5:5217) 或公网反代域名 (如 https://days.example.com)
  baseUrl: "http://100.64.0.5:5217",

  // 认证 Token (可在 DaysHub 设置中查看，或直接填你的登录密码)
  token: "lwd199592",

  // 小组件点击后跳转打开的 URL
  openUrl: "http://100.64.0.5:5217",

  // 刷新缓存间隔 (分钟)
  refreshMinutes: 30
};

// ========== 主执行流程 ==========
async function run() {
  const widget = await createWidget();
  if (config.runsInWidget) {
    Script.setWidget(widget);
  } else {
    // 在应用内调试时，根据屏幕预览中号卡片
    widget.presentMedium();
  }
  Script.complete();
}

async function createWidget() {
  const widget = new ListWidget();
  widget.url = CONFIG.openUrl;
  widget.setPadding(12, 14, 12, 14);

  // 设置自适应渐变背景
  const isDark = Device.isUsingDarkAppearance();
  const gradient = new LinearGradient();
  if (isDark) {
    gradient.colors = [new Color("#1a1c23"), new Color("#121317")];
    gradient.locations = [0.0, 1.0];
  } else {
    gradient.colors = [new Color("#ffffff"), new Color("#f4f6fa")];
    gradient.locations = [0.0, 1.0];
  }
  widget.backgroundGradient = gradient;

  // 拉取数据
  let data = null;
  try {
    data = await fetchSummaryData();
  } catch (err) {
    renderError(widget, err.message, isDark);
    return widget;
  }

  const widgetFamily = config.widgetFamily || "medium";
  if (widgetFamily === "small") {
    renderSmallWidget(widget, data, isDark);
  } else {
    renderMediumWidget(widget, data, isDark);
  }

  // 设定下一次更新时间
  const nextRefresh = new Date(Date.now() + CONFIG.refreshMinutes * 60 * 1000);
  widget.refreshAfterDate = nextRefresh;

  return widget;
}

// ========== 数据拉取 ==========
async function fetchSummaryData() {
  const url = `${CONFIG.baseUrl}/api/widget/summary?token=${encodeURIComponent(CONFIG.token)}`;
  const req = new Request(url);
  req.timeoutInterval = 8;
  const json = await req.loadJSON();
  if (!json || !json.ok) {
    throw new Error(json.error || "服务接口返回异常");
  }
  return json;
}

// ========== 中尺寸小组件 (Medium) 布局 ==========
function renderMediumWidget(widget, data, isDark) {
  const primaryText = isDark ? new Color("#f1f5f9") : new Color("#1e293b");
  const secondaryText = isDark ? new Color("#94a3b8") : new Color("#64748b");
  const accentColor = new Color("#6366f1");

  // 1. 顶部栏: 日期 / 星期 / 农历 / 年进度
  const headerStack = widget.addStack();
  headerStack.layoutHorizontally();
  headerStack.centerAlignContent();

  const dateTxt = headerStack.addText(`${data.date.substring(5)} ${data.weekday}`);
  dateTxt.font = Font.boldSystemFont(12);
  dateTxt.textColor = primaryText;

  headerStack.addSpacer(6);

  const lunarTxt = headerStack.addText(`· ${data.lunar.replace(/农历\d+年/, '')}`);
  lunarTxt.font = Font.systemFont(11);
  lunarTxt.textColor = secondaryText;

  headerStack.addSpacer();

  // 年进度胶囊标签
  const progStack = headerStack.addStack();
  progStack.backgroundColor = isDark ? new Color("#2e3440") : new Color("#e2e8f0");
  progStack.cornerRadius = 4;
  progStack.setPadding(2, 6, 2, 6);
  const progTxt = progStack.addText(`年进度 ${data.progress.year_percent}%`);
  progTxt.font = Font.mediumSystemFont(10);
  progTxt.textColor = isDark ? new Color("#cbd5e1") : new Color("#475569");

  widget.addSpacer(8);

  // 2. 主体左右分栏
  const bodyStack = widget.addStack();
  bodyStack.layoutHorizontally();
  bodyStack.centerAlignContent();

  // 左侧: 焦点主倒计时事件卡片
  const leftStack = bodyStack.addStack();
  leftStack.layoutVertically();
  leftStack.backgroundColor = isDark ? new Color("#242731") : new Color("#f8fafc");
  leftStack.cornerRadius = 8;
  leftStack.setPadding(8, 10, 8, 10);

  const nextEv = data.next_event;
  if (nextEv) {
    const focusTitleStack = leftStack.addStack();
    focusTitleStack.layoutHorizontally();
    const iconTxt = focusTitleStack.addText(nextEv.icon || "⏳");
    iconTxt.font = Font.systemFont(12);
    focusTitleStack.addSpacer(4);
    const titleTxt = focusTitleStack.addText(nextEv.title);
    titleTxt.font = Font.boldSystemFont(13);
    titleTxt.textColor = primaryText;
    titleTxt.lineLimit = 1;

    leftStack.addSpacer(2);

    const daysStack = leftStack.addStack();
    daysStack.layoutHorizontally();
    daysStack.bottomAlignContent();
    const daysNum = daysStack.addText(`${nextEv.days}`);
    daysNum.font = Font.boldSystemFont(28);
    daysNum.textColor = accentColor;
    daysStack.addSpacer(3);
    const unitTxt = daysStack.addText("天后");
    unitTxt.font = Font.systemFont(11);
    unitTxt.textColor = secondaryText;

    leftStack.addSpacer(2);

    const subTxt = leftStack.addText(nextEv.sub || nextEv.date);
    subTxt.font = Font.systemFont(10);
    subTxt.textColor = secondaryText;
    subTxt.lineLimit = 1;
  } else {
    const noEvTxt = leftStack.addText("暂无近期倒数事件");
    noEvTxt.font = Font.systemFont(12);
    noEvTxt.textColor = secondaryText;
  }

  bodyStack.addSpacer(10);

  // 右侧: 近期后续事件列表
  const rightStack = bodyStack.addStack();
  rightStack.layoutVertically();

  const topList = (data.top_events || []).slice(1, 4);
  if (topList.length > 0) {
    for (const ev of topList) {
      const row = rightStack.addStack();
      row.layoutHorizontally();
      row.centerAlignContent();

      const rIcon = row.addText(ev.icon || "📅");
      rIcon.font = Font.systemFont(11);
      row.addSpacer(4);

      const rTitle = row.addText(ev.title);
      rTitle.font = Font.systemFont(12);
      rTitle.textColor = primaryText;
      rTitle.lineLimit = 1;

      row.addSpacer();

      const rDays = row.addText(`${ev.days}天`);
      rDays.font = Font.boldSystemFont(11);
      rDays.textColor = accentColor;

      rightStack.addSpacer(4);
    }
  } else if (data.accumulate_highlight) {
    // 如果没有后续倒数事件，展示累计里程碑
    const row = rightStack.addStack();
    row.layoutVertically();
    const accTitle = row.addText(`💝 ${data.accumulate_highlight.title}`);
    accTitle.font = Font.boldSystemFont(12);
    accTitle.textColor = primaryText;
    const accDays = row.addText(`已累计 ${data.accumulate_highlight.days_passed} 天`);
    accDays.font = Font.systemFont(11);
    accDays.textColor = secondaryText;
  } else {
    const emptyTxt = rightStack.addText("保持热爱，奔赴山海 ✨");
    emptyTxt.font = Font.systemFont(11);
    emptyTxt.textColor = secondaryText;
  }
}

// ========== 小尺寸小组件 (Small) 布局 ==========
function renderSmallWidget(widget, data, isDark) {
  const primaryText = isDark ? new Color("#f1f5f9") : new Color("#1e293b");
  const secondaryText = isDark ? new Color("#94a3b8") : new Color("#64748b");
  const accentColor = new Color("#6366f1");

  // 顶部
  const dateTxt = widget.addText(`${data.date.substring(5)} ${data.weekday}`);
  dateTxt.font = Font.boldSystemFont(11);
  dateTxt.textColor = primaryText;

  const lunarTxt = widget.addText(data.lunar.replace(/农历\d+年/, ''));
  lunarTxt.font = Font.systemFont(10);
  lunarTxt.textColor = secondaryText;

  widget.addSpacer(6);

  // 焦点事件
  const ev = data.next_event;
  if (ev) {
    const titleStack = widget.addStack();
    titleStack.layoutHorizontally();
    const iconTxt = titleStack.addText(ev.icon || "⏳");
    iconTxt.font = Font.systemFont(11);
    titleStack.addSpacer(3);
    const titleTxt = titleStack.addText(ev.title);
    titleTxt.font = Font.boldSystemFont(12);
    titleTxt.textColor = primaryText;
    titleTxt.lineLimit = 1;

    widget.addSpacer(1);

    const daysStack = widget.addStack();
    daysStack.layoutHorizontally();
    daysStack.bottomAlignContent();
    const daysNum = daysStack.addText(`${ev.days}`);
    daysNum.font = Font.boldSystemFont(26);
    daysNum.textColor = accentColor;
    daysStack.addSpacer(2);
    const unitTxt = daysStack.addText("天后");
    unitTxt.font = Font.systemFont(10);
    unitTxt.textColor = secondaryText;
  } else {
    const emptyTxt = widget.addText("暂无倒计时");
    emptyTxt.font = Font.systemFont(12);
    emptyTxt.textColor = secondaryText;
  }

  widget.addSpacer();

  // 底部年进度
  const progTxt = widget.addText(`年进度 ${data.progress.year_percent}% (剩${data.progress.year_remaining_days}天)`);
  progTxt.font = Font.systemFont(9);
  progTxt.textColor = secondaryText;
}

// ========== 错误视图 ==========
function renderError(widget, message, isDark) {
  const errTitle = widget.addText("⚠️ DaysHub 离线");
  errTitle.font = Font.boldSystemFont(12);
  errTitle.textColor = new Color("#ef4444");

  widget.addSpacer(4);

  const errMsg = widget.addText(message || "请检查网络或Token");
  errMsg.font = Font.systemFont(10);
  errMsg.textColor = isDark ? new Color("#94a3b8") : new Color("#64748b");
}

// 执行脚本
await run();
