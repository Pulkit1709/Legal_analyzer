from utils.features import extract_features_for_clause


def test_placeholders_and_money_date_keywords():
	clause = {
		"text": "Vendor shall not be liable to pay $10,000 on or before Jan 1, 2026. Contact admin@example.com or visit https://example.com",
	}
	aug = extract_features_for_clause(clause)
	f = aug["features"]
	assert aug["normalized_text"].count("[MONEY]") >= 1
	assert f["has_money"] is True
	assert f["has_date"] is True
	assert f["has_email"] is True
	assert f["has_url"] is True
	assert f["has_modals"] in (True, False)  # model dependent
	assert f["has_negation"] is True


def test_keywords_and_stats():
	clause = {"text": "This Limitation of Liability clause shall survive termination and indemnity obligations remain."}
	aug = extract_features_for_clause(clause)
	f = aug["features"]
	keys = f["keywords"]
	assert keys.get("limitation") is True
	assert keys.get("termination") is True
	assert keys.get("indemnity") is True
	assert f["length_tokens"] > 0
