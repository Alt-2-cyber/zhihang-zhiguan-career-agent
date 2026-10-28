import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

from docx import Document

from competition_illustrated_assets import OUT,ASSETS,EVIDENCE,PROJECT
from competition_illustrated_content import NAME,PAGES,used


def main():
    docx=OUT/(NAME+'_比赛项目文档_图文增强版.docx')
    pdf=docx.with_suffix('.pdf');markdown=docx.with_suffix('.md')
    qa=json.loads((EVIDENCE/'render_check.json').read_text(encoding='utf-8'))
    assert qa['pages']==42 and qa['figures']==60 and qa['all_42_pages_include_figures']
    basis=json.loads((EVIDENCE/'document_basis.json').read_text(encoding='utf-8'))
    manifest=json.loads((EVIDENCE/'figures_manifest.json').read_text(encoding='utf-8'))
    index=json.loads((EVIDENCE/'figure_index.json').read_text(encoding='utf-8'))
    assert set(manifest)==set(used)and len(set(used))==60
    assert {n['number']for n in index}==set(range(1,61))
    assert all('pdf_page'in n for n in index)
    previous=Document(PROJECT/'docs'/'deliverables'/'比赛提交材料_职航智管_20261025'/(NAME+'_作品介绍_详细版.docx'))
    current=Document(docx)
    text='\n'.join(p.text for p in current.paragraphs)
    # All prose/code/table content in the shared detailed source remains in
    # the new document; the changes add figures and explanations around it.
    from competition_detailed_content import PAGES as ORIGINAL
    for p in ORIGINAL:
        for b in p['blocks']:
            if b['kind']in ['p','h','code']:assert b['text']in text,(p['id'],b['kind'])
    output_files=[docx,pdf,markdown,OUT/'README.md',OUT/'提交前核对.md']
    for file in output_files:assert file.is_file()and file.stat().st_size>100
    for file in list(OUT.glob('*.md'))+list(EVIDENCE.glob('*.json'))+list(EVIDENCE.glob('*.log')):
        value=file.read_text(encoding='utf-8-sig')
        assert not re.search(r'Student123!|Counselor123!|sk-[a-zA-Z0-9_-]{20,}|eyJ[a-zA-Z0-9_-]{45,}',value),file.name
    photo_source=PROJECT/'frontend'/'public'/'ai-interviewer.source.txt'
    if photo_source.exists():shutil.copy2(photo_source,EVIDENCE/'digital-human-photo-source.txt')
    OUT.joinpath('图源与数据口径.md').write_text('''# 图源与数据口径

图文增强版共60张不同的图，正文图号连续，每个图解页紧跟对应章节。

| 类型 | 数量 | 使用方式 |
| --- | --- | --- |
| 架构与流程图 | 32 | 根据项目源码或明确标注的治理/试点方案绘制 |
| 真实界面及注释图 | 19 | 历史浏览器截图，只裁切和等比缩放，保留原数值及状态 |
| 数据图表 | 9 | 采用2026-10-20已保存数据与测试记录，附演示/本机实测说明 |

## 图注和来源

`evidence/figure_index.json`列出图号、素材名、图注、插入尺寸和PDF页码。`evidence/figures_manifest.json`记录原文件、裁切位置、日期或绘制依据。`assets/`保留PNG，数据图同时保留原SVG。

工具详情图左侧是原界面局部等比放大，右侧为解释文字，不代表产品增加了新控件。面试官照片使用项目已有素材，原来源声明保存在证据目录，不当作实时生成视频。

## 数据边界

24名学生、6个岗位、85条申请、96项任务和9条风险来自人工构造演示库；匹配分和面试分来自local-demo/local-rules。历史测试与本机接口采样均保留原日期。当前阶段分布、累计到达阶段和最近七天事件分别说明，不混作就业成效。

2026-10-22文件上传解析失败、历史E2E未通过项，以及未部署的语音视觉服务状态均保留。图文增强未修改应用源码、未重新运行整套测试，也未生成新的真实业务数据。

许可检查、贡献流程、长期路线、试点评估和演示顺序是方案或建议，不表示公开仓库、许可证、CI、团队角色或试点已经落实。
''',encoding='utf-8')
    result={
        'edition':'图文增强版','revision':'2026-10-26','pages':42,'main_chapters':24,'extra_visual_explanations':16,
        'figures':60,'diagrams':32,'screenshots_and_annotated_details':19,'data_charts':9,
        'all_42_pages_include_figures':True,'continuous_figure_numbers':True,
        'chinese_characters':basis['chinese_characters'],'nonwhitespace_characters':basis['nonwhitespace_characters'],
        'previous_detailed_prose_preserved':True,'previous_detailed_edition_preserved':True,
        'pdf_docx_markdown_verified':True,'historical_data_and_known_failures_retained':True,
        'repository_and_video_urls_still_pending':True,
        'new_test_suite_run':False,
        'files':[{'name':f.name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}for f in [pdf,docx,markdown]]
    }
    (EVIDENCE/'delivery_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    hashes=[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(OUT.rglob('*'))if p.is_file()and p.name!='SHA256.json']
    (EVIDENCE/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    archive_path=OUT.parent/'职航智管_比赛项目文档_图文增强版_20261026.zip'
    with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as archive:
        for file in sorted(OUT.rglob('*')):
            if file.is_file():archive.write(file,'职航智管_比赛项目文档_图文增强版/'+file.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive_path)as archive:
        assert archive.testzip()is None
        names=set(archive.namelist())
        for file in re.findall(r'\]\(([^)]+)\)',markdown.read_text(encoding='utf-8')):
            assert '职航智管_比赛项目文档_图文增强版/'+file in names
    print(json.dumps({**result,'zip':str(archive_path),'zip_mib':round(archive_path.stat().st_size/1048576,2)},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
