from __future__ import annotations

from typing import List, Dict, Any
import io
import json
import pandas as pd
from collections import Counter
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from utils.pii import redact


def build_json_report(document_name: str, results: List[Dict[str, Any]], summary: Dict[str, Any], redact_pii: bool = False) -> Dict[str, Any]:
	severity_dist = Counter([r.get("severity", "") for r in results if r.get("severity")])
	by_category = Counter([])
	report_clauses = []
	for r in results:
		for p in r.get("predictions", []):
			by_category[p.get("label") or p.get("category", "")] += 1
		c = dict(r)
		if redact_pii:
			c["text"] = redact(c.get("text", ""))
		report_clauses.append(c)
	return {
		"document_name": document_name,
		"summary": {
			**summary,
			"severity_distribution": dict(severity_dist),
			"by_category": dict(by_category) or summary.get("by_category", {}),
		},
		"clauses": report_clauses,
		"recommendations": [],
	}


def build_csv_report(df: pd.DataFrame, redact_pii: bool = False) -> io.BytesIO:
	buffer = io.StringIO()
	if redact_pii and "text" in df.columns:
		df = df.copy()
		df["text"] = df["text"].astype(str).map(lambda x: redact(x))
	cols = [
		"clause_id", "page", "category", "severity", "confidence", "text", "explanation"
	]
	df.to_csv(buffer, columns=[c for c in cols if c in df.columns], index=False)
	bio = io.BytesIO(buffer.getvalue().encode("utf-8"))
	return bio


def build_pdf_report(document_name: str, results: List[Dict[str, Any]], summary: Dict[str, Any], redact_pii_flag: bool = False) -> bytes:
	buf = io.BytesIO()
	doc = SimpleDocTemplate(buf, pagesize=A4)
	styles = getSampleStyleSheet()
	story = []

	story.append(Paragraph(f"Risk Report: {document_name}", styles['Title']))
	story.append(Spacer(1, 12))
	story.append(Paragraph(f"Total Clauses: {summary.get('total_clauses', len(results))}", styles['Normal']))
	story.append(Paragraph(f"Flagged: {summary.get('flagged', 0)}", styles['Normal']))
	story.append(Spacer(1, 12))

	rows = [["Clause ID", "Page", "Category", "Severity", "Confidence", "Excerpt"]]
	for r in results:
		cat = (r.get("predictions") or [{}])[0].get("category") or (r.get("predictions") or [{}])[0].get("label")
		conf = (r.get("predictions") or [{}])[0].get("confidence") or (r.get("predictions") or [{}])[0].get("score")
		text = r.get("text", "")
		if redact_pii_flag:
			text = redact(text)
		rows.append([
			r.get("clause_id", ""),
			r.get("page", ""),
			cat or "",
			r.get("severity", ""),
			f"{conf:.2f}" if isinstance(conf, (int, float)) else "",
			(text[:140] + ("..." if len(text) > 140 else "")),
		])
	table = Table(rows, repeatRows=1)
	table.setStyle(TableStyle([
		('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
		('GRID', (0,0), (-1,-1), 0.25, colors.grey),
		('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
		('ALIGN', (1,1), (1,-1), 'CENTER'),
	]))
	story.append(table)

	doc.build(story)
	return buf.getvalue()
