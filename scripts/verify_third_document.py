#!/usr/bin/env python3
"""Check the delivered paper, retained evidence, frozen sources, and cleanup."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,tarfile
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'docs/revision-20260924'
PREVIOUS=ROOT/'docs/final-pass-20260925'
CURRENT=ROOT/'docs/second-audit-20260925'
FINAL=ROOT/'docs/third-audit-20260925'
TITLE='How Much Can We Sample? A Controlled Study of Head and Tail Sampling with OpenTelemetry'

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def active_sources():
    found={}
    def visit(name):
        if not name.endswith('.tex'):name+='.tex'
        if name in found:return
        path=ROOT/'paper'/name;assert path.is_file(),name
        value=path.read_text();found[name]=value
        for target in re.findall(r'\\(?:input|tableinput)\{([^}]+)\}',value):visit(target)
    visit('main.tex');return found

def main():
    pdf=ROOT/'output/pdf/how-much-can-we-sample.pdf';reader=PdfReader(pdf)
    text='\n'.join(page.extract_text() for page in reader.pages)
    sources=active_sources();source='\n'.join(sources.values())
    aux=(ROOT/'paper/main.aux').read_text();log=(ROOT/'paper/main.log').read_text();biblog=(ROOT/'paper/main.blg').read_text()
    citations={k for group in re.findall(r'\\citation\{([^}]+)\}',aux) for k in group.split(',')}
    bibliography=set(re.findall(r'\\bibcite\{([^}]+)\}',aux));labels=re.findall(r'\\newlabel\{([^}]+)\}',aux)
    references=set(re.findall(r'\\(?:ref|eqref)\{([^}]+)\}',source))
    assert citations==bibliography and references<=set(labels)
    assert len(labels)==len(set(labels))
    assert not re.search(r'Overfull|Underfull|LaTeX Warning|Package .* Warning|undefined|Missing character',log)
    assert 'Warning--' not in biblog and 'error message' not in biblog
    assert not re.search('\u2014|---|textemdash',source) and '\u2014' not in text
    assert not re.search(r'\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b',source)
    assert pdf.read_bytes()==(ROOT/'paper/main.pdf').read_bytes()
    assert reader.metadata.title==TITLE and reader.metadata.author=='Victor Bona'
    with tarfile.open(ORIGINAL/'original-source-and-paper.tar.gz') as archive:
        originals={m.name:archive.extractfile(m).read().decode() for m in archive.getmembers() if m.isfile() and m.name.startswith('paper/') and m.name.endswith('.tex') and not Path(m.name).name.startswith('._')}
        original_manifest=archive.extractfile('SHA256SUMS').read().decode()
    original=originals['paper/main.tex'];current=sources['main.tex']
    expected=original.split('\\begin{document}')[0]
    expected=expected.replace('How Much Can We Sample? Evaluating Trace Sampling Strategies for Production Observability',TITLE)
    expected=expected.replace('How Much Can We Sample?\\\\Evaluating Trace Sampling Strategies\\\\for Production Observability','How Much Can We Sample?\\\\A Controlled Study of Head and Tail Sampling\\\\with OpenTelemetry')
    expected=expected.replace('OpenTelemetry, formal analysis','OpenTelemetry, measurement study')
    actual=current.split('\\begin{document}')[0]
    for name in ['revision-measurements.tex','cost-measurements.tex','second-audit-measurements.tex','third-audit-measurements.tex']:actual=actual.replace('\\input{'+name+'}\n','')
    assert actual==expected,'Unexpected template/author/preamble change'
    def sections(name,archived=False):
        value=originals[name] if archived else (ROOT/name).read_text()
        if name=='paper/main.tex':value=value.split('\\appendix')[0]
        result=[]
        for match in re.finditer(r'\\section\*?\{([^}]+)\}|\\input\{([^}]+)\}',value):
            if match[1]:result.append(match[1])
            else:
                target='paper/'+match[2]
                exists=target in originals if archived else (ROOT/target).exists()
                if exists:result.extend(sections(target,archived))
        return result
    assert sections('paper/main.tex',True)==sections('paper/main.tex')
    def preserve(manifest):
        count=0
        for line in manifest.splitlines():
            expected,name=line.split('  ',1)
            if name.startswith('data/raw/'):assert digest(ROOT/name)==expected,name;count+=1
        return count
    original_raw=preserve(original_manifest);assert original_raw==722
    assert digest(CURRENT/'prerevision-source-and-paper.tar.gz')=='46c98cc16fdea05e52b67edab12fa8a9bf331aa1329fa88d731aa36f78f72acf'
    with tarfile.open(CURRENT/'prerevision-source-and-paper.tar.gz') as archive:
        prior_manifest=archive.extractfile('SHA256SUMS').read().decode()
    previous_raw=preserve(prior_manifest);assert previous_raw==4514
    frozen_counts=[]
    for folder,name,key in [(ORIGINAL,'confirmatory-freeze.json','sha256'),(PREVIOUS,'execution-freeze.json','sha256'),(CURRENT,'execution-freeze.json','files')]:
        freeze=json.loads((folder/name).read_text())
        for filename,expected in freeze[key].items():assert digest(ROOT/filename)==expected,filename
        frozen_counts.append(len(freeze[key]))
    cost=ROOT/'data/raw/final-cost-20260925/confirm-v1'
    assert (cost/'executed-source/execution-freeze.json').read_bytes()==(PREVIOUS/'execution-freeze.json').read_bytes()
    raw=ROOT/'data/raw/second-audit-20260925'
    for group in ['load-confirm-v1','diagnosis-confirm-v1','diagnosis-replay-v1']:
        assert (raw/group/'executed-source/execution-freeze.json').read_bytes()==(CURRENT/'execution-freeze.json').read_bytes()
    load=json.loads((CURRENT/'load-validation.json').read_text());diagnosis=json.loads((CURRENT/'diagnosis-validation.json').read_text());contract=json.loads((CURRENT/'contract-validation.json').read_text())
    assert load['status']=='PASS' and load['cells']==80
    assert diagnosis['status']=='PASS' and diagnosis['corpus_episodes']==600 and diagnosis['comparison_rows']==80000 and diagnosis['intervals_recomputed_by_binomial_inversion']
    assert contract['status']=='PASS' and contract['scope']=='all measured extensions'
    summary=json.loads((ROOT/'data/derived/second-audit-20260925/diagnosis-summary.json').read_text())
    assert summary['baseline']['full_correct']==568 and summary['baseline']['episodes']==600
    assert {(r['policy'],r['budget']) for r in summary['results'] if r.get('meets_five_point_margin')}=={(p,b) for p in ['head','tail'] for b in [.8,.95]}
    for p in ['head','tail']:
        value=next(r for r in summary['results'] if r['policy']==p and r['budget']==.8)
        assert value['upper_loss_bound']<=.05
    assert json.loads((ROOT/'data/derived/second-audit-20260925/load-summary.json').read_text())['cells']==80
    assert json.loads((CURRENT/'corruption-checks.json').read_text())['status']=='PASS'
    model=json.loads((ROOT/'data/raw/revision-20260924/model-verification.json').read_text());assert model['status']=='PASS'
    assert digest(ROOT/'data/raw/revision-20260924/model-verification-source.py')==digest(ROOT/'tests/verify_model.py')
    with tarfile.open(FINAL/'prerevision-source-and-paper.tar.gz') as archive:
        last_manifest=archive.extractfile('SHA256SUMS').read().decode()
    last_raw=preserve(last_manifest)
    new_freeze=json.loads((FINAL/'execution-freeze.json').read_text())
    for name,sha in new_freeze['files'].items():assert digest(ROOT/name)==sha
    newer=ROOT/'data/raw/third-audit-20260925'
    for group in ['diagnosis-confirm-v1','diagnosis-replay-v1','load-confirm-v1']:
        assert json.loads((newer/group/'executed-source/execution-freeze.json').read_text())==new_freeze
    for name in ['load-validation.json','diagnosis-validation.json','contract-validation.json','corruption-checks.json']:
        assert json.loads((FINAL/name).read_text())['status']=='PASS'
    assert json.loads((FINAL/'diagnosis-validation.json').read_text())['comparison_rows']==240000
    assert json.loads((FINAL/'load-validation.json').read_text())['cells']==20
    visual=json.loads((FINAL/'pdf-visual-review.json').read_text())
    assert visual['status']=='PASS' and visual['pdf_sha256']==digest(pdf) and visual['pages_inspected']==len(reader.pages)
    assert len(visual['page_images_sha256'])==len(reader.pages)
    assert not (FINAL/'cleanup-namespace.txt').read_text().strip()
    nodes=json.loads((FINAL/'cleanup-nodes.json').read_text())
    ready=[n['metadata']['name'] for n in nodes['items'] if any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions'])]
    assert len(ready)==len(nodes['items'])
    figures=sum(s.startswith('fig:') for s in labels);tables=sum(s.startswith('tab:') for s in labels)
    assert figures==2 and tables==7
    receipt={'status':'PASS','utc':datetime.now(timezone.utc).isoformat(),'pdf_sha256':digest(pdf),'pdf_pages':len(reader.pages),'cited_references':len(bibliography),'figures':figures,'tables':tables,'all_citations_and_references_resolve':True,'template_settings_author_and_main_section_order_preserved':True,'permitted_title_and_keyword_changes':True,'active_tex_files':len(sources),'source_emdash_count':0,'pdf_emdash_count':0,'tex_warnings_or_bad_boxes':0,'bibtex_warnings':0,'original_raw_files_unchanged':original_raw,'previous_delivery_raw_files_unchanged':previous_raw,'frozen_file_counts':frozen_counts,'load_cells_validated':80,'diagnosis_incidents_validated':600,'diagnosis_replay_rows_validated':80000,'last_delivery_raw_files_unchanged':last_raw,'new_load_cells_validated':20,'new_diagnosis_incidents':600,'new_replay_rows_validated':240000,'new_frozen_files_unchanged':len(new_freeze['files']),'all_final_pages_visually_inspected':True,'namespace_removed':True,'nodes_ready':ready}
    (FINAL/'final-document-checks.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
