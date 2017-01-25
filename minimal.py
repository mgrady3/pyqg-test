import numpy as np
import os
import pyqtgraph as pqg
import sys
from PyQt5 import QtWidgets


class TestWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TestWindow, self).__init__(parent)
        self.layout = QtWidgets.QVBoxLayout()
        self.imageplot = pqg.ImageView()
        self.layout.addWidget(self.imageplot)
        self.setLayout(self.layout)
        self.data = None
        self.loadData()
        self.show()

    def loadData(self):
        self.data = np.random.rand(640, 480)
        self.imageplot.setImage(self.data)


def main():
    app = QtWidgets.QApplication(sys.argv)
    tw = TestWindow()
    tw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
