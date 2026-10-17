"""把已交学生的作答附件下载下来，并把每页渲染成图，供判分使用。"""
import os
import time

import pypdfium2 as pdfium

import roster


def collect(client, work_id, out_dir, scale=2.0, log=print):
    """返回 (all_rows, submitted_rows, done)。done 里带 pages / bytes。"""
    rows, submitted = roster.collect(client, work_id, log=log)
    img_dir = os.path.join(out_dir, 'img')
    os.makedirs(img_dir, exist_ok=True)

    done = []
    for r in submitted:
        pdf_path = os.path.join(out_dir, f"{r['stuNo']}_{r['name']}.pdf")
        try:
            size, _ = client.download_attachment(r['objectid'], pdf_path)
        except Exception as exc:  # 单份失败不该拖垮整批
            log(f"  跳过 {r['stuNo']} {r['name']}：{exc}")
            continue
        doc = pdfium.PdfDocument(pdf_path)
        for i in range(len(doc)):
            doc[i].render(scale=scale).to_pil().save(
                os.path.join(img_dir, f"{r['stuNo']}_p{i + 1}.png"))
        done.append({**r, 'pages': len(doc), 'bytes': size})
        log(f"  {r['stuNo']} {r['name']}  {size}B  {len(doc)}页")
        time.sleep(0.8)
    return rows, submitted, done
