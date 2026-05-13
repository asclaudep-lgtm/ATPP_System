"""Графическое дерево БОМ — QGraphicsScene с узлами-изделиями и связями."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGraphicsView,
                              QGraphicsScene, QGraphicsItem,
                              QGraphicsRectItem, QGraphicsTextItem,
                              QGraphicsLineItem, QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QPainterPath)

from modules.bom import get_bom_tree, BOMNode


class BOMNodeItem(QGraphicsRectItem):
    """Графический узел БОМ."""

    COLORS = {
        'Изделие': '#1976d2',
        'Сборочная единица': '#388e3c',
        'ДСЕ': '#f9a825',
        'Деталь': '#7b1fa2',
    }

    def __init__(self, node: BOMNode, x=0, y=0, parent=None):
        w, h = 180, 60
        super().__init__(QRectF(x, y, w, h), parent)
        self.bom_node = node
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
                     True)

        color = QColor(self.COLORS.get(node.level, '#666'))
        self.setPen(QPen(color.darker(130), 2))
        self.setBrush(QBrush(color.lighter(160)))

        # Текст
        self.text = QGraphicsTextItem(self)
        self.text.setPlainText(
            f'{node.product_designation}\n{node.product_name}\n'
            f'×{node.quantity} {node.level}')
        self.text.setFont(QFont('sans', 8))
        self.text.setPos(x + 4, y + 4)

    def center(self) -> QPointF:
        r = self.rect()
        return self.mapToScene(r.center())


class BOMConnection(QGraphicsLineItem):
    """Линия связи между узлами БОМ."""

    def __init__(self, parent_item: BOMNodeItem,
                 child_item: BOMNodeItem):
        super().__init__()
        self.parent_item = parent_item
        self.child_item = child_item
        self.setPen(QPen(QColor('#999'), 2))
        self.setZValue(-1)
        self._update_line()

    def _update_line(self):
        p1 = self.parent_item.center()
        p2 = self.child_item.center()
        self.setLine(p1.x(), p1.y(), p2.x(), p2.y())


class BOMGraphWidget(QWidget):
    """Графический просмотрщик БОМ."""

    def __init__(self, db_manager, product_id=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.product_id = product_id
        self._connections: list[BOMConnection] = []
        self._init_ui()
        if product_id:
            self.load_bom(product_id)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        fit_btn = QPushButton('По размеру')
        fit_btn.clicked.connect(self._fit_view)
        ctrl.addWidget(fit_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(self.view)

    def load_bom(self, product_id: int = None):
        if product_id is None:
            product_id = self.product_id
        if product_id is None:
            return
        self.product_id = product_id
        self.scene.clear()
        self._connections.clear()

        with self.db_manager.get_session() as s:
            tree = get_bom_tree(s, product_id=product_id)

        if not tree:
            return

        x_spacing = 220
        y_spacing = 100
        self._layout_tree(tree, 0, 0, x_spacing, y_spacing)
        self._fit_view()

    def _layout_tree(self, nodes, depth, start_y, x_spacing, y_spacing):
        """Рекурсивно разместить узлы БОМ на сцене."""
        x = depth * x_spacing
        y = start_y
        items = []

        for node in nodes:
            item = BOMNodeItem(node, x, y)
            self.scene.addItem(item)
            items.append((item, node))
            y += 80

        # Рекурсивно для детей
        current_y = start_y
        for item, node in items:
            if node.children:
                child_y = current_y
                self._layout_tree(node.children, depth + 1,
                                  child_y, x_spacing, y_spacing)
                # Соединения к детям
                for conn_item in self.scene.items():
                    if (isinstance(conn_item, BOMNodeItem) and
                        conn_item.bom_node.id in
                            {c.id for c in node.children}):
                        conn = BOMConnection(item, conn_item)
                        self.scene.addItem(conn)
                        self._connections.append(conn)
            current_y += 80

    def _fit_view(self):
        self.view.fitInView(self.scene.sceneRect().adjusted(-20, -20, 20, 20),
                            Qt.AspectRatioMode.KeepAspectRatio)
