"""Turn uploaded files into plain text that Yatharth can fact-check."""
import base64
import io

IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
TEXT_TYPES = ("txt", "md", "csv", "json")


def file_to_text(name: str, data: bytes) -> str:
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext in TEXT_TYPES:
        return data.decode("utf-8", errors="ignore")
    if ext == "pdf":
        try:
            from pypdf import PdfReader

            pages = PdfReader(io.BytesIO(data)).pages[:20]
            text = "\n".join((p.extract_text() or "") for p in pages).strip()
        except Exception:
            raise ValueError(f"{name}: could not read this PDF.")
        if not text:
            raise ValueError(f"{name}: no text found (scanned PDF?). Upload it as an image instead.")
        return text
    if ext in IMAGE_TYPES:
        from llm import read_image  # needs Bifrost + a vision model

        text = read_image(base64.b64encode(data).decode(), IMAGE_TYPES[ext]).strip()
        if not text:
            raise ValueError(f"{name}: no readable text found in the image.")
        return text
    raise ValueError(f"{name}: unsupported file type. Use txt, md, pdf, png, jpg or webp.")
