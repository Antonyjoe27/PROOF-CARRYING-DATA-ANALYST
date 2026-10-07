PDF_MESSAGE = "PDF support is not yet enabled"


def load_pdf(path):
    """Placeholder (stretch goal). Raises a clear message; CSV/XLSX workflows are unaffected."""
    raise NotImplementedError(f"{PDF_MESSAGE} ({getattr(path, 'name', path)} was not loaded).")
