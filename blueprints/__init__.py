"""
DaysHub 模块化蓝图包 v2.0.0
"""
from blueprints.auth import auth_bp
from blueprints.events import events_bp
from blueprints.widget import widget_bp
from blueprints.admin import admin_bp
from blueprints.system import system_bp

__all__ = ["auth_bp", "events_bp", "widget_bp", "admin_bp", "system_bp"]
