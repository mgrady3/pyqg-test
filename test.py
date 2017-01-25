import numpy as np
import os
import pyqtgraph as pqg
import sys
from PyQt5 import QtCore, QtWidgets


class CrossHair(QtWidgets.QGraphicsItem):
    def __init__(self):
        super(QtWidgets.QGraphicsItem, self).__init__()
        self.setFlag(self.ItemIgnoresTransformations)

    def paint(self, p, *args):
        p.setPen(pqg.mkPen('y'))
        p.drawLine(-10, 0, 10, 0)
        p.drawLine(0, -10, 0, 10)

    def boundingRect(self):
        return QtCore.QRectF(-10, -10, 20, 20)


class TestWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TestWindow, self).__init__(parent)
        self.layout = QtWidgets.QHBoxLayout()
        # ImageView is too bulky
        # self.imageplot = pqg.ImageView()
        self.implotwidget = pqg.PlotWidget()
        self.implotwidget.setTitle("LEEM Real Space Image")
        self.layout.addWidget(self.implotwidget)
        self.IVpltw = pqg.PlotWidget()
        self.IVpltw.setLabel('bottom', 'Energy', units='eV')
        self.IVpltw.setLabel('left', 'Intensity', units='a.u.')
        self.layout.addWidget(self.IVpltw)
        # self.IVpltw.show()
        # handle realtime mouse movement
        self.setLayout(self.layout)
        self.initData()
        self.loadData()
        self.createPlot()

    def initData(self):
        with open("datapath.txt", 'r') as f:
            self.datapath = f.readlines()[0].split('\n')[0]

    def loadData(self):
        files = [name for name in os.listdir(self.datapath) if name.endswith('.dat')]
        data = []
        for fl in files:
            with open(os.path.join(self.datapath, fl), 'rb') as f:
                hdln = len(f.read()) - 2 * 600 * 592
                f.seek(0)
                shape = (600, 592)  # (r, c)
                data.append(np.fromstring(f.read()[hdln:], '<u2').reshape(shape))
        # main 3d numpy array
        self.dat3d = np.dstack(data)
        # generate energy data for plotting
        self.elist = [-9.9]
        while len(self.elist) < self.dat3d.shape[2]:
            self.elist.append(round(self.elist[-1] + 0.1, 2))

        # self.imageplot.setImage(self.dat3d[:, :, middle].T)

    def createPlot(self):

        middle = int(self.dat3d.shape[2] / 2)
        self.img = pqg.ImageItem(self.dat3d[:, :, middle].T)
        self.implotwidget.addItem(self.img)
        self.implotwidget.hideAxis('left')
        self.implotwidget.hideAxis('bottom')

        self.ch = CrossHair()
        self.implotwidget.addItem(self.ch)
        # handle mouse clicks
        self.img.scene().sigMouseClicked.connect(self.handleClick)

        self.img.scene().sigMouseMoved.connect(self.handleMove)

    def handleClick(self, event):
        """ sigMouseClicked emits a QEvent (or subclass thereof)"""

        # filter for events inside image:
        pos = event.pos()
        mappedPos = self.img.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())

        if xmp < 0 or \
           xmp > self.dat3d.shape[1] or \
           ymp < 0 or \
           ymp > self.dat3d.shape[0]:
            return  # discard click events originating outside the image

        pw = pqg.plot(self.elist, self.dat3d[ymp, xmp, :], title="LEEM-I(V)")
        pw.setLabel('bottom', 'Energy', units='eV')
        pw.setLabel('left', 'Intensity', units='a.u.')
        pw.show()

    def handleMove(self, pos):
        """ sigMouseMoved emits the position of the mouse"""

        mappedPos = self.img.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())

        if xmp < 0 or \
           xmp > self.dat3d.shape[1] - 1 or \
           ymp < 0 or \
           ymp > self.dat3d.shape[0] - 1:
            return  # discard  movement events originating outside the image

        # update crosshair
        self.ch.setPos(xmp, ymp)

        # update IV plot
        xdata = self.elist
        ydata = smooth(self.dat3d[ymp, xmp, :])
        pdi = pqg.PlotDataItem(xdata, ydata, pen='r')
        self.IVpltw.getPlotItem().clear()
        self.IVpltw.getPlotItem().addItem(pdi, clear=True)
        # self.IVpltw.show()

def smooth(inpt, window_len=10, window_type='flat'):
    """
    Smoothing function based on Scipy Cookbook recipe for data smoothing
    Uses predefined window function (selectable) to smooth a 1D data set
    Computes the convolution with a normalized window
    :param inpt: input list or 1d array
    :param window_len: even integer size of window
    :param window_type: string for type of window function
    :return otpt: 1d numpy array of smoothed data with same length as inpt
    """
    if not (window_len % 2 == 0):
        window_len += 1
        print('Window length supplied is odd - using next highest integer: {}.'.format(window_len))

    if window_len <= 3:
        print('Error in data smoothing - please select a larger window length')
        return

    # window_type = 'hanning'
    if not window_type in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        print('Error - Invalid window_type')
        return

    # Generate two arguments to pass into numpy.convolve()
    # s is the input signal doctored with reflections of the input at the beginning and end
    # this serves to remove noise in the smoothing method
    # w is the window matrix based on pre-defined window functions or unit matrix for flat window

    s = np.r_[inpt[window_len-1:0:-1], inpt, inpt[-1:-window_len:-1]]
    # w = eval('np.'+window_type+'(window_len)')
    if window_type == 'flat':  # moving average
        w = np.ones(window_len, 'd')
    else:
        w = eval('np.'+window_type+'(window_len)')

    # create smoothed data via numpy.convolve using the normalized input window matrix
    otpt = np.convolve(w/w.sum(), s, mode='valid')

    # format otpt to be same size as inpt and return
    return otpt[int(window_len/2-1):-int(window_len/2)]


def main():
    app = QtWidgets.QApplication(sys.argv)
    tw = TestWindow()
    tw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
