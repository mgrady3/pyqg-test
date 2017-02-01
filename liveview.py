"""LiveViewer - A program for rapid analysis of LEEM-I(V) data sets.

Author: Maxwell Grady
Affiliation: University of New Hampshire Department of Physics - Pohl group
Version: 0.1.0
Date: January 31, 2017
"""
import os
import sys
import yaml
import LEEMFUNCTIONS as LF
import numpy as np
import pyqtgraph as pg
from experiment import Experiment
from qthreads import WorkerThread
from PyQt5 import QtCore, QtGui, QtWidgets


class CustomStream(QtCore.QObject):
    """Send messages to arbitrary Widget."""

    message = QtCore.pyqtSignal(str)

    def __init__(self):
        super(QtCore.QObject, self).__init__()

    def write(self, message):
        self.message.emit(str(message))

    def flush(self):
        pass


class ExtendedCrossHair(QtCore.QObject):
    """Set of perpindicular InfiniteLines tracking mouse postion."""

    def __init__(self):
        super(ExtendedCrossHair, self).__init__()
        self.hline = pg.InfiniteLine(angle=0, movable=False)
        self.vline = pg.InfiniteLine(angle=90, movable=False)
        self.curPos = (0, 0)  # store (x, y) mouse position


class MainWindow(QtWidgets.QMainWindow):
    """Top level conatiner to wrap LiveViewer object.
    Provides dockable interface.
    """

    def __init__(self):
        super(QtWidgets.QMainWindow, self).__init__()
        self.lv = LiveViewer()
        self.setCentralWidget(self.lv)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.lv.dockwidget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.lv.bottomdock)


class MessageConsole(QtWidgets.QWidget):
    """QTextArea to collect messages rerouted from sys.stdout.
    Will be contained in a DockWidget dockable to the bottom
    of the main window.
    """

    def __init__(self):
        super(QtWidgets.QWidget, self).__init__()
        layout = QtWidgets.QVBoxLayout()
        self.textedit = QtWidgets.QTextEdit()
        layout.addWidget(self.textedit)
        self.setLayout(layout)

        self.stream = CustomStream()
        self.stream.message.connect(self.set_message)

        sys.stdout = self.stream
        sys.stderr = self.stream

        self.show()

    @QtCore.pyqtSlot(str)
    def set_message(self, message):
        """Update QTextEdit with string from sys.stdout or sys.stderr."""
        self.textedit.moveCursor(QtGui.QTextCursor.End)
        self.textedit.insertPlainText(message)

    def closeEvent(self, event):
        """Override closeEvent to reset sys.stdout and sys.stderr."""
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        super(MessageConsole, self).closeEvent(event)


class LiveViewer(QtWidgets.QWidget):
    """LEEM data analysis in real-time: Main Window"""

    def __init__(self, parent=None):
        super(QtWidgets.QWidget, self).__init__()

        self.layout = QtWidgets.QHBoxLayout()

        self.dockwidget = QtWidgets.QDockWidget(self)
        self.groupbox = QtWidgets.QGroupBox()
        self.buttonboxlayout = QtWidgets.QVBoxLayout()
        self.loadexperimentbutton = QtWidgets.QPushButton("Load Experiment")
        self.loadexperimentbutton.clicked.connect(self.load_experiment)
        self.quitbutton = QtWidgets.QPushButton("Quit")
        self.quitbutton.clicked.connect(self.quit)
        self.buttonboxlayout.addWidget(self.loadexperimentbutton)
        self.buttonboxlayout.addStretch()
        self.buttonboxlayout.addWidget(self.quitbutton)
        self.groupbox.setLayout(self.buttonboxlayout)
        self.dockwidget.setWidget(self.groupbox)
        # self.dockwidget.setFloating(True)
        # self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockwidget)

        self.bottomdock = QtWidgets.QDockWidget(self)
        self.console = MessageConsole()
        self.bottomdock.setWidget(self.console)

        self.imageplotwidget = pg.PlotWidget()
        self.imageplotwidget.setTitle("LEEM Real Space Image")
        self.layout.addWidget(self.imageplotwidget)

        self.ivplotwidget = pg.PlotWidget()
        self.ivplotwidget.setLabel('bottom', 'Energy', units='eV')
        self.ivplotwidget.setLabel('left', 'Intensity', units='arb units')
        self.layout.addWidget(self.ivplotwidget)

        self.setLayout(self.layout)

        self.exp = None
        self.hasdisplayeddata = False
        self.setupData()
        # self.load_experiment()
        self.setupEventHooks()
        self.show()

    def setupData(self):
        """Setup dummy data to ensure all arrays are present
        in case of long load time.
        Note: the self.hasdisplayeddata flag should also ensure
        no attempt to access arrays before laoding has completed.
        """
        # dummy data - will get overwritten/resized as needed
        self.dat3d = np.zeros((600, 592, 250))
        self.dat3ds = self.dat3d.copy()
        self.posMask = np.zeros((600, 592))
        self.image = pg.ImageItem(self.dat3d[:, :, 0])
        self.imageplotwidget.addItem(self.image)

    def setupEventHooks(self):
        """ Setup hooks for mouse clicks and mouse movement;
        Key press events tracked directly via overloading KeyPressEvent().
        """
        self.image.scene().sigMouseClicked.connect(self.handleClick)

        sig = self.image.scene().sigMouseMoved
        self.proxy = pg.SignalProxy(signal=sig,
                                    rateLimit=60,
                                    slot=self.handleMouseMoved)

    def load_experiment(self):
        """ Query User for YAML config file to load experiment settings
        Adapted from my other project https://www.github.com/mgrady3/pLEASE
        """

        yamlFilter = "YAML (*.yaml);;YML (*.yml);;All Files (*)"
        homeDir = os.getenv("HOME")
        caption = "Select YAML Experiment Config File"
        fileName = QtGui.QFileDialog.getOpenFileName(parent=None,
                                                     caption=caption,
                                                     directory=homeDir,
                                                     filter=yamlFilter)
        if isinstance(fileName, str):
            config = fileName  # string path to .yaml or .yml config file
        elif isinstance(fileName, tuple):
            try:
                config = fileName[0]
            except IndexError:
                print('No Config file found.')
                print('Please Select a directory with a .yaml file.')
                print('Loading Canceled ...')
                return
        else:
            print('No Config file found.')
            print('Please Select a directory with a .yaml file.')
            print('Loading Canceled ...')
            return
        if config == '':
            print("Loading canceled")
            return

        if self.exp is not None:
            # already loaded an experiment; save old experiment then load new
            self.prev_exp = self.exp

        self.exp = Experiment()
        # path_to_config = os.path.join(new_dir, config)
        self.exp.fromFile(config)
        print("New Data Path loaded from file: {}".format(self.exp.path))
        print("Loaded the following settings:")

        yaml.dump(self.exp.loaded_settings, stream=sys.stdout)
        # self.pp.pprint(exp.loaded_settings)

        if self.exp.exp_type == 'LEEM':
            self.load_LEEM_experiment()

        elif self.exp.exp_type == 'LEED':
            print("Error: Only LEEM data sets can be opened with LiveViewer.")
            return
            # self.load_LEED_experiment()
        else:
            print("Error: Unrecognized Experiment Type in YAML Config file")
            print("Valid Experiment Types for LiveViewer are LEEM")
            print("Please refer to Experiment.yaml for documentation.")
            return

    def load_LEEM_experiment(self):
        """Load LEEM data from settings described by YAML config file."""
        if self.exp is None:
            return
        if self.exp.data_type.lower() == 'raw':
            try:
                self.thread = WorkerThread(task='LOAD_LEEM',
                                           path=str(self.exp.path),
                                           imht=self.exp.imh,
                                           imwd=self.exp.imw,
                                           bits=self.exp.bit,
                                           byte=self.exp.byte_order)
                try:
                    self.thread.disconnect()
                except TypeError:
                    pass  # no signals connected, that's OK, continue as needed
                self.thread.connectOutputSignal(self.retrieve_LEEM_data)
                self.thread.finished.connect(self.update_img_after_load)
                self.thread.start()
            except ValueError:
                print("Error loading LEEM Experiment:")
                print("Please Verify Experiment Config Settings.")
                return

        elif self.exp.data_type.lower() == 'image':
            try:
                self.thread = WorkerThread(task='LOAD_LEEM_IMAGES',
                                           path=self.exp.path,
                                           ext=self.exp.ext)
                try:
                    self.thread.disconnect()
                except TypeError:
                    pass  # no signals connected, that's OK, continue as needed
                self.thread.connectOutputSignal(self.retrieve_LEEM_data)
                self.thread.finished.connect(self.update_img_after_load)
                self.thread.start()
            except ValueError:
                print('Error loading LEEM data from images.')
                print('Please check YAML experiment config file')
                print('Required parameters: path, ext')
                print('Check for valid data path')
                print('Check file extensions: \'.tif\' and \'.png\'.')
                return

    @QtCore.pyqtSlot(np.ndarray)
    def retrieve_LEEM_data(self, data):
        """Grab the 3d numpy array emitted from the data loading I/O thread."""
        self.dat3d = data
        self.posMask = np.zeros((self.dat3d.shape[0], self.dat3d.shape[1]))
        # print("LEEM data recieved from QThread.")
        return

    @QtCore.pyqtSlot()
    def update_img_after_load(self):
        """Called upon data lopading I/O thread emitting finished signal."""
        # print("QThread has finished execution ...")
        if self.hasdisplayeddata:
            self.imageplotwidget.getPlotItem().clear()

        self.currentIndex = self.dat3d.shape[2]//2
        self.image = pg.ImageItem(self.dat3d[:, :, self.currentIndex].T)
        self.imageplotwidget.addItem(self.image)
        self.imageplotwidget.hideAxis('bottom')
        self.imageplotwidget.hideAxis('left')

        # reset new crosshair on load to force crosshair on top of image
        self.crosshair = ExtendedCrossHair()
        self.imageplotwidget.addItem(self.crosshair.hline, ignoreBounds=True)
        self.imageplotwidget.addItem(self.crosshair.vline, ignoreBounds=True)

        self.elist = [self.exp.mine]
        while len(self.elist) < self.dat3d.shape[2]:
            self.elist.append(round(self.elist[-1] + self.exp.stepe, 2))
        self.checkDataSize()
        self.hasdisplayeddata = True

    def checkDataSize(self):
        """Ensure initial array sizes all match."""
        mainshape = self.dat3d.shape
        if self.dat3ds.shape != mainshape:
            self.dat3ds = np.zeros(mainshape)
        if self.posMask.shape != (mainshape[0], mainshape[1]):
            self.posMask = np.zeros((mainshape[0], mainshape[1]))

    def showImage(self, idx):
        """Display image from main data array at index=idx."""
        if idx not in range(self.dat3d.shape[2] - 1):
            return
        self.image.setImage(self.dat3d[:, :, idx].T)

    def handleClick(self, event):
        """User click in image area."""
        if not self.hasdisplayeddata:
            return
        # print("Click registered...")
        pos = event.pos()
        mappedPos = self.image.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())

        if xmp < 0 or \
           xmp > self.dat3d.shape[1] or \
           ymp < 0 or \
           ymp > self.dat3d.shape[0]:
            return  # discard click events originating outside the image

        pw = pg.plot(self.elist, self.dat3d[ymp, xmp, :], title='LEEM-I(V)')
        pw.setLabel('bottom', 'Energy', units='eV')
        pw.setLabel('left', 'Intensity', units='a.u.')
        pw.show()

    def handleMouseMoved(self, pos):
        """Track mouse movement within image area."""
        if not self.hasdisplayeddata:
            return
        try:
            pos = pos[0]
        except IndexError:
            return

        mappedPos = self.image.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())

        if xmp < 0 or \
           xmp > self.dat3d.shape[1] - 1 or \
           ymp < 0 or \
           ymp > self.dat3d.shape[0] - 1:
            return  # discard  movement events originating outside the image

        # update crosshair
        # self.ch.setPos(xmp, ymp)
        self.crosshair.curPos = (xmp, ymp)
        self.crosshair.vline.setPos(xmp)
        self.crosshair.hline.setPos(ymp)

        # update IV plot
        xdata = self.elist

        if self.posMask[ymp, xmp]:
            ydata = self.dat3ds[ymp, xmp, :]
        else:
            ydata = LF.smooth(self.dat3d[ymp, xmp, :],
                              window_len=10,
                              window_type='flat')
            self.dat3ds[ymp, xmp, :] = ydata
            self.posMask[ymp, xmp] = 1
        pdi = pg.PlotDataItem(xdata, ydata, pen='r')
        self.ivplotwidget.getPlotItem().clear()
        self.ivplotwidget.getPlotItem().addItem(pdi, clear=True)

    def keyPressEvent(self, event):
        """Set arrow keys to advance LEEM image."""
        maxIdx = self.dat3d.shape[2] - 1
        minIdx = 0
        if (event.key() == QtCore.Qt.Key_Left) and \
           (self.currentIndex >= minIdx + 1):
            self.currentIndex -= 1
            self.showImage(self.currentIndex)
        elif (event.key() == QtCore.Qt.Key_Right) and \
             (self.currentIndex <= maxIdx - 1):
            self.currentIndex += 1
            self.showImage(self.currentIndex)

    @staticmethod
    def quit():
        QtWidgets.QApplication.instance().quit()


def main():
    app = QtWidgets.QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
