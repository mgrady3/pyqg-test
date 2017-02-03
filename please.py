"""PLEASE - The Python Low-energy Electron Analysis SuitE.

Author: Maxwell Grady
Affiliation: University of New Hampshire Department of Physics Pohl group
Version 1.0.0
Date: February, 2017
"""

import os
import sys
import traceback
import yaml
import LEEMFUNCTIONS as LF
import numpy as np
import pyqtgraph as pg
from data import LeedData, LeemData
from experiment import Experiment
from qthreads import WorkerThread
from PyQt5 import QtCore, QtGui, QtWidgets

__Version = '1.0.0'


class CustomStream(QtCore.QObject):
    """Send messages to arbitrary widget."""

    message = QtCore.pyqtSignal(str)

    def __init__(self):
        super(QtCore.QObject, self).__init__()

    def write(self, message):
        """Assume message can be cast to string."""
        self.message.emit(str(message))

    def flush(self):
        """Overloaded for stream interface."""
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

    def __init__(self, v=None):
        """Parameter v tracks the current PLEASE version number."""
        super(QtWidgets.QMainWindow, self).__init__()
        self.setWindowTitle("PLEASE v. {}".format(v))
        self.viewer = Viewer()
        self.setCentralWidget(self.viewer)
        self.setupDockableWidgets()
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockwidget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.bottomdock)

    def setupDockableWidgets(self):
        """Various Widgets which can be Docked to MainWindow."""
        # Leftside button widgets
        self.dockwidget = QtWidgets.QDockWidget(self)
        self.groupbox = QtWidgets.QGroupBox()
        self.buttonboxlayout = QtWidgets.QVBoxLayout()
        self.loadexperimentbutton = QtWidgets.QPushButton("Load Experiment")
        self.loadexperimentbutton.clicked.connect(self.viewer.load_experiment)
        self.quitbutton = QtWidgets.QPushButton("Quit")
        self.quitbutton.clicked.connect(self.quit)
        self.buttonboxlayout.addWidget(self.loadexperimentbutton)
        self.buttonboxlayout.addStretch()
        self.buttonboxlayout.addWidget(self.quitbutton)
        self.groupbox.setLayout(self.buttonboxlayout)
        self.dockwidget.setWidget(self.groupbox)

        # bottom message console
        self.bottomdock = QtWidgets.QDockWidget(self)
        self.console = MessageConsole()
        self.bottomdock.setWidget(self.console)

    @staticmethod
    def quit():
        QtWidgets.QApplication.instance().quit()


class MessageConsole(QtWidgets.QWidget):
    """QTextArea to collect messages rerouted from sys.stdout.
    Will be contained in a DockWidget dockable to the bottom
    of the main window.
    """

    def __init__(self):
        super(QtWidgets.QWidget, self).__init__()

        layout = QtWidgets.QVBoxLayout()
        self.textedit = QtWidgets.QTextEdit()
        self.textedit.setReadOnly(True)
        layout.addWidget(self.textedit)
        self.setLayout(layout)

        self.stream = CustomStream()
        self.stream.message.connect(self.set_message)

        sys.stdout = self.stream
        sys.stderr = self.stream
        self.welcome()
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

    @staticmethod
    def welcome():
        print("Welcome to PLEASE!")
        print("Use the button bar to the left to load data for analysis.")


class Viewer(QtWidgets.QWidget):
    """Main Container for Viewing LEEM and LEED data."""

    def __init__(self, parent=None):
        super(QtWidgets.QWidget, self).__init__()
        self.initData()
        self.layout = QtWidgets.QVBoxLayout()

        self.tabs = QtWidgets.QTabWidget()
        self.LEEMTab = QtWidgets.QWidget()
        self.LEEDTab = QtWidgets.QWidget()
        self.initLEEMTab()
        self.initLEEDTab()
        self.tabs.addTab(self.LEEMTab, "LEEM-I(V)")
        self.initLEEMEventHooks()
        self.tabs.addTab(self.LEEDTab, "LEED-I(V)")

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)
        self.show()

    def initData(self):
        """Specific initialization.

        Certain attributes require initialization so that their signals
        can be accessed.
        """
        self.leemdat = LeemData()
        self.leeddat = LeedData()
        self.exp = None  # overwritten on load with Experiment object
        self.hasdisplayedLEEMdata = False
        self.curLEEMIndex = 0
        self.curLEEDIndex = 0
        dummydata = np.zeros((10, 10))
        self.LEEMimage = pg.ImageItem(dummydata)  # required for signal hook
        self.LEEDimage = pg.ImageItem(dummydata)  # required for signal hook
        self.labelStyle = {'color': '#FFFFFF',
                           'font-size': '16pt'}

    def initLEEMTab(self):
        """Setup Layout of LEEM Tab."""
        self.LEEMTabLayout = QtWidgets.QHBoxLayout()
        self.LEEMimageplotwidget = pg.PlotWidget()
        self.LEEMimageplotwidget.setTitle("LEEM Real Space Image",
                                          size='18pt', color='#FFFFFF')
        self.LEEMTabLayout.addWidget(self.LEEMimageplotwidget)
        self.LEEMivplotwidget = pg.PlotWidget()
        self.LEEMivplotwidget.setLabel('bottom',
                                       'Energy', units='eV',
                                       **self.labelStyle)
        self.LEEMivplotwidget.setLabel('left',
                                       'Intensity', units='arb units',
                                       **self.labelStyle)

        self.LEEMimageplotwidget.addItem(self.LEEMimage)
        self.LEEMTabLayout.addWidget(self.LEEMivplotwidget)
        self.LEEMTab.setLayout(self.LEEMTabLayout)

    def initLEEDTab(self):
        """Setup Layout of LEED Tab."""
        self.LEEDTabLayout = QtWidgets.QHBoxLayout()
        self.LEEDimageplotwidget = pg.PlotWidget()
        self.LEEDimageplotwidget.setTitle("LEED Reciprocal Space Image",
                                          size='18pt', color='#FFFFFF')
        self.LEEDTabLayout.addWidget(self.LEEDimageplotwidget)
        self.LEEDivplotwidget = pg.PlotWidget()
        self.LEEDivplotwidget.setLabel('bottom',
                                       'Energy', units='eV',
                                       **self.labelStyle)
        self.LEEDivplotwidget.setLabel('left',
                                       'Intensity', units='arb units',
                                       **self.labelStyle)
        self.LEEDimageplotwidget.addItem(self.LEEDimage)
        self.LEEDTabLayout.addWidget(self.LEEDivplotwidget)
        self.LEEDTab.setLayout(self.LEEDTabLayout)

    def initLEEMEventHooks(self):
        """Setup event hooks for mouse click and mouse move.

        Signals beginning with 'sig' are defined by pyqtgraph
        as opposed to being defined in Qt.
        """
        # signals
        sigmc = self.LEEMimage.scene().sigMouseClicked
        sigmmv = self.LEEMimage.scene().sigMouseMoved

        sigmc.connect(self.handleLEEMClick)
        sigmmv.connect(self.handleLEEMMouseMoved)

    def load_experiment(self):
        """Query User for YAML config file to load experiment settings.
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

        if self.exp.exp_type == 'LEEM':
            self.load_LEEM_experiment()
        elif self.exp.exp_type == 'LEED':
            self.load_LEED_experiment()
        else:
            print("Error: Unrecognized Experiment Type in YAML Config file")
            print("Valid Experiment Types for LiveViewer are LEEM, LEED")
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
                self.thread.finished.connect(self.update_LEEM_img_after_load)
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
                self.thread.finished.connect(self.update_LEEM_img_after_load)
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
        self.leemdat.dat3d = data
        self.leemdat.dat3ds = data.copy()
        self.leemdat.posMask = np.zeros((self.leemdat.dat3d.shape[0],
                                         self.leemdat.dat3d.shape[1]))
        # print("LEEM data recieved from QThread.")
        return

    @QtCore.pyqtSlot(np.ndarray)
    def retrieve_LEED_data(self, data):
        """Grab the numpy array emitted from the data loading I/O thread."""
        pass

    @QtCore.pyqtSlot()
    def update_LEEM_img_after_load(self):
        """Called upon data loading I/O thread emitting finished signal."""
        # print("QThread has finished execution ...")
        if self.hasdisplayedLEEMdata:
            self.LEEMimageplotwidget.getPlotItem().clear()

        self.curLEEMIndex = self.leemdat.dat3d.shape[2]//2
        self.LEEMimage = pg.ImageItem(self.leemdat.dat3d[:,
                                                         :,
                                                         self.curLEEMIndex].T)
        self.LEEMimageplotwidget.addItem(self.LEEMimage)
        self.LEEMimageplotwidget.hideAxis('bottom')
        self.LEEMimageplotwidget.hideAxis('left')

        # reset new crosshair on load to force crosshair on top of image
        self.crosshair = ExtendedCrossHair()
        self.LEEMimageplotwidget.addItem(self.crosshair.hline,
                                         ignoreBounds=True)
        self.LEEMimageplotwidget.addItem(self.crosshair.vline,
                                         ignoreBounds=True)

        self.leemdat.elist = [self.exp.mine]
        while len(self.leemdat.elist) < self.leemdat.dat3d.shape[2]:
            nextEnergy = self.leemdat.elist[-1] + self.exp.stepe
            self.leemdat.elist.append(round(nextEnergy, 2))
        self.checkDataSize(datatype="LEEM")
        self.hasdisplayedLEEMdata = True
        title = "Real Space LEEM Image: {} eV"
        energy = LF.filenumber_to_energy(self.leemdat.elist, self.curLEEMIndex)
        self.LEEMimageplotwidget.setTitle(title.format(energy),
                                          **self.labelStyle)
        self.LEEMimageplotwidget.setFocus()

    def checkDataSize(self, datatype=None):
        """Ensure helper array sizes all match main data array size."""
        if datatype is None:
            return
        elif datatype == 'LEEM':
            mainshape = self.leemdat.dat3d.shape
            if self.leemdat.dat3ds.shape != mainshape:
                self.leemdat.dat3ds = np.zeros(mainshape)
            if self.leemdat.posMask.shape != (mainshape[0], mainshape[1]):
                self.leemdat.posMask = np.zeros((mainshape[0], mainshape[1]))
        elif datatype == 'LEED':
            pass
        else:
            return

    def handleLEEMClick(self, event):
        """User click in image area."""
        if not self.hasdisplayedLEEMdata:
            return

        # clicking outside image area may cause event.currentItem
        # to be None. This would then raise an error when trying to
        # call event.pos()
        if event.currentItem is None:
            return

        pos = event.pos()
        mappedPos = self.LEEMimage.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())

        if xmp < 0 or \
           xmp > self.leemdat.dat3d.shape[1] or \
           ymp < 0 or \
           ymp > self.leemdat.dat3d.shape[0]:
            return  # discard click events originating outside the image
        try:
            pw = pg.plot(self.leemdat.elist,
                         self.leemdat.dat3d[ymp, xmp, :],
                         title='LEEM-I(V)')
        except IndexError:
            return
        pw.setLabel('bottom', 'Energy', units='eV', **self.labelStyle)
        pw.setLabel('left', 'Intensity', units='a.u.', **self.labelStyle)
        pw.show()

    def handleLEEMMouseMoved(self, pos):
        """Track mouse movement within LEEM image area."""
        if not self.hasdisplayedLEEMdata:
            return
        if isinstance(pos, tuple):
            try:
                # if pos a tuple containing a QPointF object
                pos = pos[0]
            except IndexError:
                # empty tuple
                return
        # else pos is a QPointF object which can be mapped directly

        mappedPos = self.LEEMimage.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())
        if xmp < 0 or \
           xmp > self.leemdat.dat3d.shape[1] - 1 or \
           ymp < 0 or \
           ymp > self.leemdat.dat3d.shape[0] - 1:
            return  # discard  movement events originating outside the image

        # update crosshair
        # self.ch.setPos(xmp, ymp)
        self.crosshair.curPos = (xmp, ymp)
        self.crosshair.vline.setPos(xmp)
        self.crosshair.hline.setPos(ymp)

        # update IV plot
        xdata = self.leemdat.elist

        if self.leemdat.posMask[ymp, xmp]:
            ydata = self.leemdat.dat3ds[ymp, xmp, :]
        else:
            ydata = LF.smooth(self.leemdat.dat3d[ymp, xmp, :],
                              window_len=10,
                              window_type='flat')
            self.leemdat.dat3ds[ymp, xmp, :] = ydata
            self.leemdat.posMask[ymp, xmp] = 1
        pdi = pg.PlotDataItem(xdata, ydata, pen='r')
        self.LEEMivplotwidget.getPlotItem().clear()
        self.LEEMivplotwidget.getPlotItem().addItem(pdi, clear=True)

    def showLEEMImage(self, idx):
        """Display image from main data array at index=idx."""
        if idx not in range(self.leemdat.dat3d.shape[2] - 1):
            return
        self.LEEMimage.setImage(self.leemdat.dat3d[:, :, idx].T)


def custom_exception_handler(exc_type, exc_value, exc_traceback):
    """Allow printing of unhandled exceptions instead of Qt Abort."""
    if issubclass(exc_type, KeyboardInterrupt):
        QtWidgets.QApplication.instance().quit()

    print("".join(traceback.format_exception(exc_type,
                                             exc_value,
                                             exc_traceback)))


def main():
    # print("Welcome to PLEASE. Installing Custom Exception Handler ...")
    sys.excepthook = custom_exception_handler
    # print("Initializing Qt Event Loop ...")
    app = QtWidgets.QApplication(sys.argv)
    # print("Creating Please App ...")
    mw = MainWindow(v=__Version)
    mw.showMaximized()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()