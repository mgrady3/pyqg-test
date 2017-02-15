import numpy as np
import os
import pyqtgraph as pqg
# from smoothn import smoothn
import sys
from PyQt5 import QtCore, QtWidgets


class ExtendedCrossHair(QtCore.QObject):
    def __init__(self):
        super(QtCore.QObject, self).__init__()
        self.vline = pqg.InfiniteLine(angle=90, movable=False)
        self.hline = pqg.InfiniteLine(angle=0, movable=False)
        self.curPos = (0, 0)


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
        self.setupEventHooks()
        # print(time.time() - ts)

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
        # self.dat3ds = np.apply_along_axis(smooth, 2, self.dat3d)
        # self.dat3dsn = smoothn(self.dat3d, axis=2)
        # generate energy data for plotting
        self.elist = [-9.9]
        while len(self.elist) < self.dat3d.shape[2]:
            self.elist.append(round(self.elist[-1] + 0.1, 2))
        self.dat3ds = self.dat3d.copy()
        self.posMask = np.zeros((600, 592))

        # self.imageplot.setImage(self.dat3d[:, :, middle].T)

    def showImage(self, idx):

        if idx not in range(self.dat3d.shape[2] - 1):
            return
        self.img.setImage(self.dat3d[:, :, idx].T)

    def createPlot(self):

        middle = int(self.dat3d.shape[2] / 2)
        self.img = pqg.ImageItem(self.dat3d[:, :, middle].T)
        self.currentIndex = middle
        self.implotwidget.addItem(self.img)
        self.implotwidget.hideAxis('left')
        self.implotwidget.hideAxis('bottom')

        # self.ch = CrossHair()
        self.ch = ExtendedCrossHair()
        self.implotwidget.addItem(self.ch.hline, ignoreBounds=True)
        self.implotwidget.addItem(self.ch.vline, ignoreBounds=True)

    def setupEventHooks(self):
        """
        setup hooks for mouse clicks and mouse movement
        key press events get tracked directly via overlaoding KeyPressEvent()
        """
        # handle mouse clicks
        self.img.scene().sigMouseClicked.connect(self.handleClick)
        # handle mouse movement
        # Use signalproxy for ratelimiting
        sig = self.img.scene().sigMouseMoved
        self.mvProxy = pqg.SignalProxy(signal=sig, rateLimit=60, slot=self.handleMove)

    def handleClick(self, event):
        """
        Generate static I(V) plot in separate window on click
        sigMouseClicked emits a QEvent (or subclass thereof)
        """

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
        """
        Use ExtendedCrossHair to track mouseposition.
        Continuously update I(V) plot with I(V) from mouse positon.
        sigMouseMoved emits the position of the mouse, which
        SignalProxy wraps into tuple.
        """
        try:
            pos = pos[0]
        except IndexError:
            return

        mappedPos = self.img.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())

        if xmp < 0 or \
           xmp > self.dat3d.shape[1] - 1 or \
           ymp < 0 or \
           ymp > self.dat3d.shape[0] - 1:
            return  # discard  movement events originating outside the image

        # update crosshair
        # self.ch.setPos(xmp, ymp)
        self.ch.curPos = (xmp, ymp)
        self.ch.vline.setPos(xmp)
        self.ch.hline.setPos(ymp)

        # update IV plot
        xdata = self.elist

        if self.posMask[ymp, xmp]:
            ydata = self.dat3ds[ymp, xmp, :]
        else:
            ydata = smooth(self.dat3d[ymp, xmp, :])
            self.dat3ds[ymp, xmp, :] = ydata
            self.posMask[ymp, xmp] = 1
        pdi = pqg.PlotDataItem(xdata, ydata, pen='r')
        self.IVpltw.getPlotItem().clear()
        self.IVpltw.getPlotItem().addItem(pdi, clear=True)
        # self.IVpltw.show()

    def keyPressEvent(self, event):
        """ Scroll through images in self.dat3d using arrow keys"""
        maxIdx = self.dat3d.shape[2] - 1
        minIdx = 0
        if (event.key() == QtCore.Qt.Key_Left) and (self.currentIndex >= minIdx + 1):
            self.currentIndex -= 1
            self.showImage(self.currentIndex)
        elif (event.key() == QtCore.Qt.Key_Right) and (self.currentIndex <= maxIdx - 1):
            self.currentIndex += 1
            self.showImage(self.currentIndex)


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

    s = np.r_[inpt[window_len -1:0:-1], inpt, inpt[-1:-window_len:-1]]
    # w = eval('np.'+window_type+'(window_len)')
    if window_type == 'flat':  # moving average
        w = np.ones(window_len, 'd')
    else:
        w = eval('np.' + window_type + '(window_len)')

    # create smoothed data via numpy.convolve using the normalized input window matrix
    otpt = np.convolve(w / w.sum(), s, mode='valid')

    # format otpt to be same size as inpt and return
    return otpt[int(window_len / 2 -1):-int(window_len / 2)]


def main():
    app = QtWidgets.QApplication(sys.argv)
    tw = TestWindow()
    tw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
