import sys
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets


class View(QtWidgets.QGraphicsView):
    def __init__(self):
        super(QtWidgets.QGraphicsView, self).__init__()
        self.closed = False
        self.scene = QtWidgets.QGraphicsScene(self)
        # Original 16bit data
        self.testdata = np.random.randint(0, 65535, size=(600, 600),
                                          dtype=np.uint16)
        # downsampled data for display only
        self.displaydata = self.map16to8(self.testdata)

        self.image = QtGui.QImage(self.displaydata,
                                  self.displaydata.shape[1],
                                  self.displaydata.shape[0],
                                  self.displaydata.strides[0],
                                  QtGui.QImage.Format_Grayscale8)
        self.pixmap = QtGui.QPixmap.fromImage(self.image)
        self.graphicspixmapitem = QtWidgets.QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.graphicspixmapitem)
        self.setScene(self.scene)

        self.graphicspixmapitem.mousePressEvent = self.handleMouseClick

    @staticmethod
    def map16to8(img, lower=None, upper=None):
        """Safely map 16-bit img to 8-bit img for display."""
        if lower is not None and not (0 <= lower < 65535):
            raise ValueError("Lower bound must be in [0, 65535].")
        if upper is not None and not(0 <= upper < 2**16):
            raise ValueError("Upper bound must be in [0, 65535].")
        if lower is None:
            lower = np.amin(img)
        if upper is None:
            upper = np.amax(img)
        if lower >= upper:
            raise ValueError("Lower bound must be < Upper bound.")

        lut = np.concatenate([
            np.zeros(lower, dtype=np.uint16),
            np.linspace(0, 255, upper - lower).astype(np.uint16),
            np.ones(2**16 - upper, dtype=np.uint16) * 255
            ])
        return lut[img].astype(np.uint8)

    def handleMouseClick(self, event):
        pos = event.pos()
        print("Mouse Clicked at X={}, Y={}".format(pos.x(), pos.y()))

        # Extract pixel value from Original Data not downsampled data
        print("Pixel value = {}".format(self.testdata[int(pos.y()),
                                                      int(pos.x())]))



def main():
    app = QtWidgets.QApplication(sys.argv)
    gv = View()
    gv.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
