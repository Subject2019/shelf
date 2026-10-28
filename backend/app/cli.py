"""EchoShelf 运维 CLI（管理员只能通过带外方式创建）。

容器内：

    docker exec -it echoshelf python -m app.cli admin create
    docker exec -it echoshelf python -m app.cli admin reset-password
    docker exec -it echoshelf python -m app.cli admin list

裸机：

    /opt/echoshelf/bin/echoshelf admin create
    /opt/echoshelf/bin/echoshelf admin reset-password

设计约束（见 docs/API.md §8）：
- 只能有一个管理员：`create` 在已有管理员时直接拒绝
- 网页端不再提供初始化接口，也不允许把别人提升为管理员
- 忘记密码用 `reset-password`，不依赖登录态
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import RefreshToken, User

MIN_PASSWORD = 8


def _session():
    settings = get_settings()
    settings.ensure_dirs()
    return get_session_factory()()


def _fail(message: str) -> None:
    print(f"错误：{message}", file=sys.stderr)
    raise SystemExit(2)


def _read_password(password: str | None) -> str:
    if password is not None:
        if len(password) < MIN_PASSWORD:
            _fail(f"密码至少 {MIN_PASSWORD} 位")
        return password
    first = getpass.getpass(f"新密码（至少 {MIN_PASSWORD} 位）：")
    if len(first) < MIN_PASSWORD:
        _fail(f"密码至少 {MIN_PASSWORD} 位")
    second = getpass.getpass("再输入一次：")
    if first != second:
        _fail("两次输入的密码不一致")
    return first


def _admin_count(session, exclude_id: int | None = None) -> int:
    query = select(func.count()).select_from(User).where(User.role == "admin")
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    return session.scalar(query) or 0


def _revoke_tokens(session, user_id: int) -> None:
    now = now_ts()
    for token in session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ):
        token.revoked_at = now


def cmd_list(_: argparse.Namespace) -> int:
    with _session() as session:
        rows = session.scalars(select(User).order_by(User.id)).all()
        if not rows:
            print("数据库里还没有用户：请先执行 `admin create`")
            return 0
        print(f"{'ID':<4} {'用户名':<20} {'角色':<10} {'状态':<6} 最近登录")
        for user in rows:
            state = "启用" if user.is_active else "停用"
            last = user.last_login_at or "-"
            print(f"{user.id:<4} {user.username:<20} {user.role:<10} {state:<6} {last}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    if len(username) < 2:
        _fail("用户名至少 2 个字符")

    with _session() as session:
        if _admin_count(session):
            existing = session.scalar(select(User.username).where(User.role == "admin"))
            _fail(
                f"已存在管理员（{existing}）。系统只允许一个管理员；如需替换请先执行 `admin demote-others`"
            )
        if session.scalar(select(User.id).where(User.username == username)):
            _fail(f"用户名已存在：{username}")

        password = _read_password(args.password)
        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=args.display_name or "管理员",
            role="admin",
            is_active=True,
            created_at=now_ts(),
        )
        session.add(user)
        session.commit()
        print(
            f"已创建管理员：{username}（请妥善保存密码，忘记可用 `admin reset-password`）"
        )
    return 0


def cmd_reset_password(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    with _session() as session:
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            _fail(f"用户不存在：{username}")
        if user.role != "admin":
            _fail(f"{username} 不是管理员，拒绝重置管理员密码")

        password = _read_password(args.password)
        user.password_hash = hash_password(password)
        _revoke_tokens(session, user.id)
        session.commit()
        print(f"已重置 {username} 的密码，旧会话全部失效")
    return 0


def cmd_demote_others(args: argparse.Namespace) -> int:
    keep = args.keep.strip().lower()
    with _session() as session:
        keeper = session.scalar(select(User).where(User.username == keep))
        if keeper is None or keeper.role != "admin":
            _fail(f"保留的管理员不存在或不是 admin：{keep}")
        others = session.scalars(
            select(User).where(User.role == "admin", User.id != keeper.id)
        ).all()
        for user in others:
            user.role = "editor"
            print(f"降级为 editor：{user.username}")
        session.commit()
        if not others:
            print(f"只有 {keep} 一个管理员，无需处理")
        else:
            print(f"完成，当前管理员：{keep}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="echoshelf", description="EchoShelf 运维命令")
    sub = parser.add_subparsers(dest="group", required=True)

    admin = sub.add_parser("admin", help="管理员账号维护（仅带外使用）")
    admin_sub = admin.add_subparsers(dest="action", required=True)

    p_list = admin_sub.add_parser("list", help="列出所有用户")
    p_list.set_defaults(func=cmd_list)

    p_create = admin_sub.add_parser("create", help="创建唯一管理员（无管理员时可用）")
    p_create.add_argument("--username", default="admin")
    p_create.add_argument("--display-name", default=None)
    p_create.add_argument("--password", default=None, help="非交互用；默认交互输入")
    p_create.set_defaults(func=cmd_create)

    p_reset = admin_sub.add_parser("reset-password", help="重置管理员密码并吊销旧会话")
    p_reset.add_argument("--username", default="admin")
    p_reset.add_argument("--password", default=None, help="非交互用；默认交互输入")
    p_reset.set_defaults(func=cmd_reset_password)

    p_demote = admin_sub.add_parser("demote-others", help="把其他管理员降为 editor")
    p_demote.add_argument("--keep", default="admin")
    p_demote.set_defaults(func=cmd_demote_others)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
