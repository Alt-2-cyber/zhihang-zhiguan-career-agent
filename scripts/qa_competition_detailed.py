import json
import re
import sys
from pathlib import Path

import fitz

from competition_detailed_content import NAME, PAGES

ROOT=Path(r'D:\table\ai_jiuye')
OUTPUT=ROOT/'docs'/'deliverables'/'比赛提交材料_职航智管_20261025'
TMP=ROOT/'output'/'competition-detailed-20261025'
TMP.mkdir(exist_ok=True)

pdf=fitz.open(OUTPUT/(NAME+'_作品介绍_详细版.pdf'))
assert len(pdf)==len(PAGES)+1==25
records=[]
for i,page in enumerate(pdf):
    text=page.get_text()
    assert '\ufffd'not in text
    if i:
        assert re.sub(r'\s','',PAGES[i-1]['title'])in re.sub(r'\s','',text),(i+1,PAGES[i-1]['title'])
    assert len(text)>220
    issues=[]
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            x0,y0,x1,y1=line['bbox']
            if y0>48 and y1<800 and (x0<38 or x1>page.rect.width-38):issues.append({'text':''.join(s['text']for s in line['spans']),'bbox':line['bbox']})
    assert not issues,(i+1,issues)
    page.get_pixmap(matrix=fitz.Matrix(1.65,1.65),alpha=False).save(TMP/f'page-{i+1:02}.png')
    records.append({'page':i+1,'heading':'cover'if i==0 else PAGES[i-1]['title'],'extracted_characters':len(text),'horizontal_text_bounds_pass':True})
report={'pages':len(pdf),'chapters':len(PAGES),'all_headings_on_expected_pages':True,'replacement_characters':0,'no_blank_pages':True,'records':records}
(OUTPUT/'evidence_detailed'/'pdf_render_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PDF QA: 25 pages, 24 chapter headings on expected pages, no blank pages or text outside horizontal margins.')
