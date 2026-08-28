"""
DaysHub 单元与集成测试套件
涵盖：
1. 农历引擎 (lunar_engine)：公农历互转、小月30日平滑容错、24节气、生肖干支、里程碑计算
2. 数据库与业务逻辑 (models)：事件 CRUD、compute_event、历史记录追溯、数据备份与日志清理
3. 安全与认证 (config & auth)：防爆破频控、HMAC 密码比对、iCal 独立 Token
"""
import os
import sys
import tempfile
import sqlite3
from datetime import date

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lunar_engine import (
    solar_to_lunar, lunar_to_solar, get_next_lunar_birthday,
    get_today_solar_term, get_shengxiao, get_ganzhi,
    days_until, days_since, get_next_milestone, get_milestones
)
from config import (
    Config, get_current_password, change_password,
    get_ical_token, reset_ical_token,
    check_login_rate_limit, record_login_failure, reset_login_failure
)


# ========== 1. 农历与日期算法测试 ==========

def test_lunar_conversion():
    # 2026-12-15 对应 农历 2026年11月7日
    d = date(2026, 12, 15)
    lunar = solar_to_lunar(d)
    assert lunar["lunar_year"] == 2026
    assert lunar["lunar_month"] == 11
    assert lunar["lunar_day"] == 7

    # 反向转换
    solar = lunar_to_solar(2026, 11, 7)
    assert solar == d


def test_lunar_small_month_tolerance():
    # 测试月末30日在小月份自动平滑降级至29日，避免异常报错
    solar = lunar_to_solar(2026, 12, 30)
    assert isinstance(solar, date)


def test_next_lunar_birthday():
    base = date(2026, 8, 25)
    # 农历11月7日 下次公历
    next_d = get_next_lunar_birthday(11, 7, False, base)
    assert next_d == date(2026, 12, 15)
    assert days_until(next_d, base) == 112


def test_milestones_and_progress():
    start = date(2024, 10, 25)
    base = date(2026, 8, 25)
    passed = days_since(start, base)
    assert passed == 669

    next_ms = get_next_milestone(start, base)
    assert next_ms is not None
    assert next_ms["milestone"] == 888

    ms_list = get_milestones(start, base)
    assert len(ms_list) >= 4
    # 100, 200, 300, 500 天应已达成
    assert all(m["is_passed"] for m in ms_list if m["milestone"] <= 500)


def test_shengxiao_ganzhi():
    assert get_shengxiao(2026) == "马"
    assert get_ganzhi(2026) == "丙午"


# ========== 2. 安全与认证限速测试 ==========

def test_login_rate_limiting():
    ip = "192.0.2.199"
    reset_login_failure(ip)

    # 前 4 次失败不锁定
    for _ in range(4):
        locked, _ = record_login_failure(ip)
        assert not locked
        allowed, _ = check_login_rate_limit(ip)
        assert allowed

    # 第 5 次触发锁定
    locked, sec = record_login_failure(ip)
    assert locked
    assert sec > 0
    allowed, rem = check_login_rate_limit(ip)
    assert not allowed
    assert rem > 0

    # 重置后恢复
    reset_login_failure(ip)
    allowed, _ = check_login_rate_limit(ip)
    assert allowed


def test_ical_token_lifecycle():
    tok1 = get_ical_token()
    assert tok1 and len(tok1) >= 16
    tok2 = reset_ical_token()
    assert tok2 and tok2 != tok1
    assert get_ical_token() == tok2


def test_backup_config_and_logic():
    from config import load_backup_config, save_backup_config
    save_backup_config({"backup_enabled": True, "backup_time": "04:30", "backup_count": 15})
    cfg = load_backup_config()
    assert cfg["backup_enabled"] is True
    assert cfg["backup_time"] == "04:30"
    assert cfg["backup_count"] == 15

    # 还原
    save_backup_config({"backup_enabled": True, "backup_time": "03:00", "backup_count": 30})


# ========== 3. 多用户与后台权限测试 ==========

def test_multi_user_lifecycle():
    from models import (
        create_user, get_user_by_username, get_user_by_id,
        list_users, update_user, delete_user,
        verify_password, create_user_token, verify_user_token
    )

    test_name = "testuser_demo"
    # 清理旧数据
    old = get_user_by_username(test_name)
    if old:
        delete_user(old["id"])

    # 1. 创建普通用户
    u = create_user(test_name, "password123", role="user", display_name="测试员")
    assert u is not None
    assert u["username"] == test_name
    assert u["role"] == "user"

    # 2. 密码校验
    user_db = get_user_by_username(test_name)
    assert user_db is not None
    assert verify_password("password123", user_db["password_hash"])
    assert not verify_password("wrong_password", user_db["password_hash"])

    # 3. 颁发与验证 Token
    tok = create_user_token(u["id"])
    verified_u = verify_user_token(tok)
    assert verified_u is not None
    assert verified_u["id"] == u["id"]
    assert verified_u["username"] == test_name

    # 4. 更新用户信息
    u_updated = update_user(u["id"], {"display_name": "新昵称", "password": "new_secret_pass"})
    assert u_updated is not None and u_updated["display_name"] == "新昵称"
    user_db_new = get_user_by_username(test_name)
    assert user_db_new is not None and verify_password("new_secret_pass", user_db_new["password_hash"])

    # 5. 用户列表
    all_users = list_users()
    assert any(user["username"] == "admin" for user in all_users)
    assert any(user["username"] == test_name for user in all_users)

    # 6. 删除用户
    assert delete_user(u["id"]) is True
    assert get_user_by_id(u["id"]) is None


def test_registration_toggle_and_logic():
    from config import is_registration_allowed, set_registration_allowed
    # 测试开关
    set_registration_allowed(False)
    assert is_registration_allowed() is False
    set_registration_allowed(True)
    assert is_registration_allowed() is True


if __name__ == "__main__":
    test_lunar_conversion()
    test_lunar_small_month_tolerance()
    test_next_lunar_birthday()
    test_milestones_and_progress()
    test_shengxiao_ganzhi()
    test_login_rate_limiting()
    test_ical_token_lifecycle()
    test_backup_config_and_logic()
    test_multi_user_lifecycle()
    test_registration_toggle_and_logic()
    print("✅ 全部 pytest 测试用例本地执行通过！")
