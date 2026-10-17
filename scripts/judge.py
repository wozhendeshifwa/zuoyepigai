"""判分：把学生页图 + 题目/参考答案/分值送进视觉模型，拿回逐题 JSON。

提示词与判据集中在这里。改判分口径就改这份，别在调用点另写一套。
"""
import base64
import json
import re
import urllib.error
import urllib.request

import config


def build_prompt(key_by_no, n_images, questions=None):
    questions = questions or config.QUESTIONS
    out = [
        '你是计算机网络课程的助教，正在批改一份手写作业。',
        f'学生把答案写在打印的题目纸上、拍照后合成 PDF，下面按页序给出 {n_images} 张页图。',
        '',
        '判分规则：',
        '- 选择题：只有两档，答对 = 满分，答错或没答 = 0。',
        '- 简答/计算：三档，0 / 满分的一半 / 满分。要点覆盖大半即可给满分；只沾一点边给一半。',
        '- 只要学生写出了与参考答案实质等价的表述就算对，不要求字面一致；错别字、简写不扣分。',
        '- 学生没作答的题给 0，transcript 写「未作答」。',
        '',
        '## 本次作业的题目、参考答案与满分',
    ]
    for no, qtype, full in questions:
        out.append(f'- 第 {no} 题（{qtype}，满分 {full}）：'
                   f'参考答案：{key_by_no.get(no, "（未提取到参考答案）")}')
    out += [
        '',
        '## 输出要求',
        f'只输出一个 JSON 数组，不要解释、不要 markdown 代码围栏，包含全部 {len(questions)} 道题：',
        '[{"no":"2","score":5,"transcript":"学生这道题写了什么，≤40字","conf":"高|中|低"}]',
        'score 必须是 0、满分的一半、或满分这三个值之一（选择题只有 0 或满分）。',
        'conf 是你对这道题判分的把握：手写看不清或答案含糊就写「低」。',
    ]
    return '\n'.join(out)


def load_key(path):
    """把答案课件抽出的 JSON 变成 {题号: 参考答案}。同一题多页时用 / 连接。"""
    data = json.load(open(path, encoding='utf-8'))
    merged = {}
    for it in data:
        m = re.match(r'^\d+-(\d+)$', str(it.get('no') or ''))
        if not m or not it.get('answer'):
            continue
        merged.setdefault(m.group(1), [])
        if it['answer'] not in merged[m.group(1)]:
            merged[m.group(1)].append(it['answer'])
    return {k: ' / '.join(v) for k, v in merged.items()}


def _post(cfg, payload):
    req = urllib.request.Request(
        cfg['base_url'].rstrip('/') + '/chat/completions',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + cfg['api_key'],
                 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode('utf-8', 'ignore'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'模型接口 HTTP {e.code}: '
                           f'{e.read().decode("utf-8", "ignore")[:300]}')


def grade_images(cfg, image_paths, key_by_no, model=None):
    """判一份作业。返回 (items, usage)。temperature=0 保证可复现。"""
    content = []
    for i, p in enumerate(image_paths, 1):
        b64 = base64.b64encode(open(p, 'rb').read()).decode('ascii')
        content.append({'type': 'text', 'text': f'第 {i} 页：'})
        content.append({'type': 'image_url',
                        'image_url': {'url': f'data:image/png;base64,{b64}'}})
    content.append({'type': 'text',
                    'text': build_prompt(key_by_no, len(image_paths))})
    data = _post(cfg, {'model': model or cfg['model'],
                       'messages': [{'role': 'user', 'content': content}],
                       'max_tokens': 3000, 'temperature': 0})
    text = (data['choices'][0]['message'].get('content') or '').strip()
    text = re.sub(r'^```(?:json)?|```$', '', text, flags=re.M).strip()
    try:
        items = json.loads(text)
    except Exception:
        m = re.search(r'\[.*\]', text, re.S)
        if not m:
            raise RuntimeError('模型没有返回可解析的 JSON：' + text[:300])
        items = json.loads(m.group(0))
    return items, data.get('usage', {})


def total_of(items):
    return sum(float(i.get('score') or 0) for i in items)


def merge_votes(runs, questions=None):
    """多跑几次同一份作业，逐题取多数档位。

    起因：同一张图、同样 temperature=0，两次判分在第 18 题上给出了 5 和 10。
    温度 0 并不等于可复现，所以「有争议的题」必须靠重复采样识别出来，
    再交给人工复核，而不是让它随机落进成绩。
    """
    from collections import Counter

    questions = questions or config.QUESTIONS
    indexed = [{str(i.get('no')): i for i in run} for run in runs]
    merged = []
    for no, _qtype, _full in questions:
        votes = [t[no]['score'] for t in indexed if no in t]
        if not votes:
            continue
        counts = Counter(votes)
        score, _ = counts.most_common(1)[0]
        item = dict(indexed[0].get(no) or {})
        item['score'] = score
        item['votes'] = votes
        if len(counts) > 1:
            item['conf'] = '低'
            item['note'] = f'多次判分不一致：{votes}，取多数 {score:g}'
        merged.append(item)
    return merged
