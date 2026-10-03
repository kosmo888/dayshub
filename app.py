"""
DaysHub Flask 主应用 v2.0.0
- 微架构模块化重构：基于 Flask Blueprint 蓝图设计
- 业务蓝图解耦：auth, events, widget, admin, system
- 生产模式支持：Waitress 高性能多线程 WSGI 驱动
- 调度引擎：APScheduler 提醒扫描与热备份
"""
import os
from flask import Flask
from config import Config, VERSION
from logger import logger
from models import init_db, seed_example_data, get_setting, set_setting
from auth_middleware import require_auth, require_admin

# 导入业务解耦蓝图
from blueprints import auth_bp, events_bp, widget_bp, admin_bp, system_bp


def create_app():
    """Flask 应用工厂函数"""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # 启动环境诊断提示
    if not Config.auth_enabled():
        logger.warning("API_TOKEN 未设置 — API 写操作无认证保护！生产环境请务必设置 DAYSHUB_API_TOKEN")
    if Config.SECRET_KEY == "dayshub-dev-key-change-me":
        logger.warning("SECRET_KEY 使用默认值 — 生产环境请修改 DAYSHUB_SECRET_KEY")

    # 1. 初始化数据库表结构与默认管理员
    init_db()

    # 2. 首次启动加载预置示例数据
    if Config.SEED_EXAMPLES and get_setting("seeded") != "1":
        try:
            seed_example_data()
            set_setting("seeded", "1")
        except Exception as e:
            logger.warning(f"预置示例数据加载跳过: {e}")

    # 3. 注册响应头（静态资源防强缓存）
    @app.after_request
    def add_header(response):
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type or "javascript" in content_type or "css" in content_type:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # 4. 注册解耦的业务模块蓝图 (保持 100% 路由向后兼容)
    app.register_blueprint(system_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(widget_bp)
    app.register_blueprint(admin_bp)

    # 5. 启动定时任务调度器（事件扫描、提醒推送与自动数据库热备份）
    from scheduler import create_scheduler
    create_scheduler(app)

    logger.info(f"DaysHub v{VERSION} 模块化微架构启动完成 — 端口 {os.environ.get('DAYSHUB_PORT', '5217')}")
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("DAYSHUB_PORT", "5217"))
    is_dev = os.environ.get("FLASK_ENV") == "development"
    if is_dev:
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        try:
            from waitress import serve
            logger.info(f"以 Waitress 生产模式运行在端口 {port}...")
            serve(app, host="0.0.0.0", port=port, threads=6, clear_untrusted_proxy_headers=False)
        except ImportError:
            logger.warning("Waitress 未安装，回退至 Flask 内置服务器")
            app.run(host="0.0.0.0", port=port, debug=False)
