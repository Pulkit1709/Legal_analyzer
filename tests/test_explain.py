import pytest
from ml.explain import explain_text


def test_explain_output_structure(tmp_path):
	# Requires a model artifact to exist; skip if not present
	import os
	model_dir = "artifacts/model_roberta"
	if not os.path.isdir(model_dir):
		pytest.skip("model artifact not found")
	res = explain_text(model_dir, "Vendor shall not be liable for damages.", method="ig")
	assert "token_importances" in res and isinstance(res["token_importances"], list)
	assert "explanation_text" in res and isinstance(res["explanation_text"], str)
