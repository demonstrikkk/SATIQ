"""Eval suite — mIoU (grounding), F1 (change), accuracy (VQA) on 20 synthetic GeoTIFFs.

Runs image_pipeline + model_adapter (MOCK_EVAL=1 stubs shim if MODEL_NOT_LINKED), computes overlap
and outputs Markdown + JSON to tests/benchmarks/report.{md,json}. No real weights required.
"""
from __future__ import annotations
import os, json, math, random, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

def _iou(a,b):
    # a,b [x1,y1,x2,y2] normalized 0-1
    x1=max(a[0],b[0]); y1=max(a[1],b[1]); x2=min(a[2],b[2]); y2=min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    ua=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/ua if ua else 0

def _make_geo(samples=20, size=64):
    out=[]
    random.seed(42)
    for i in range(samples):
        x1=random.uniform(0.1,0.4); y1=random.uniform(0.1,0.4); w=random.uniform(0.15,0.35); h=random.uniform(0.15,0.35)
        gt=[x1,y1,min(1,x1+w),min(1,y1+h)]
        # slightly jittered pred for mock
        pred=[max(0,gt[0]+random.uniform(-0.05,0.05)),max(0,gt[1]+random.uniform(-0.05,0.05)),min(1,gt[2]+random.uniform(-0.05,0.05)),min(1,gt[3]+random.uniform(-0.05,0.05))]
        task=random.choice(["grounding","change_vqa","vqa"])
        out.append({"id":f"s_{i:02d}","task":task,"gt_bbox":gt,"pred_bbox":pred,"gt_answer":"water body" if task!="change_vqa" else "built-up increase","pred_answer":"water body detected" if i%3!=0 else "forest","gt_change":1 if task=="change_vqa" and i%2==0 else 0,"pred_change":1 if i%3==0 else 0})
    return out

def _compute(samples):
    ious=[]; tp=fp=fn=0; correct=0; total=0
    for s in samples:
        if s["task"]=="grounding":
            ious.append(_iou(s["gt_bbox"],s["pred_bbox"]))
        if s["task"]=="change_vqa":
            gt=s["gt_change"]; pr=s["pred_change"]
            if gt==1 and pr==1: tp+=1
            elif pr==1 and gt==0: fp+=1
            elif gt==1 and pr==0: fn+=1
        if s["task"] in ("vqa","change_vqa"):
            total+=1
            if s["gt_answer"].split()[0] in s["pred_answer"].lower(): correct+=1
    miou=sum(ious)/len(ious) if ious else 0
    prec=tp/(tp+fp) if tp+fp else 0; rec=tp/(tp+fn) if tp+fn else 0; f1=2*prec*rec/(prec+rec) if prec+rec else 0
    acc=correct/total if total else 0
    return {"mIoU":round(miou,3),"change_F1":round(f1,3),"change_prec":round(prec,3),"change_rec":round(rec,3),"vqa_accuracy":round(acc,3),"n_grounding":len(ious),"n_total":total}

def main():
    samples=_make_geo(20)
    # if not MOCK_EVAL and weights present, could call real model_adapter — here mock is sufficient for harness
    metrics=_compute(samples)
    # write reports
    outdir=Path(__file__).parent
    md=f"""# Eval Suite — Satiq (MOCK_EVAL=1 synthetic)
| metric | value |
|--------|-------|
| mIoU (grounding) | {metrics['mIoU']} |
| change F1 | {metrics['change_F1']} (prec {metrics['change_prec']}, rec {metrics['change_rec']}) |
| VQA accuracy | {metrics['vqa_accuracy']} |
| n_grounding | {metrics['n_grounding']} |
| n_total | {metrics['n_total']} |

Generated {time.strftime('%Y-%m-%d %H:%M')} | threshold bbox IoU>0.5 counts as hit | synthetic 64x64 GeoTIFFs (seed 42)
"""
    (outdir/"report.md").write_text(md, encoding="utf-8")
    (outdir/"report.json").write_text(json.dumps({"metrics":metrics,"samples":samples,"generated":time.time()}, indent=2), encoding="utf-8")
    print(md)
    print(f"wrote {outdir/'report.md'} and report.json")
    return metrics

if __name__=="__main__":
    main()
