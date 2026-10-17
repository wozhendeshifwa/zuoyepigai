"""排查用的只读小工具，合并成一个入口。

原来这些是 20 多个一次性脚本（find / slice / peek / scan / links /
count_markers / dump_inputs / read_xls / crop / pdf_report ...），
同一个目的反复造，且每次都在命令行上跟引号搏斗。

    cx.py inspect xls   <file> [--filled] [--diff other.xls]
    cx.py inspect grep  <file> <正则>
    cx.py inspect slice <file> <标记> [--radius 800]
    cx.py inspect crop  <img> <out> --box l,t,r,b [--scale 3]
    cx.py inspect pdf   <file> [--pages 1,2,3]
"""
import argparse
import re


def _arg(ap):
    ap.add_argument('file')
    return ap


def cmd_xls(args):
    import xlrd
    sh = xlrd.open_workbook(args.file).sheet_by_index(0)
    head = [str(sh.cell_value(r, c)).strip()
            for r in range(min(6, sh.nrows)) for c in range(sh.ncols)]
    if args.diff:
        other = xlrd.open_workbook(args.diff).sheet_by_index(0)
        diff = [(i, j) for i in range(min(sh.nrows, other.nrows))
                for j in range(min(sh.ncols, other.ncols))
                if str(sh.cell_value(i, j)) != str(other.cell_value(i, j))]
        print(f'行数 {sh.nrows} vs {other.nrows}，列数 {sh.ncols} vs {other.ncols}')
        print(f'差异 {len(diff)} 处，所在列 {sorted({j for _, j in diff})}')
        return 0
    score_col = next((i for i, c_i in enumerate(range(sh.ncols))
                      if str(sh.cell_value(1, c_i)).strip() == '分数'), None)
    if args.filled and score_col is not None:
        n = 0
        for r in range(2, sh.nrows):
            v = sh.cell_value(r, score_col)
            if isinstance(v, (int, float)) and v > 0:
                n += 1
                print(f'  {sh.cell_value(r, 0)} | {sh.cell_value(r, 1)} | 分数={v}')
        print(f'  非零 {n} 行 / 共 {sh.nrows - 2} 行')
        return 0
    print(f'sheet={sh.name!r} rows={sh.nrows} cols={sh.ncols}')
    for r in range(min(6, sh.nrows)):
        cells = []
        for c in range(sh.ncols):
            v = sh.cell_value(r, c)
            cells.append(str(int(v) if isinstance(v, float) and v == int(v) else v)[:24])
        print(f'  r{r}: ' + ' | '.join(cells))
    return 0


def cmd_grep(args):
    text = open(args.file, encoding='utf-8', errors='ignore').read()
    hits = sorted(set(re.findall(args.pattern, text)))
    for h in hits[:args.limit]:
        print(str(h)[:200])
    print(f'-- unique={len(hits)}')
    return 0


def cmd_slice(args):
    text = open(args.file, encoding='utf-8', errors='ignore').read()
    idx = text.find(args.marker)
    if idx < 0:
        print(f'找不到标记 {args.marker!r}')
        return 1
    lo = max(0, idx - args.radius)
    print(text[lo:idx + args.radius])
    return 0


def cmd_crop(args):
    from PIL import Image
    l, t, r, b = (int(x) for x in args.box.split(','))
    im = Image.open(args.file).crop((l, t, r, b))
    im = im.resize((int(im.width * args.scale), int(im.height * args.scale)),
                   Image.LANCZOS)
    im.save(args.out)
    print(f'{args.out}  {im.size}')
    return 0


def cmd_pdf(args):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(args.file)
    pages = [int(x) for x in args.pages.split(',')] if args.pages else \
        list(range(1, min(4, len(doc)) + 1))
    print(f'{args.file}  共 {len(doc)} 页')
    for p in pages:
        if not (1 <= p <= len(doc)):
            continue
        page = doc[p - 1]
        text = page.get_textpage().get_text_bounded().strip()
        print(f'  p{p}: 文字层 {len(text)} 字  {text[:60]!r}')
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog='cx.py inspect')
    sub = ap.add_subparsers(dest='what', required=True)

    p = sub.add_parser('xls')
    _arg(p)
    p.add_argument('--filled', action='store_true')
    p.add_argument('--diff')
    p.set_defaults(fn=cmd_xls)

    p = sub.add_parser('grep')
    _arg(p)
    p.add_argument('pattern')
    p.add_argument('--limit', type=int, default=40)
    p.set_defaults(fn=cmd_grep)

    p = sub.add_parser('slice')
    _arg(p)
    p.add_argument('marker')
    p.add_argument('--radius', type=int, default=800)
    p.set_defaults(fn=cmd_slice)

    p = sub.add_parser('crop')
    _arg(p)
    p.add_argument('out')
    p.add_argument('--box', required=True)
    p.add_argument('--scale', type=float, default=3.0)
    p.set_defaults(fn=cmd_crop)

    p = sub.add_parser('pdf')
    _arg(p)
    p.add_argument('--pages')
    p.set_defaults(fn=cmd_pdf)

    args = ap.parse_args(argv)
    return args.fn(args)
