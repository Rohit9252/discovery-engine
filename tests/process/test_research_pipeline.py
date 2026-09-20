from pathlib import Path

import src.process.research_pipeline as pipeline


def test_pipeline_runs_both_passes_and_exports_without_unnecessary_retries(monkeypatch):
    calls=[]
    monkeypatch.setattr(pipeline,'run_research',lambda **kwargs: calls.append(kwargs) or {'failed':0})
    monkeypatch.setattr(pipeline,'export_report',lambda:(Path('report.json'),{'state':'completed'}))
    result=pipeline.run_pipeline(workers=2)
    assert calls==[{'workers':2},{'workers':2,'review_candidates':True}]
    assert result['status']['state']=='completed'


def test_pipeline_retries_only_failed_review_candidates_as_single_records(monkeypatch):
    calls=[]
    def fake(**kwargs):
        calls.append(kwargs)
        return {'failed':1 if len(calls)==2 else 0}
    monkeypatch.setattr(pipeline,'run_research',fake)
    monkeypatch.setattr(pipeline,'export_report',lambda:(Path('report.json'),{'state':'partial'}))
    result=pipeline.run_pipeline()
    assert calls[-1]=={'workers':4,'review_candidates':True,'batch_size':1}
    assert result['status']['state']=='partial'  # never force completion over an export's actual state
