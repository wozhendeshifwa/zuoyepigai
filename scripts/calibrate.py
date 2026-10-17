"""得分区间与班级均分调分——纯函数，不碰网络、不碰文件，便于测试。"""


def clamp(value, lo, hi):
    return min(hi, max(lo, value))


def to_range(raw, floor, cap):
    """把百分制原始分夹进 [floor, cap]。"""
    return clamp(float(raw), float(floor), float(cap))


def calibrate(totals, target, floor, cap, tolerance=1.0, max_rounds=200):
    """求一个全班统一平移量，使均分落到 target±tolerance。

    返回 (shift, adjusted)。均分已在区间内时 shift 为 0。
    平移后逐人夹进 [floor, cap]，因此均值可能被夹住而收敛不到目标，
    此时返回能取到的最接近结果——调用方负责把偏差报给人看。
    """
    totals = [float(t) for t in totals]
    if not totals:
        return 0.0, []
    mean = sum(totals) / len(totals)
    if abs(mean - target) <= tolerance:
        return 0.0, [clamp(t, floor, cap) for t in totals]

    shift = target - mean
    for _ in range(max_rounds):
        adjusted = [clamp(t + shift, floor, cap) for t in totals]
        err = target - sum(adjusted) / len(adjusted)
        if abs(err) < 0.01:
            break
        shift += err
    return shift, [clamp(t + shift, floor, cap) for t in totals]
