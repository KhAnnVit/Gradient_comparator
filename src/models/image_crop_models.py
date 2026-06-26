from dataclasses import dataclass
from typing import Optional

from PIL import Image


@dataclass
class ImageCropRequest:
    """
    Данные, необходимые для вырезания области изображения,
    выделенной пользователем на Canvas.
    """

    source_image: Image.Image

    # Координаты рамки выделения на Canvas:
    # x1, y1, x2, y2
    selection_coords: tuple[float, float, float, float]

    canvas_width: int
    canvas_height: int

    displayed_image_width: int
    displayed_image_height: int

    offset_x: int
    offset_y: int

    zoom_factor: float

    # Угол поворота изображения.
    angle: int = 0

    # Нужно ли вернуть вырезанный фрагмент обратно
    # в исходную ориентацию.
    restore_original_orientation: bool = True


@dataclass
class ImageCropResult:
    """
    Результат вырезания области изображения.
    """

    success: bool
    image: Optional[Image.Image] = None
    crop_box: Optional[tuple[int, int, int, int]] = None
    error_message: str = ""