import sys
import numpy as np
from PyQt5 import QtGui, QtWidgets


class View(QtWidgets.QGraphicsView):
    def __init__(self):
        super(QtWidgets.QGraphicsView, self).__init__()
        self.scene = QtWidgets.QGraphicsScene(self)
        self.testdata = np.random.randint(0, 255, size=(600, 600),
                                          dtype=np.uint8)
        self.image = QtGui.QImage(self.testdata,
                                  self.testdata.shape[1],
                                  self.testdata.shape[0],
                                  self.testdata.strides[0],
                                  QtGui.QImage.Format_Grayscale8)
        self.pixmap = QtGui.QPixmap.fromImage(self.image)
        self.graphicspixmapitem = QtWidgets.QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.graphicspixmapitem)
        self.setScene(self.scene)


def main():
    app = QtWidgets.QApplication(sys.argv)
    gv = View()
    gv.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
