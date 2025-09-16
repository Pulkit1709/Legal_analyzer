from utils.segmenter import segment_pages_to_clauses


def test_segment_basic_headings_and_merge():
	pages = [
		{
			"page_number": 1,
			"blocks": [
				{"text": "1. Confidentiality", "bbox": {"x":0,"y":0,"w":100,"h":10}},
				{"text": "The parties shall keep information confidential.", "bbox": {"x":0,"y":12,"w":200,"h":10}},
				{"text": "Notwithstanding the foregoing, disclosures may occur as required by law.", "bbox": {"x":0,"y":24,"w":200,"h":10}},
				{"text": "2. Termination", "bbox": {"x":0,"y":36,"w":100,"h":10}},
				{"text": "Either party may terminate upon 30 days' notice.", "bbox": {"x":0,"y":48,"w":200,"h":10}},
			],
		}
	]
	clauses = segment_pages_to_clauses(pages)
	assert any("Confidentiality" in c.get("parent_section_title", "") for c in clauses)
	assert any("Termination" in c.get("parent_section_title", "") for c in clauses)
	for c in clauses:
		assert "clause_id" in c and "text" in c and "page" in c
		assert isinstance(c.get("bounding_boxes", []), list)
