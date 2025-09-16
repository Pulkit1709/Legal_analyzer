from __future__ import annotations

from typing import List, Dict, Any, Tuple
import io
import base64
import fitz  # PyMuPDF

CATEGORY_COLORS = {
	"Safe": "#2e7d32",
	"Financial": "#1565c0",
	"Compliance": "#6a1b9a",
	"Liability": "#c62828",
	"Operational": "#ef6c00",
}


def rasterize_page(pdf_bytes: bytes, page_number: int, dpi: int = 144) -> Tuple[bytes, int, int, Tuple[float, float]]:
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	page_index = max(0, page_number - 1)
	page = doc[page_index]
	mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
	pix = page.get_pixmap(matrix=mat, alpha=False)
	img_bytes = pix.tobytes(output="png")
	page_size_pts = (page.rect.width, page.rect.height)
	doc.close()
	return img_bytes, pix.width, pix.height, page_size_pts


def _to_data_uri(png_bytes: bytes) -> str:
	b64 = base64.b64encode(png_bytes).decode("ascii")
	return f"data:image/png;base64,{b64}"


def _scale_bbox_to_pixels(bbox: Dict[str, float], page_size_pts: Tuple[float, float], img_size_px: Tuple[int, int]) -> Dict[str, float]:
	px_per_pt_x = img_size_px[0] / page_size_pts[0]
	px_per_pt_y = img_size_px[1] / page_size_pts[1]
	x = bbox.get("x", 0.0) * px_per_pt_x
	y = bbox.get("y", 0.0) * px_per_pt_y
	w = bbox.get("w", 0.0) * px_per_pt_x
	h = bbox.get("h", 0.0) * px_per_pt_y
	return {"x": x, "y": y, "w": w, "h": h}


def build_page_html(img_bytes: bytes, img_w: int, img_h: int, page_size_pts: Tuple[float, float], highlights: List[Dict[str, Any]]) -> str:
	data_uri = _to_data_uri(img_bytes)
	layers = []
	for h in highlights:
		bbox = h.get("bbox") or {}
		cat = h.get("category", "Safe")
		opacity = max(0.15, min(0.9, float(h.get("intensity", 0.4))))
		px_bbox = _scale_bbox_to_pixels(bbox, page_size_pts, (img_w, img_h))
		layers.append(
			f'<div title="{cat}" style="position:absolute; left:{px_bbox["x"]}px; top:{px_bbox["y"]}px; '
			f'width:{px_bbox["w"]}px; height:{px_bbox["h"]}px; '
			f'background:{CATEGORY_COLORS.get(cat, "#888888")}; opacity:{opacity};"></div>'
		)
	legend = ''.join([f'<span style="display:inline-block;width:12px;height:12px;background:{COLOR};margin-right:6px;"></span>{name}&nbsp;&nbsp;'
					  for name, COLOR in CATEGORY_COLORS.items()])
	html = f'''
	<div style="display:flex;flex-direction:column;gap:8px;">
	  <div style="position:relative; width:{img_w}px; height:{img_h}px; border:1px solid #ddd;">
		<img src="{data_uri}" width="{img_w}" height="{img_h}" style="position:absolute; left:0; top:0;" />
		{''.join(layers)}
	  </div>
	  <div style="font-size:12px;color:#555;">Legend: {legend}</div>
	</div>
	'''
	return html
