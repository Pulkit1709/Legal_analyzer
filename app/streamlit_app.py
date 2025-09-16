import io
import json
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
import requests

from utils.extract import extract_document
from utils.segment import segment_clauses
from utils.classify import classify_clauses
from utils.report import build_json_report, build_csv_report
from utils.annotate import generate_annotated_pdf
from utils.viewer import rasterize_page, build_page_html


st.set_page_config(page_title="Legal Risk Analyzer (MVP)", layout="wide")

CATEGORY_COLORS = {
	"Safe": "#2e7d32",
	"Financial": "#1565c0",
	"Compliance": "#6a1b9a",
	"Liability": "#c62828",
	"Operational": "#ef6c00",
}


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
	categories = sorted(df["category"].dropna().unique())
	selected_categories = st.sidebar.multiselect("Filter by category", categories, default=categories)
	severity_levels = ["Low", "Medium", "High"]
	selected_severity = st.sidebar.multiselect("Filter by severity", severity_levels, default=severity_levels)
	conf_threshold = st.sidebar.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)

	mask = (
		(df["category"].isin(selected_categories))
		& (df["severity"].isin(selected_severity))
		& (df["confidence"] >= conf_threshold)
	)
	return df[mask]


st.title("Intelligent Legal Document Risk Analyzer — Streamlit MVP")
st.caption("Upload PDF/DOCX, extract clauses, classify risks, view highlights, and download reports.")

with st.sidebar:
	st.header("Upload")
	uploaded_file = st.file_uploader("Choose a contract (PDF/DOCX)", type=["pdf", "docx"])
	st.markdown("---")
	st.header("Options")
	use_api = st.checkbox("Use backend API for upload", value=False)
	api_base = st.text_input("API base URL", value="http://localhost:8080")
	join_short_sentences = st.checkbox("Merge short sentences into clauses", value=True)
	dpi = st.slider("Viewer DPI", 96, 200, 144, 4)
	user_id = st.text_input("User ID (for feedback)", value="user_local")
	st.markdown("---")
	st.caption("This is an MVP with heuristic classifier. Replace with ML model later.")

if uploaded_file:
	file_bytes = uploaded_file.read()
	if use_api:
		with st.spinner("Uploading to API..."):
			files = {"file": (uploaded_file.name, file_bytes, uploaded_file.type or "application/octet-stream")}
			try:
				resp = requests.post(f"{api_base}/api/upload", files=files, timeout=60)
			except Exception as e:
				st.error(f"Upload failed: {e}")
				raise st.stop()
			if resp.status_code >= 300:
				st.error(f"Upload failed: {resp.status_code} {resp.text}")
				raise st.stop()
			data = resp.json()
			st.success(f"Queued with job_id: {data.get('job_id')}")
			st.json(data)
			raise st.stop()

	with st.spinner("Extracting text..."):
		pages = extract_document(io.BytesIO(file_bytes), name=uploaded_file.name)
		doc_name = uploaded_file.name

	with st.spinner("Segmenting into clauses..."):
		clauses = segment_clauses(pages, merge_short=join_short_sentences)

	with st.spinner("Classifying risks..."):
		results = classify_clauses(clauses)

	rows: List[Dict[str, Any]] = []
	for item in results:
		rows.append({
			"clause_id": item["clause_id"],
			"page": item["page"],
			"text": item["text"],
			"category": item["predictions"][0]["category"] if item["predictions"] else "Safe",
			"confidence": item["predictions"][0]["confidence"] if item["predictions"] else 0.0,
			"severity_score": item["severity_score"],
			"severity": item["severity"],
			"explanation": item.get("explanation", ""),
			"bbox": None,
		})
	df = pd.DataFrame(rows)

	st.subheader("Summary")
	summary = {
		"total_clauses": int(len(results)),
		"flagged": int((df["category"] != "Safe").sum()),
		"by_category": df[df["category"] != "Safe"]["category"].value_counts().to_dict(),
	}
	cols = st.columns(3)
	cols[0].metric("Total clauses", summary["total_clauses"])
	cols[1].metric("Flagged", summary["flagged"])
	cols[2].metric("Categories flagged", len(summary["by_category"]))

	left, right = st.columns([3, 4])
	with left:
		st.markdown("Viewer")
		page_no = st.number_input("Page", min_value=1, max_value=max(1, int(df["page"].max() or 1)), value=1, step=1)
		img_bytes, img_w, img_h, page_size_pts = rasterize_page(file_bytes, int(page_no), dpi=dpi)
		highlights = []
		for _, r in df[df["page"] == int(page_no)].iterrows():
			if r["category"] == "Safe":
				continue
			highlights.append({
				"bbox": r.get("bbox"),
				"category": r["category"],
				"intensity": max(0.2, min(0.9, float(r["confidence"]))),
				"clause_id": r["clause_id"],
			})
		html = build_page_html(img_bytes, img_w, img_h, page_size_pts, highlights)
		st.components.v1.html(html, height=img_h + 80, scrolling=True)

	with right:
		st.subheader("Clauses")
		filtered = render_sidebar_filters(df)
		st.dataframe(
			filtered[["clause_id", "page", "category", "severity", "confidence", "text", "explanation"]],
			use_container_width=True,
			hide_index=True,
		)
		st.markdown("---")
		st.markdown("Feedback")
		selected_id = st.text_input("Clause ID to give feedback on", value=(filtered["clause_id"].iloc[0] if not filtered.empty else ""))
		new_labels = st.multiselect("Correct Label(s)", options=list(CATEGORY_COLORS.keys()), default=[])
		new_severity = st.selectbox("Severity", options=["", "Low", "Medium", "High"], index=0)
		comment = st.text_area("Comment")
		if st.button("Submit Feedback"):
			payload = {
				"user_id": user_id,
				"items": [
					{
						"clause_id": selected_id,
						"original_prediction": {},
						"new_labels": new_labels or None,
						"new_severity": new_severity or None,
						"comment": comment or None,
					}
				]
			}
			try:
				resp = requests.post(f"{api_base}/api/feedback/job_local", json=payload, timeout=30)
				if resp.status_code < 300:
					st.success("Feedback submitted")
				else:
					st.error(f"Feedback failed: {resp.status_code} {resp.text}")
			except Exception as e:
				st.error(f"Feedback error: {e}")

	st.subheader("Downloads")
	json_report = build_json_report(doc_name, results, summary)
	csv_report = build_csv_report(df)

	col1, col2, col3 = st.columns(3)
	with col1:
		st.download_button(
			label="Download JSON report",
			data=json.dumps(json_report, ensure_ascii=False, indent=2).encode("utf-8"),
			file_name=f"{doc_name}_risk_report.json",
			mime="application/json",
		)
	with col2:
		st.download_button(
			label="Download CSV",
			data=csv_report.getvalue(),
			file_name=f"{doc_name}_clauses.csv",
			mime="text/csv",
		)
	with col3:
		if doc_name.lower().endswith(".pdf"):
			with st.spinner("Generating annotated PDF..."):
				annotated = generate_annotated_pdf(file_bytes, results)
			st.download_button(
				label="Download annotated PDF",
				data=annotated,
				file_name=f"{doc_name.replace('.pdf','')}_annotated.pdf",
				mime="application/pdf",
			)
		else:
			st.caption("Annotated PDF available only for PDF uploads.")
else:
	st.info("Upload a PDF or DOCX to begin.")
