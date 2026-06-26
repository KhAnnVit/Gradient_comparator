from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image


@dataclass
class PDFLoadSettings:
    """
    Настройки загрузки PDF.
    """

    dpi: int = 300
    poppler_path: Optional[Path | str] = None


@dataclass
class PDFLoadResult:
    """
    Результат загрузки PDF-страницы.
    """

    success: bool

    pdf_path: Optional[Path] = None

    # Загруженная страница как PIL.Image.
    page_image: Optional[Image.Image] = None

    # Номер текущей страницы.
    # Внутри приложения используем 0-based:
    # 0 — первая страница, 1 — вторая и т.д.
    page_number: int = 0

    # Общее количество страниц в PDF.
    page_count: int = 0

    error_message: str = ""