# ./classes/CropOverlay.py

from PyQt6 import QtCore, QtGui
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygonF
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF

class CropOverlay(QWidget):
    def __init__(self, render_frame_widget, main_ui):
        super().__init__(None)

        self.render_frame = render_frame_widget
        self.main_ui = main_ui

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self.is_cropping_active = False
        self.is_dragging = False
        self.crop_orientation = None
        self.current_line_pos = QPoint(0,0)
        self.start_drag_pos = None

        self.arrow_size = 10
        self.arrow_offset = 5

        self.locked_axis = None

        self.hide()

    def update_geometry(self):
        """Positions the overlay to perfectly cover the render_frame widget."""
        global_pos = self.render_frame.mapToGlobal(QPoint(0, 0))
        self.setGeometry(global_pos.x(), global_pos.y(), self.render_frame.width(), self.render_frame.height())

    def start_interaction(self):
        if not self.is_cropping_active:
            self.is_cropping_active = True
            self.update_geometry()
            self.grabKeyboard()
            self.show()
            self.raise_()
            self.activateWindow()
            self.update()

    def stop_interaction(self):
        if self.is_cropping_active:
            self.is_cropping_active = False
            self.is_dragging = False
            self.crop_orientation = None
            self.releaseKeyboard()
            self.hide()
            self.locked_axis = None

    def keyReleaseEvent(self, event):
        """Handles key release even when the overlay has focus."""
        if event.key() == Qt.Key.Key_Control and not event.isAutoRepeat():
            self.stop_interaction()
        super().keyReleaseEvent(event)

    def _get_video_geometry(self) -> QRect:
        """
        Calculates the exact on-screen rectangle of the VISIBLE (cropped) video area.
        """
        try:
            frame_w, frame_h = self.width(), self.height()
            native_w = self.main_ui.videoProps.get('width')
            native_h = self.main_ui.videoProps.get('height')

            if not all([frame_w > 0, frame_h > 0, native_w > 0, native_h > 0]):
                return QRect(0, 0, 0, 0)

            crop_t = self.main_ui.boxFilterCropT.value()
            crop_b = self.main_ui.boxFilterCropB.value()
            crop_l = self.main_ui.boxFilterCropL.value()
            crop_r = self.main_ui.boxFilterCropR.value()

            effective_native_w = native_w - crop_l - crop_r
            effective_native_h = native_h - crop_t - crop_b

            if effective_native_w <= 0 or effective_native_h <= 0:
                return QRect(0, 0, 0, 0)

            aspect_frame = frame_w / frame_h
            aspect_video = effective_native_w / effective_native_h

            if aspect_frame > aspect_video:
                scaled_h = frame_h
                scaled_w = scaled_h * aspect_video
            else:
                scaled_w = frame_w
                scaled_h = scaled_w / aspect_video

            offset_x = (frame_w - scaled_w) / 2
            offset_y = (frame_h - scaled_h) / 2

            return QRect(int(offset_x), int(offset_y), int(scaled_w), int(scaled_h))

        except Exception as e:
            return QRect(0, 0, 0, 0)

    def mouseMoveEvent(self, event):
        if not self.is_cropping_active: return

        video_rect = self._get_video_geometry()
        if not video_rect.isValid() or not video_rect.contains(event.pos()):
            if self.crop_orientation is not None:
                self.crop_orientation = None
                self.update()
            return

        if self.is_dragging:
            self._handle_drag(event.pos())
        else:
            self._handle_hover(event.pos(), video_rect)
        self.update()

    def _handle_hover(self, pos, video_rect):
        """
        Locks the crop-axis on first hover and uses the ORIGINAL video midpoint
        to determine the active crop edge.
        """
        relative_x_screen = pos.x() - video_rect.x()
        relative_y_screen = pos.y() - video_rect.y()

        if self.locked_axis is None:
            distances = {
                'top': relative_y_screen,
                'bottom': video_rect.height() - relative_y_screen,
                'left': relative_x_screen,
                'right': video_rect.width() - relative_x_screen
            }
            initial_orientation = min(distances, key=distances.get)

            if initial_orientation in ['left', 'right']:
                self.locked_axis = 'horizontal'
            else:
                self.locked_axis = 'vertical'

        new_orientation = None
        if self.locked_axis:
            native_w = self.main_ui.videoProps.get('width', 1)
            native_h = self.main_ui.videoProps.get('height', 1)
            crop_t = self.main_ui.boxFilterCropT.value()
            crop_l = self.main_ui.boxFilterCropL.value()
            crop_r = self.main_ui.boxFilterCropR.value()
            crop_b = self.main_ui.boxFilterCropB.value()

            effective_native_w = native_w - crop_l - crop_r
            effective_native_h = native_h - crop_t - crop_b

            if video_rect.width() > 0 and video_rect.height() > 0:
                scale_x = effective_native_w / video_rect.width()
                scale_y = effective_native_h / video_rect.height()
                absolute_native_x = (relative_x_screen * scale_x) + crop_l
                absolute_native_y = (relative_y_screen * scale_y) + crop_t

                if self.locked_axis == 'horizontal':
                    midpoint_x_original = native_w / 2
                    if absolute_native_x < midpoint_x_original:
                        new_orientation = 'left'
                    else:
                        new_orientation = 'right'
                elif self.locked_axis == 'vertical':
                    midpoint_y_original = native_h / 2
                    if absolute_native_y < midpoint_y_original:
                        new_orientation = 'top'
                    else:
                        new_orientation = 'bottom'

        if new_orientation != self.crop_orientation:
            self.crop_orientation = new_orientation

        self.current_line_pos = pos

    def _handle_drag(self, pos):
        self.current_line_pos = pos

    def mousePressEvent(self, event):
        if self.is_cropping_active and self.crop_orientation and event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.start_drag_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if self.is_dragging and event.button() == Qt.MouseButton.LeftButton:
            video_rect = self._get_video_geometry()
            if not video_rect.isValid() or video_rect.width() == 0 or video_rect.height() == 0:
                self.is_dragging = False
                return

            native_w = self.main_ui.videoProps.get('width', 1)
            native_h = self.main_ui.videoProps.get('height', 1)
            crop_t = self.main_ui.boxFilterCropT.value()
            crop_b = self.main_ui.boxFilterCropB.value()
            crop_l = self.main_ui.boxFilterCropL.value()
            crop_r = self.main_ui.boxFilterCropR.value()

            effective_native_w = native_w - crop_l - crop_r
            effective_native_h = native_h - crop_t - crop_b

            if effective_native_w <=0 or effective_native_h <= 0:
                self.is_dragging = False
                return

            scale_x = effective_native_w / video_rect.width()
            scale_y = effective_native_h / video_rect.height()

            clamped_x = max(video_rect.left(), min(event.pos().x(), video_rect.right()))
            clamped_y = max(video_rect.top(), min(event.pos().y(), video_rect.bottom()))

            relative_mouse_x = clamped_x - video_rect.x()
            relative_mouse_y = clamped_y - video_rect.y()
            native_mouse_x = relative_mouse_x * scale_x
            native_mouse_y = relative_mouse_y * scale_y

            if self.crop_orientation == 'top':
                final_val = crop_t + native_mouse_y
                self.main_ui.boxFilterCropT.setValue(max(0, int(round(final_val))))
            elif self.crop_orientation == 'bottom':
                final_val = crop_b + (effective_native_h - native_mouse_y)
                self.main_ui.boxFilterCropB.setValue(max(0, int(round(final_val))))
            elif self.crop_orientation == 'left':
                final_val = crop_l + native_mouse_x
                self.main_ui.boxFilterCropL.setValue(max(0, int(round(final_val))))
            elif self.crop_orientation == 'right':
                final_val = crop_r + (effective_native_w - native_mouse_x)
                self.main_ui.boxFilterCropR.setValue(max(0, int(round(final_val))))

            self.is_dragging = False

    def paintEvent(self, event):
        if not self.is_cropping_active or not self.crop_orientation:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen_color = QColor(255, 255, 0, 200)
        pen = QPen(pen_color, 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        video_rect = self._get_video_geometry()
        if not video_rect.isValid(): return

        clamped_pos_x = max(video_rect.left(), min(self.current_line_pos.x(), video_rect.right()))
        clamped_pos_y = max(video_rect.top(), min(self.current_line_pos.y(), video_rect.bottom()))

        if self.crop_orientation in ['top', 'bottom']:
            painter.drawLine(video_rect.left(), clamped_pos_y, video_rect.right(), clamped_pos_y)
        elif self.crop_orientation in ['left', 'right']:
            painter.drawLine(clamped_pos_x, video_rect.top(), clamped_pos_x, video_rect.bottom())

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(pen_color))

        arrow = QPolygonF()
        ax, ay = self.current_line_pos.x(), self.current_line_pos.y()
        s = self.arrow_size
        o = self.arrow_offset

        if self.crop_orientation == 'top':
            arrow.append(QPointF(ax, clamped_pos_y - o))
            arrow.append(QPointF(ax - s / 2, clamped_pos_y - o - s))
            arrow.append(QPointF(ax + s / 2, clamped_pos_y - o - s))
        elif self.crop_orientation == 'bottom':
            arrow.append(QPointF(ax, clamped_pos_y + o))
            arrow.append(QPointF(ax - s / 2, clamped_pos_y + o + s))
            arrow.append(QPointF(ax + s / 2, clamped_pos_y + o + s))
        elif self.crop_orientation == 'left':
            arrow.append(QPointF(clamped_pos_x - o, ay))
            arrow.append(QPointF(clamped_pos_x - o - s, ay - s / 2))
            arrow.append(QPointF(clamped_pos_x - o - s, ay + s / 2))
        elif self.crop_orientation == 'right':
            arrow.append(QPointF(clamped_pos_x + o, ay))
            arrow.append(QPointF(clamped_pos_x + o + s, ay - s / 2))
            arrow.append(QPointF(clamped_pos_x + o + s, ay + s / 2))

        if not arrow.isEmpty():
            painter.drawPolygon(arrow)
