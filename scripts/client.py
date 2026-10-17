"""学习通的 HTTP 客户端：一处管 Cookie、UA、Referer 与表单/文件上传。

不在各脚本里散落 urllib 调用——那是 38 个临时脚本互相抄的来源。
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

import config

MOOC2 = 'https://mooc2-ans.chaoxing.com'
MOOC1 = 'https://mooc1.chaoxing.com'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def mark_url(task_id):
    return (f'{MOOC2}/mooc2-ans/work/mark?courseid={config.COURSE_ID}&clazzid=0'
            f'&id={task_id}&cpi={config.CPI}&evaluation=0&from=&v=2'
            f'&prePageNum=1&prePageSize=12&topicid=0&perspectiveType=0')


def mark_list_url(work_id, size=200):
    return (f'{MOOC2}/mooc2-ans/work/mark-list?courseid={config.COURSE_ID}'
            f'&clazzid={config.CLAZZ_ID}&workid={work_id}&submit=true&status=0'
            f'&cpi={config.CPI}&evaluation=0&groupId=0&sort=0&from=&topicid=0'
            f'&order=0&pages=1&size={size}')


def review_url(work_id, answer_id):
    return (f'{MOOC2}/mooc2-ans/work/library/review-work?courseid={config.COURSE_ID}'
            f'&clazzid={config.CLAZZ_ID}&workId={work_id}&workAnswerId={answer_id}'
            f'&groupId=0&from=&sort=0&order=0&status=0&pages=1&size=20&topicid=0')


class Client:
    def __init__(self, cookie=None):
        self.cookie = cookie or config.load_cookie()

    def _open(self, url, data=None, referer=None, headers=None, timeout=120):
        h = {
            'Cookie': self.cookie,
            'User-Agent': UA,
            'Accept': '*/*',
            'Referer': referer or MOOC2 + '/',
        }
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h,
                                     method='POST' if data is not None else 'GET')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def get(self, url, **kw):
        return self._open(url, **kw)

    def get_text(self, url, **kw):
        return self._open(url, **kw)[1].decode('utf-8', 'ignore')

    def post_form(self, url, fields, referer=None):
        body = urllib.parse.urlencode(fields).encode('utf-8')
        return self._open(url, data=body, referer=referer, headers={
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        })

    def post_file(self, url, field, path, referer=None):
        boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
        fname = os.path.basename(path).encode('utf-8')
        body = (f'--{boundary}\r\n'.encode() +
                b'Content-Disposition: form-data; name="' + field.encode() +
                b'"; filename="' + fname + b'"\r\n' +
                b'Content-Type: application/vnd.ms-excel\r\n\r\n' +
                open(path, 'rb').read() +
                f'\r\n--{boundary}--\r\n'.encode())
        return self._open(url, data=body, referer=referer, headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        }, timeout=180)

    @staticmethod
    def hidden(html, elem_id):
        m = re.search(r'id="%s"[^>]*value="([^"]*)"' % re.escape(elem_id), html)
        if not m:
            m = re.search(r'value="([^"]*)"[^>]*id="%s"' % re.escape(elem_id), html)
        return m.group(1) if m else ''

    def mark_params(self, task_id):
        """批阅页里的隐藏参数：workid / enc / 上传地址 / ip。"""
        text = self.get_text(mark_url(task_id))
        keys = ('workid', 'clazzid', 'courseid', 'cpi', 'mooc', 'enc', 'ip',
                'workScoreExportEnc', 'moocImportExportUrl')
        return {k: self.hidden(text, k) for k in keys}

    def download_grade_template(self, task_id, out_path):
        """导出当前成绩表（学习通认的导入模板），返回落盘路径。"""
        p = self.mark_params(task_id)
        base = p['moocImportExportUrl'] or 'https://mooc1.chaoxing.com/import-export-ans'
        url = (f'{base}/export-workscore?courseId={p["courseid"]}'
               f'&classId={p["clazzid"]}&workId={p["workid"]}&mooc={p["mooc"]}'
               f'&isTemplate=true&cpi={p["cpi"]}&enc={p["workScoreExportEnc"]}'
               f'&addLog=true')
        status, raw, _ = self.get(url)
        if status != 200 or not raw.startswith(b'\xd0\xcf\x11\xe0'):
            raise SystemExit(f'导出成绩表失败：HTTP {status}，前 8 字节 {raw[:8].hex()}')
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, 'wb').write(raw)
        return out_path

    def download_attachment(self, objectid, out_path):
        status, raw, _ = self.get(f'{MOOC1}/ananas/status/{objectid}')
        if status != 200:
            raise RuntimeError(f'附件状态接口 HTTP {status}')
        meta = json.loads(raw.decode('utf-8', 'ignore'))
        url = meta.get('download') or ''
        if not url:
            raise RuntimeError('附件没有 download 地址')
        status, raw, _ = self.get(url)
        if status != 200 or not raw.startswith(b'%PDF'):
            raise RuntimeError(f'附件下载失败 HTTP {status}')
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, 'wb').write(raw)
        return len(raw), meta.get('filename', '')
