from src.models.image_crop_models import ImageCropRequest, ImageCropResult
from src.utils.logger import logger


class ImageCropService:
    """
    Сервис для вырезания области изображения по координатам Canvas.

    Этот класс не знает ничего про Tkinter, кнопки, Canvas-виджеты
    и GUI-разделы приложения.

    Его задача:
    - получить координаты выделения;
    - пересчитать их в координаты изображения;
    - ограничить crop_box границами изображения;
    - вернуть вырезанную PIL-картинку.
    """

    def crop_from_canvas_selection(self, request: ImageCropRequest) -> ImageCropResult:
        """
        Вырезает область изображения по выделению на Canvas.
        """

        try:
            validation_error = self._validate_request(request)

            if validation_error:
                return ImageCropResult(
                    success=False,
                    error_message=validation_error
                )

            crop_box = self._get_crop_box(request)

            if crop_box is None:
                return ImageCropResult(
                    success=False,
                    error_message="Выделенная область пустая или находится вне изображения."
                )

            cropped_image = request.source_image.crop(crop_box)

            if request.restore_original_orientation and request.angle:
                cropped_image = cropped_image.rotate(
                    -request.angle,
                    expand=True
                )

            return ImageCropResult(
                success=True,
                image=cropped_image,
                crop_box=crop_box
            )

        except Exception:
            logger.exception("Ошибка при вырезании области изображения")

            return ImageCropResult(
                success=False,
                error_message="Внутренняя ошибка при вырезании области."
            )

    def _validate_request(self, request: ImageCropRequest) -> str:
        """
        Проверяет, достаточно ли данных для crop.
        Возвращает текст ошибки или пустую строку.
        """

        if request.source_image is None:
            return "Исходное изображение отсутствует."

        if not request.selection_coords or len(request.selection_coords) != 4:
            return "Некорректные координаты выделения."

        if request.canvas_width <= 0 or request.canvas_height <= 0:
            return "Некорректный размер Canvas."

        if request.displayed_image_width <= 0 or request.displayed_image_height <= 0:
            return "Некорректный размер отображаемого изображения."

        if request.zoom_factor <= 0:
            return "Некорректный масштаб изображения."

        return ""

    def _get_crop_box(self, request: ImageCropRequest):
        """
        Переводит координаты выделения Canvas в crop_box изображения.
        """

        x1, y1, x2, y2 = request.selection_coords

        image_left, image_top = self._get_image_left_top_on_canvas(request)

        crop_x1 = (x1 - image_left) / request.zoom_factor
        crop_y1 = (y1 - image_top) / request.zoom_factor
        crop_x2 = (x2 - image_left) / request.zoom_factor
        crop_y2 = (y2 - image_top) / request.zoom_factor

        crop_x1, crop_x2 = sorted([crop_x1, crop_x2])
        crop_y1, crop_y2 = sorted([crop_y1, crop_y2])

        crop_box = self._clamp_crop_box(
            x1=crop_x1,
            y1=crop_y1,
            x2=crop_x2,
            y2=crop_y2,
            image_width=request.source_image.width,
            image_height=request.source_image.height
        )

        if not self._is_valid_crop_box(crop_box):
            return None

        return crop_box

    def _get_image_left_top_on_canvas(self, request: ImageCropRequest):
        """
        Возвращает координаты левого верхнего угла изображения на Canvas.
        """

        image_left = (
            request.canvas_width / 2
            + request.offset_x
            - request.displayed_image_width / 2
        )

        image_top = (
            request.canvas_height / 2
            + request.offset_y
            - request.displayed_image_height / 2
        )

        return image_left, image_top

    def _clamp_crop_box(self, x1, y1, x2, y2, image_width, image_height):
        """
        Ограничивает crop_box границами изображения.
        """

        x1 = max(0, min(x1, image_width))
        y1 = max(0, min(y1, image_height))
        x2 = max(0, min(x2, image_width))
        y2 = max(0, min(y2, image_height))

        return (
            int(round(x1)),
            int(round(y1)),
            int(round(x2)),
            int(round(y2))
        )

    def _is_valid_crop_box(self, crop_box) -> bool:
        """
        Проверяет, что crop_box не пустой.
        """

        left, top, right, bottom = crop_box
        return left < right and top < bottom