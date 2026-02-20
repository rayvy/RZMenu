# RZMenu/qt_editor/systems/smart_snap.py
from PySide6 import QtCore
import math

class SmartSnapSystem:
    ADHESION_THRESHOLD = 8.0   # Пикселей для жесткого прилипания к углам
    ALIGNMENT_THRESHOLD = 10.0 # Пикселей для выравнивания осей

    def __init__(self):
        pass

    @staticmethod
    def get_targets(scene, exclude_items):
        """Сбор геометрии всех объектов сцены, кроме перемещаемых."""
        targets = []
        from ..widgets.viewport import RZElementItem
        
        for item in scene.items():
            if isinstance(item, RZElementItem) and item.isVisible() and item not in exclude_items:
                # Нормализуем Rect, чтобы ширина/высота всегда были положительными
                r = item.rect().normalized()
                # Use scenePos() for true Global Coordinates
                pos = item.scenePos()
                # Абсолютные координаты в сцене
                scene_rect = QtCore.QRectF(pos.x() + r.x(), pos.y() + r.y(), r.width(), r.height())
                targets.append(scene_rect)
        return targets

    def solve_snap(self, current_rect, target_rects, grid_size, modes):
        """
        Главный решатель снаппинга.
        modes: dict {'adhesion': bool, 'alignment': bool, 'grid': bool}
        Возвращает: (final_x, final_y, guides_list)
        """
        # Исходные координаты (куда мышка притащила элемент)
        res_x = current_rect.x()
        res_y = current_rect.y()
        guides = []

        # 1. ADHESION (Прилипание к точкам) - Высший приоритет
        # Работает если включен Ctrl (Grid) или Ctrl+Alt, 
        # но по твоему ТЗ: Ctrl = Grid + Adhesion.
        if modes.get('adhesion'):
            adhesion_pos = self._check_adhesion(current_rect, target_rects)
            if adhesion_pos:
                # Если нашли прилипание, возвращаем его и игнорируем всё остальное
                return adhesion_pos.x(), adhesion_pos.y(), []

        # Если прилипания не случилось, рассчитываем оси независимо
        
        # 2. ALIGNMENT (Осевое выравнивание)
        align_x = None
        align_y = None
        
        if modes.get('alignment'):
            align_x, guide_x = self._check_axis_alignment(current_rect, target_rects, 'X')
            align_y, guide_y = self._check_axis_alignment(current_rect, target_rects, 'Y')
            
            if guide_x: guides.append(guide_x)
            if guide_y: guides.append(guide_y)

        # 3. GRID (Сетка) - Низший приоритет (фоллбек)
        if modes.get('grid'):
            # Применяем сетку, только если ось не была выровнена Alignment-ом
            if align_x is None:
                align_x = round(res_x / grid_size) * grid_size
            if align_y is None:
                align_y = round(res_y / grid_size) * grid_size

        # Применяем результаты (если были найдены, иначе оставляем оригинал)
        if align_x is not None: res_x = align_x
        if align_y is not None: res_y = align_y

        return res_x, res_y, guides

    def _check_adhesion(self, src, targets):
        """
        Проверяет углы и центр. Если расстояние < 5px, возвращает QPointF новой позиции Origin.
        """
        # Точки интереса исходного объекта (относительно его Origin)
        # Мы храним смещение точки от Origin (0,0), чтобы потом восстановить Origin
        # Например: TopLeft -> offset(0,0), Center -> offset(w/2, h/2)
        w, h = src.width(), src.height()
        src_points = [
            (src.topLeft(), QtCore.QPointF(0, 0)),
            (src.topRight(), QtCore.QPointF(w, 0)),
            (src.bottomLeft(), QtCore.QPointF(0, h)),
            (src.bottomRight(), QtCore.QPointF(w, h)),
            (src.center(), QtCore.QPointF(w/2, h/2))
        ]

        best_dist = self.ADHESION_THRESHOLD
        best_origin = None

        for tgt in targets:
            tgt_points = [
                tgt.topLeft(), tgt.topRight(), 
                tgt.bottomLeft(), tgt.bottomRight(), 
                tgt.center()
            ]
            
            for s_pt, s_offset in src_points:
                for t_pt in tgt_points:
                    # Manhattan length быстрее и для снапа удобнее
                    # dist = (s_pt - t_pt).manhattanLength()
                    # Но для точного радиуса лучше Евклидова
                    dist = math.hypot(s_pt.x() - t_pt.x(), s_pt.y() - t_pt.y())
                    
                    if dist < best_dist:
                        best_dist = dist
                        # Вычисляем, где должен быть Origin, чтобы s_pt совпала с t_pt
                        # NewOrigin = TargetPoint - SourceOffset
                        best_origin = t_pt - s_offset

        return best_origin

    def _check_axis_alignment(self, src, targets, axis):
        """
        Проверяет выравнивание граней (L, R, C для X; T, B, C для Y).
        Возвращает (new_origin_coord, QLineF_guide).
        """
        best_val = None
        best_guide = None
        min_dist = self.ALIGNMENT_THRESHOLD

        # Определяем координаты граней исходника и смещения от Origin
        if axis == 'X':
            # Val, Offset from Origin
            src_edges = [
                (src.left(), 0), 
                (src.right(), src.width()), 
                (src.center().x(), src.width()/2)
            ]
            range_min, range_max = src.top(), src.bottom()
        else:
            src_edges = [
                (src.top(), 0), 
                (src.bottom(), src.height()), 
                (src.center().y(), src.height()/2)
            ]
            range_min, range_max = src.left(), src.right()

        for tgt in targets:
            if axis == 'X':
                tgt_edges = [tgt.left(), tgt.right(), tgt.center().x()]
                tgt_min, tgt_max = tgt.top(), tgt.bottom()
            else:
                tgt_edges = [tgt.top(), tgt.bottom(), tgt.center().y()]
                tgt_min, tgt_max = tgt.left(), tgt.right()

            for s_val, s_offset in src_edges:
                for t_val in tgt_edges:
                    dist = abs(s_val - t_val)
                    if dist < min_dist:
                        min_dist = dist
                        # New Origin Coord = Target Edge - Offset
                        best_val = t_val - s_offset
                        
                        # Создаем направляющую линию
                        # Объединяем диапазоны, чтобы линия покрывала оба объекта
                        draw_min = min(range_min, tgt_min) - 20
                        draw_max = max(range_max, tgt_max) + 20
                        
                        if axis == 'X':
                            best_guide = QtCore.QLineF(t_val, draw_min, t_val, draw_max)
                        else:
                            best_guide = QtCore.QLineF(draw_min, t_val, draw_max, t_val)

        return best_val, best_guide

    # Оставляем старый метод для Resize Gizmo (он работает хорошо, не ломаем)
    def calculate_edge_snap(self, value, orientation, target_rects):
        best_val = None
        best_guide = None
        min_dist = self.ALIGNMENT_THRESHOLD

        for target in target_rects:
            points = []
            if orientation == 0: # X Coords
                points = [target.left(), target.right(), target.center().x()]
                g_min, g_max = target.top(), target.bottom()
            else: # Y Coords
                points = [target.top(), target.bottom(), target.center().y()]
                g_min, g_max = target.left(), target.right()

            for pt in points:
                dist = abs(value - pt)
                if dist < min_dist:
                    min_dist = dist
                    best_val = pt
                    if orientation == 0:
                        best_guide = QtCore.QLineF(pt, g_min - 500, pt, g_max + 500)
                    else:
                        best_guide = QtCore.QLineF(g_min - 500, pt, g_max + 500, pt)

        return best_val, best_guide