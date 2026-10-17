# 学习通接口事实（计算机网络 / 教师端）

只记那些**查文档查不到、试错又贵**的东西。代码在 `scripts/`，这里只写事实与坑。

## 取数链路

```
visit/courselistdata            → 课程卡片（courseId + enc + cpi）
coursecontroller/isNewCourse    → 跳到 mooc2-ans/mycourse/tch?courseid=…&clazzid=…&enc=…
mooc2-ans/work/list             → 作业列表（taskId 在 li id="work<taskId>"，workId 在 viewWork 的第二个参数）
mooc2-ans/work/mark             → 批阅列表页；隐藏字段里有 workid/enc/ip/上传地址
mooc2-ans/work/mark-list        → 学生名单片段
mooc2-ans/work/library/review-work → 单个学生的批阅页（题目 + 参考答案 + 作答）
```

**`enc` 一律从页面隐藏字段取**（`#enc`、`#workScoreExportEnc`），不要自己算。

## 三个会骗人的计数

| 来源 | 说的是 | 真相 |
| --- | --- | --- |
| 作业列表「N 已交」 | 10 | 只是待批数，不等于真交 |
| `mark-list` 返回行数 | 10 | 默认分页只给 10 行，必须带 `pages=1&size=200` |
| 成绩表「提交时间」 | 35 | 点了提交但没传文件的人也有时间 |

**以「学生答案里有附件」为准**：`review-work` 页里 `class="stuAnswerWords"` 到 `</dl>` 之间若有 `objectid=`，才算真交。正则不能越过这个边界，否则会抓到下面「正确答案」的附件（踩过）。

## 附件下载

`GET mooc1.chaoxing.com/ananas/status/{objectid}` → JSON 里的 `download` 字段才是真地址。直接拼 `p.ananas.chaoxing.com/star3/origin/{objectid}` 是 404。

## 写操作（三个，都有副作用）

**导入成绩** `POST {moocImportExportUrl}/import/importScore?workId=…&courseid=…&classid=…&enc=…&cpi=…&ipAddress=…`，multipart 字段名 `excelFile`。

- **按行全量写**：文件里有一行，它就当成这个人已批并写入分数。
- 只认 `.xls`；`.xlsx` 直接回「暂不支持 excel2007」。
- **只含部分学生的表会被拒**（`{"msg":"数据异常","error null"}`），所以单人改分不能用导入。
- 后果：文件里放全班模板 = 没交作业的人被写成 0 分且状态变「完成」。这件事发生过一次。

**单人改分** `POST mooc2-ans/work/markscore?markScore=<分>&markAnswerIds=<answerId>&markType=0`，表单带 `courseid/clazzid/cpi/workid/answerIds/type/score`，回 `{"status":true}`。改一个人的分只走这条。

**批量打回** `POST mooc2-ans/work/batchBack?backAnswerIdsStr=<逗号分隔>`，表单带 `reason`、`extraTime`。可撤销（页面有「撤销打回」）。

## 没有「恢复未交」

打回后状态是「待重做」，不是「未交」——学习通没有撤销评分或恢复未交的入口（批阅页、作业列表页、作业统计页的脚本都翻过）。想让没交的人不被写分，唯一可靠的做法是**别把他放进导入文件**。

## 成绩模板

`导出成绩` 得到 BIFF8 `.xls`：第 1 行是「作业名称：…」，第 2 行是表头 13 列，**分数在第 9 列（index 8）**，另有「作业批语 / 状态 / 领取时间 / 提交时间」。导入时改这一列即可。
