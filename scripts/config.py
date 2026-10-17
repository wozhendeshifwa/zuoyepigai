"""项目常量与配置读取。

改作业/换课程时只动这里，不要让常量散落到各个脚本里。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = os.path.join(ROOT, 'research_src')
FETCH = os.path.join(RESEARCH, 'fetch')
SUB = os.path.join(RESEARCH, 'sub')
GRADE = os.path.join(RESEARCH, 'grade')
KEY = os.path.join(RESEARCH, 'key')
OUT = os.path.join(ROOT, 'out')

# 计算机网络 / 计科2024级5-6班
COURSE_ID = '265589210'
CLAZZ_ID = '152831310'
CPI = '488846510'

# 教务惯例：得分固定在 75-98，不出现 100；班级均分目标 92±1
SCORE_FLOOR = 75.0
SCORE_CAP = 98.0
TARGET_MEAN = 92.0

# 本次作业：第3章第1次作业（taskId 用于页面，workId 用于接口）
DEFAULT_TASK_ID = '133161756'
DEFAULT_WORK_ID = '56915590'

# 每题分值：选择 5×3 + 简答 10×7 + 计算 15 = 100
QUESTIONS = [
    ('2', '选择', 5), ('16', '选择', 5), ('23', '选择', 5),
    ('4', '简答', 10), ('6', '简答', 10), ('8', '简答', 10), ('18', '简答', 10),
    ('19', '简答', 10), ('21', '简答', 10), ('24', '简答', 10),
    ('26', '计算', 15),
]
FULL = {no: full for no, _, full in QUESTIONS}


def _read_kv(path):
    cfg = {}
    if not os.path.exists(path):
        return cfg
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    return cfg


def load_cookie():
    """学习通 Cookie，从 research_src/cookie.txt 读（该目录已在 .gitignore 内）。"""
    path = os.path.join(RESEARCH, 'cookie.txt')
    if not os.path.exists(path):
        raise SystemExit(f'缺少 {path}：请把浏览器里的 Cookie 请求头整行贴进去')
    return open(path, encoding='utf-8').read().strip()


def load_vision():
    """视觉模型配置。缺 key 时给出可执行的提示，而不是等到判分中途才炸。"""
    cfg = _read_kv(os.path.join(RESEARCH, 'vision_key.txt'))
    missing = [k for k in ('base_url', 'model', 'api_key') if not cfg.get(k)]
    if missing:
        raise SystemExit(
            '缺少视觉模型配置 ' + ', '.join(missing) +
            '（写在 research_src/vision_key.txt）')
    return cfg
