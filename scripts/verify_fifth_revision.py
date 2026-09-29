#!/usr/bin/env python3
"""Verify the current paper, presentation data, historical integrity, and PDF review."""
from datetime import datetime,timezone
import hashlib,itertools,json,re,tarfile
from pathlib import Path
from pypdf import PdfReader
from verify_fourth_revision import active_sources,sections,table

ROOT=Path(__file__).resolve().parents[1];REPORT=ROOT/'docs/fifth-audit-20260928'
TITLE='Trace Sampling at the Collector Boundary: Costs and Diagnostic Evidence'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(name):return json.loads((ROOT/name).read_text())
def close(a,b):assert abs(a-b)<1e-10,(a,b)

def main():
    sources=active_sources();source='\n'.join(sources.values());pdf=ROOT/'output/pdf/trace-sampling-collector-boundary.pdf'
    reader=PdfReader(pdf);pdf_text='\n'.join(p.extract_text() for p in reader.pages)
    aux=(ROOT/'paper/main.aux').read_text();log=(ROOT/'paper/main.log').read_text();biblog=(ROOT/'paper/main.blg').read_text()
    cites={k for g in re.findall(r'\\citation\{([^}]+)\}',aux) for k in g.split(',')}
    bibliography=set(re.findall(r'\\bibcite\{([^}]+)\}',aux));bibkeys=set(re.findall(r'(?m)^@\w+\{([^,]+),',(ROOT/'paper/references.bib').read_text()))
    labels=re.findall(r'\\newlabel\{([^}]+)\}',aux);references=set(re.findall(r'\\(?:ref|eqref)\{([^}]+)\}',source))
    assert cites==bibliography==bibkeys and references<=set(labels) and len(labels)==len(set(labels))
    assert not re.search(r'Overfull|Underfull|LaTeX Warning|Package .* Warning|undefined|Missing character',log)
    assert 'Warning--' not in biblog and 'error message' not in biblog
    assert not re.search('\u2014|---|textemdash',source) and '\u2014' not in pdf_text
    assert not re.search(r'\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b',source)
    assert reader.metadata.title==TITLE and reader.metadata.author=='Victor Bona'
    assert pdf.read_bytes()==(ROOT/'paper/main.pdf').read_bytes()
    assert 'AI-assisted research workflow' in sources['methods.tex']
    assert 'delivery-results.tex' in sources and 'delivery-appendix.tex' not in sources
    assert not re.search(r'Clopper.Pearson|largest qualifying|qualifying.discard|union bound',pdf_text,re.I)
    assert sum(k.startswith('fig:') for k in labels)==3
    assert sum(k.startswith('tab:') for k in labels)==6
    with tarfile.open(REPORT/'prerevision-source-and-paper.tar.gz') as archive:
        previous={Path(m.name).name:archive.extractfile(m).read().decode() for m in archive.getmembers() if m.isfile() and m.name.startswith('paper/') and m.name.endswith('.tex')}
        manifest=archive.extractfile('SHA256SUMS').read().decode()
    assert sections(sources)==sections(previous)
    def preamble(s):return re.sub(r'(?m)^\\input\{[^}]+\}\n','',s.split('\\begin{document}')[0])
    assert preamble(sources['main.tex'])==preamble(previous['main.tex'])
    for name in ['measurements.tex','revision-measurements.tex','cost-measurements.tex','second-audit-measurements.tex','third-audit-measurements.tex']:
        assert sources[name]==previous[name],name
    raw=0
    for line in manifest.splitlines():
        digest,name=line.split('  ',1)
        if name.startswith('data/raw/'):
            assert sha(ROOT/name)==digest,name;raw+=1
    assert raw==7328
    freeze_counts=[]
    for name,key in [('docs/revision-20260924/confirmatory-freeze.json','sha256'),('docs/final-pass-20260925/execution-freeze.json','sha256'),('docs/second-audit-20260925/execution-freeze.json','files'),('docs/third-audit-20260925/execution-freeze.json','files'),('docs/fifth-audit-20260928/execution-freeze.json','files'),('docs/fifth-audit-20260928/batching-execution-freeze-v2.json','files')]:
        f=read(name)[key]
        for p,digest in f.items():assert sha(ROOT/p)==digest,p
        freeze_counts.append(len(f))
    placement=read('data/derived/fifth-audit-20260928/placement-summary.json');high=read('data/derived/fifth-audit-20260928/batching-summary.json')
    assert (placement['cells'],high['cells'])==(40,20) and placement['rate_traces_s']==8000
    assert high['rate_traces_s']==read('docs/fifth-audit-20260928/batching-execution-freeze-v2.json')['selected_rates_traces_s']['batching']
    macros=dict(re.findall(r'\\newcommand\{\\([^}]+)\}\{([^}]+)\}',sources['fifth-measurements.tex']))
    for export,prefix in [('file','File'),('dual','Dual')]:
        for policy,short in [('gate10','Gate'),('collector10','Uniform'),('tail10','Tail')]:
            c=placement['contrasts'][f'{export}:{policy}-minus-full']['collector_cpu_saving_percent']
            assert macros[f'Placement{prefix}{short}Saving']==f"{c['mean']:.1f}"
    assert macros['PlacementFileUniformIncrease']==f"{-placement['contrasts']['file:collector10-minus-full']['collector_cpu_saving_percent']['mean']:.1f}"
    assert all(x>0 for x in placement['contrasts']['file:collector10-minus-full']['collector_cpu_s']['values'])
    assert all(x<0 for x in placement['contrasts']['dual:collector10-minus-full']['collector_cpu_s']['values'])
    assert macros['HighBatchRate']==f"{high['rate_traces_s']*5:,}"
    for timeout,name,batches in [(100,'Short',1200),(1000,'Long',1154)]:
        c=high['contrasts'][f'{timeout}:tail100-minus-full']['collector_cpu_s']
        assert all(x>0 for x in c['values'])
        assert macros[f'HighBatch{name}Difference']==f"{c['mean']:+.2f}"
        assert macros[f'HighBatch{name}Interval']==f"[{c['lower']:+.2f}, {c['upper']:+.2f}]"
        full=high['groups'][f'dual-{timeout}-full'];tail=high['groups'][f'dual-{timeout}-tail100']
        assert full['batch_count']['values']==full['batch_size_triggers']['values']==[1000]*5
        assert full['batch_timeout_triggers']['values']==[0]*5
        assert tail['batch_count']['values']==[batches]*5
    expected=[]
    for export in ['file','dual']:
        full=placement['groups'][f'{export}-1000-full']
        for policy,name in [('full','Full'),('gate10',r'Pre-ingress 10\%'),('collector10',r'Collector 10\%'),('tail10',r'Tail 10\%')]:
            g=placement['groups'][f'{export}-1000-{policy}'];saving='0.0 [baseline]'
            if policy!='full':
                c=placement['contrasts'][f'{export}:{policy}-minus-full']['collector_cpu_saving_percent']
                saving=f"{c['mean']:.1f} [{c['lower']:.1f}, {c['upper']:.1f}]"
            expected.append([name,f"{g['collector_cpu_s']['mean']:.2f}",saving,f"{g['jaeger_cpu_s']['mean']:.2f}",f"{100*g['json_bytes']['mean']/full['json_bytes']['mean']:.1f}",f"{g['collector_rss_bytes']['mean']/2**20:.1f}"])
    actual=[r for r in table('fifth-placement-rows.tex') if len(r)==6]
    assert actual==expected
    figure=read('data/derived/fifth-audit-20260928/cost-figure-data.json')['contrasts']
    old=read('data/derived/final-cost-20260925/cost-summary.json')
    assert len(figure)==10
    for key,value in figure.items():
        rate,export,timeout,policy=key.split(':')
        wanted=old['contrasts'][f'{export}-{timeout}-{policy}-minus-bypass'] if rate=='250' else high['contrasts'][f'{timeout}:tail100-minus-full']['collector_cpu_s']
        assert value==wanted
    counts={}
    for row in table('matched-probe-summary-rows.tex'):
        levels=[([x] if x!='Either' else allowed) for x,allowed in zip(row[:4],[['Yes','No'],['Immediate','Late'],['On','Off'],['Yes','No']])]
        for combination in itertools.product(*levels):assert combination not in counts;counts[combination]=row[4:]
    assert len(counts)==16
    for row in table('matched-probe-rows.tex'):assert counts[tuple(row[:4])]==row[4:7]
    for receipt in ['placement-validation.json','batching-validation.json','contract-validation.json','context-validation.json','validator-negative-controls.json','exclusion-validation.json']:
        assert read('docs/fifth-audit-20260928/'+receipt)['status']=='PASS'
    assert read('docs/fifth-audit-20260928/placement-validation.json')['cells']==40
    assert read('docs/fifth-audit-20260928/batching-validation.json')['cells']==20
    visual=read('docs/fifth-audit-20260928/pdf-visual-review.json')
    assert visual['status']=='PASS' and visual['pdf_sha256']==sha(pdf)
    assert visual['pages_inspected']==len(reader.pages)==len(visual['page_images_sha256'])
    for name,digest in visual['page_images_sha256'].items():
        page=ROOT/'tmp/fifth-audit-render'/name
        if page.exists():assert sha(page)==digest
    acm=read('docs/fifth-audit-20260928/acm-layout-check.json')
    assert acm['main_body_within_ten_pages'] and acm['overfull_boxes']==0
    result={'status':'PASS','utc':datetime.now(timezone.utc).isoformat(),'title':TITLE,'pdf_sha256':sha(pdf),'pdf_pages':len(reader.pages),'extracted_whitespace_tokens':len(pdf_text.split()),'cited_references':len(cites),'uncited_bibliography_entries':0,'figures':3,'tables':6,'template_author_main_section_order_preserved':True,'all_prior_measurement_macros_unchanged':True,'source_and_pdf_em_dashes':0,'tex_bibtex_warnings_bad_boxes':0,'previous_delivery_raw_files_unchanged':raw,'frozen_file_counts_unchanged':freeze_counts,'new_measured_cells':60,'all_final_pages_visually_inspected':True,'acm_pages_before_references':acm['pages_before_references']}
    (REPORT/'final-document-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
