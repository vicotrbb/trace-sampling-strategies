#!/usr/bin/env python3
"""Internal layout estimate only; preserve the delivered article template."""
import json,re,shutil,subprocess
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'tmp/fifth-audit-acm-check';out.mkdir(exist_ok=True)
receipt_dir=ROOT/'docs/fifth-audit-20260928';receipt_dir.mkdir(exist_ok=True)
for p in (ROOT/'paper').glob('*.tex'):shutil.copy2(p,out/p.name)
shutil.copy2(ROOT/'paper/references.bib',out/'references.bib');shutil.copytree(ROOT/'paper/figures',out/'figures',dirs_exist_ok=True)
p=out/'main.tex';s=p.read_text().replace(r'\documentclass[11pt]{article}',r'\documentclass[sigconf,nonacm]{acmart}')
s=s.replace(r'\usepackage[margin=1.1in]{geometry}','').replace(r'\usepackage[numbers,sort&compress]{natbib}','')
s=s.replace(r'\usepackage{amsmath,amssymb,amsthm}',r'\usepackage{amsthm}')
s=s.replace(r'\usepackage[hidelinks]{hyperref}',r'\hypersetup{hidelinks}')
title=re.search(r'pdftitle=\{([^}]+)\}',s).group(1)
start=s.index('\\title{');end=s.index('\\author{',start)
s=s[:start]+'\\title{'+title+'}\n'+s[end:]
a=s.index('\\author{');b=s.index('\\date{',a)
s=s[:a]+'''\\author{Victor Bona}
\\affiliation{\\institution{Independent Researcher}\\city{Blumenau}\\country{Brazil}}
\\email{victor.bona@hotmail.com}
\\settopmatter{printacmref=false,printccs=false}
\\citestyle{acmnumeric}
'''+s[b:]
s=s.replace('\\maketitle\n\\begin{abstract}','\\begin{abstract}').replace('\\end{abstract}','\\end{abstract}\n\\maketitle')
s=s.replace('\\bibliographystyle{plainnat}','\\clearpage\n\\bibliographystyle{ACM-Reference-Format}')
p.write_text(s)
for p in out.glob('*.tex'):
    s=p.read_text().replace('\\begin{table}[htbp]','\\begin{table*}[t]').replace('\\end{table}','\\end{table*}').replace('\\begin{figure}[htbp]','\\begin{figure*}[t]').replace('\\end{figure}','\\end{figure*}')
    p.write_text(s)
with (receipt_dir/'acm-layout-build.txt').open('w') as log:
    subprocess.run(['latexmk','-pdf','-interaction=nonstopmode','-halt-on-error','main.tex'],cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True)
reader=PdfReader(out/'main.pdf');pages=[p.extract_text() for p in reader.pages]
reference=next(i for i,p in enumerate(pages) if re.search(r'(?m)^References\s*$',p))
log=(out/'main.log').read_text()
result={'purpose':'Internal ACM layout estimate; not an anonymized or submission-ready artifact','title':title,'pages_before_references':reference,'total_pages':len(pages),'main_body_within_ten_pages':reference<=10,'references_forced_to_next_page':True,'tables_and_figures_use_full_width_floats':True,'source_template_unchanged':True,'overfull_boxes':len(re.findall('Overfull',log))}
(receipt_dir/'acm-layout-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
