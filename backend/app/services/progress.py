"""收听进度合并（ADR-0002）。

规则：客户端权威 + 最后写入胜 + 单调不回退 + 显式跳转豁免。
纯函数实现，便于单测覆盖全部边界。

`position_sec` 是全书绝对秒，因此「不回退」按绝对位置判断，跨轨同样成立：
从第 3 轨回到第 1 轨、又没有标 `explicit_seek` 的上报一律视为旧设备补传而拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import Track

MAX_CLOCK_SKEW_SEC = 300
SEEK_TOLERANCE_SEC = 30.0


@dataclass(frozen=True, slots=True)
class ProgressState:
    position_sec: float
    track_id: int | None
    client_updated_at: int


@dataclass(frozen=True, slots=True)
class MergeDecision:
    accepted: bool
    position_sec: float
    track_id: int | None
    client_updated_at: int


def sane_timestamp(client_updated_at: int, server_now: int) -> int:
    """设备时钟偏差超过 5 分钟时改用服务器时间，防止单设备永久压制其它设备。"""
    if abs(client_updated_at - server_now) > MAX_CLOCK_SKEW_SEC:
        return server_now
    return client_updated_at


def merge_progress(
    old: ProgressState | None,
    new: ProgressState,
    *,
    server_now: int,
    explicit_seek: bool,
) -> MergeDecision:
    new_ts = sane_timestamp(new.client_updated_at, server_now)

    # 1. 同一个或更早的时间戳：重复/迟到上报，直接拒绝（天然幂等）
    if old is not None and new_ts <= old.client_updated_at:
        return _keep(old)

    # 2. 用户显式跳转无条件采纳
    if explicit_seek:
        return MergeDecision(True, new.position_sec, new.track_id, new_ts)

    # 3. 绝对位置回退超过容差：视为旧设备补传/误报，保留较后位置。
    #    position_sec 是全书绝对秒，正常换轨只会前进，所以跨轨回退也要拦住；
    #    用户真的往回拖时前端会带 explicit_seek，走第 2 条。
    if old is not None and new.position_sec < old.position_sec - SEEK_TOLERANCE_SEC:
        return _keep(old)

    # 4. 前进 / 跨轨 / 首次
    return MergeDecision(True, new.position_sec, new.track_id, new_ts)


def _keep(old: ProgressState) -> MergeDecision:
    return MergeDecision(False, old.position_sec, old.track_id, old.client_updated_at)


def track_start_offsets(tracks: list[Track]) -> dict[int, float]:
    """全书绝对起点：按轨顺序累加时长（CUE 分轨的 duration 已是差值）。"""
    offsets: dict[int, float] = {}
    cursor = 0.0
    for track in tracks:
        offsets[track.id] = cursor
        cursor += track.duration_sec
    return offsets


def locate_track(
    offsets: dict[int, float], tracks: list[Track], position_sec: float
) -> int | None:
    if not tracks:
        return None
    for track in tracks:
        if position_sec < offsets[track.id] + track.duration_sec:
            return track.id
    return tracks[-1].id


def track_position(position_sec: float, track_start: float) -> float:
    return max(0.0, position_sec - track_start)
