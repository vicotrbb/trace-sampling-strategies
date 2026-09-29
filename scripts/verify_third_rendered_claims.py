#!/usr/bin/env python3
"""Check manuscript table text against independently selected summary entries."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'paper';D=ROOT/'data/derived/third-audit-20260925'
def read(name):return json.loads((D/name).read_text())
def rows(name):return [[v.strip() for v in line.rstrip().removesuffix('\\\\').split('&')] for line in (P/name).read_text().splitlines()]
def main():
    diagnosis=read('diagnosis-summary.json');cost=read('load-summary.json')
    cohort=rows('window-cohort-rows.tex');assert len(cohort)==3
    for line,w in zip(cohort,[20,50,200]):
        b=diagnosis['baselines'][str(w)];counts=diagnosis['protected_counts'][str(w)]
        expected=[str(w),str(b['correct'])+'/600',format(b['correct']/6,'.2f'),format(counts['reference']/(6*w),'.2f'),format(counts['incident']/(6*w),'.2f')]
        assert line==expected,(line,expected)
    supported=rows('window-supported-rows.tex');assert len(supported)==6
    for line,(w,p) in zip(supported,[(w,p) for w in [20,50,200] for p in ['head','tail']]):
        outcomes=[v for v in diagnosis['results'] if v['window']==w and v['policy']==p and v.get('meets_five_point_margin')]
        if not outcomes:assert line==[str(w),p.capitalize(),'None','--','--','--','--'];continue
        best=sorted(outcomes,key=lambda v:v['budget'])[0]
        expected=[str(w),p.capitalize(),format(100-100*best['budget'],'.0f'),format(best['correct']/50,'.2f'),format(best['upper_loss_bound']*100,'.2f'),format(best['mean_reference_retained'],'.1f'),format(best['mean_incident_retained'],'.1f')]
        assert line==expected,(line,expected)
    boundary=rows('boundary-rows.tex');assert len(boundary)==4
    for line,policy in zip(boundary,['full','gate10','collector10','tail10']):
        group=cost['groups'][policy]
        assert line[1]==format(group['accepted_spans']['mean']/30000,'.1f')
        assert line[2]==format(group['cpu_s']['mean'],'.3f')
        if policy=='full':assert line[3]=='Reference'
        else:
            contrast=cost['contrasts'][policy+'-minus-full']['cpu_saving_percent']
            assert line[3]==f"{contrast['mean']:.1f} [{contrast['lower']:.1f}, {contrast['upper']:.1f}]"
        assert line[4]==format(100*group['json_bytes']['mean']/cost['groups']['full']['json_bytes']['mean'],'.1f')
        assert line[5]==format(group['max_rss_bytes']['mean']/2**20,'.1f')
    macros=re.findall(r'\\newcommand\{\\([A-Za-z]+)\}\{([^}]+)\}',(P/'third-audit-measurements.tex').read_text())
    assert len(macros)==len((P/'third-audit-measurements.tex').read_text().splitlines())
    assert dict(macros)['SensitivityThreshold']==format(diagnosis['threshold_ms'],'.2f')
    receipt={'status':'PASS','cohort_rows':3,'supported_rows':6,'boundary_rows':4,'generated_macro_names_valid':len(macros),'selection_criterion':'minimum qualifying rate among the complete declared grid'}
    (ROOT/'docs/third-audit-20260925/rendered-claims-check.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
