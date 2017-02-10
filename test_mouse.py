import sys
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets


class Window(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(QtWidgets.QWidget, self).__init__(parent=parent)
        self.pw = pg.PlotWidget()
        self.img = np.random.normal(size=(400, 400))  # random data
        self.imageitem = pg.ImageItem()
        self.imageitem.setImage(self.img)
        self.pw.addItem(self.imageitem)
        self.pw.hideAxis('bottom')
        self.pw.hideAxis('left')
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.pw)
        self.setLayout(self.layout)

        # connect mouseclick signal to custom handler
        self.pw.scene().sigMouseClicked.connect(self.click)

    def click(self, event):
        pos = event.pos()
        print("Event Position in Scene Coordinates: {}".format(pos))

        w = 20
        h = 20
        topleft = QtCore.QPointF(pos.x()-w//2, pos.y()-h//2)
        # create a QRectF  (topleft.x, topleft.y, w, h)
        rect = QtCore.QRectF(topleft.x(), topleft.y(), w, h)
        pen = QtCore.QPen()
        pen.setStyle(QtCore.Qt.SolidLine)
        pen.setWidth(2)
        pen.setBrush(QtCore.Qt.red)

        self.pw.scene().addRect(rect, pen=pen)


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
