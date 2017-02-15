import sys
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets


class ImWin(QtWidgets.QLabel):
    def __init__(self):
        super(QtWidgets.QLabel, self).__init__()
        self.path = '/Users/Maxwell/Desktop/test.png'
        self.pm = QtGui.QPixmap(self.path)
        self.im = self.pm.toImage()
        self.setPixmap(self.pm)
        self.mousePressEvent = self.handleClick

    def handleClick(self, event):
        x = event.x()
        y = event.y()
        print("Coordinates: X = {0}, Y = {1}".format(x, y))
        colors = QtGui.QColor(self.im.pixel(x, y)).getRgb()
        #  print(colors)
        r = colors[0]
        g = colors[1]
        b = colors[2]
        a = colors[3]
        print("Pixel Value: r={0}, g={1}, b={2}, a={3}".format(r, g, b, a))


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = ImWin()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
