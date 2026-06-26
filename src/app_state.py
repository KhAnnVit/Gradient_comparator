from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any


@dataclass
class AppState:
    """
    Центральное состояние приложения.

    AppState НЕ должен управлять интерфейсом,
    НЕ должен вызывать logger,
    НЕ должен обращаться к controller.

    Его задача — только хранить данные приложения.
    """

    # =========================================================
    # PDF
    # =========================================================

    current_pdf_path: Optional[Path] = None
    current_pdf_page: int = 0
    selected_image: Optional[Any] = None

    # =========================================================
    # OCR
    # =========================================================

    ocr_text: str = ""
    ocr_source: str = ""

    # =========================================================
    # COMPARE
    # =========================================================

    compare_text_1: str = ""
    compare_text_2: str = ""

    compare_text_1_source: str = ""
    compare_text_2_source: str = ""

    # =========================================================
    # EXCEL
    # =========================================================

    current_excel_path: Optional[Path] = None
    current_excel_sheet: str = ""

    current_excel_row: Optional[int] = None
    current_excel_col: Optional[int] = None
    current_excel_cell_value: str = ""

    # =========================================================
    # ОБЩЕЕ СОСТОЯНИЕ
    # =========================================================

    current_tab: str = "tab1"
    status_message: str = ""

    # =========================================================
    # RESET-МЕТОДЫ
    # =========================================================

    def reset_ocr(self):
        """Очищает данные OCR."""
        self.selected_image = None
        self.ocr_text = ""
        self.ocr_source = ""

    def reset_compare(self):
        """Очищает данные сравнения."""
        self.compare_text_1 = ""
        self.compare_text_2 = ""
        self.compare_text_1_source = ""
        self.compare_text_2_source = ""

    def reset_excel_selection(self):
        """Очищает информацию о выбранной Excel-ячейке."""
        self.current_excel_row = None
        self.current_excel_col = None
        self.current_excel_cell_value = ""

    def set_status(self, message: str):
        """Сохраняет последнее статусное сообщение."""
        self.status_message = message