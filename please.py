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
from colors import Palette
from data import LeedData, LeemData
from experiment import Experiment
from qthreads import WorkerThread
from PyQt5 import QtCore, QtGui, QtWidgets
from terminal import MessageConsole

__Version = '1.0.0'
__imgorder = 'row-major'  # pyqtgraph global setting


class ExtendedCrossHair(QtCore.QObject):
    """Set of perpindicular InfiniteLines tracking mouse postion."""

    def __init__(self):
        super(ExtendedCrossHair, self).__init__()
        self.hline = pg.InfiniteLine(angle=0, movable=False)
        self.vline = pg.InfiniteLine(angle=90, movable=False)
        self.curPos = (0, 0)  # store (x, y) mouse position


class MainWindow(QtWidgets.QMainWindow):
    """Top level conatiner to wrap Viewer object.

    Provides dockable interface.
    Provides Menubar - to be implemented later
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
        """Dock control and information widgets to main window."""
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


class ImView(QtWidgets.QGraphicsView):
    """Container for images using the QGV-Framework."""

    # signal to send to Viewer object to display iv curve
    # params: int x, int y, int color index
    ivEvent = QtCore.pyqtSignal(int, int, int)

    # signal to send to Viewer object to clear all IV curves
    clearEvent = QtCore.pyqtSignal()

    def __init__(self, colors, parent=None, rad=20):
        """Setup the QGraphicsView Framework; Analogous to Model-View Framework.

        :param: colors - list of QColor objects
        :param: parent - reference to Viewer object
        :param: rad - user configurable setting for integration window radius

        :QGraphicsView: self - contains the viewport to see image data
        :QGraphicsScene: self.scene - container for items to be displayed. Scene
            also handles event routing between view and graphics items.
        :QImage: - self.image - Wrapper class around numpy array. Image is
            cast to uint8 for display purposes. Original image data in numpy
            array remains unchanged to retain accuracy in all calculations.
        :QGraphicsPixmapItem: - self.graphicspixmapitem - GraphicsItem wrapper
            for QPixmap generated from the QImage. Added to Scene to be
            displayed in viewport.
        """
        super(QtWidgets.QGraphicsView, self).__init__(parent=parent)
        self.num_clicks = 0
        self.max_clicks = len(colors)
        self.colors = colors
        self.boxrad = rad  # User configurable
        self.hasloadeddata = False
        # initialize View with random data
        self.originaldata = np.random.randint(0, 65535, size=(600, 600),
                                              dtype=np.uint16)
        # Display data is cast to uint8 to create QImage in 8bit grayscale
        self.displaydata = self.map16to8(self.originaldata)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.image = QtGui.QImage(self.displaydata,
                                  self.displaydata.shape[1],
                                  self.displaydata.shape[0],
                                  self.displaydata.strides[0],
                                  QtGui.QImage.Format_Grayscale8)
        self.graphicspixmapitem = QtWidgets.QGraphicsPixmapItem(
                                         QtGui.QPixmap.fromImage(self.image))
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

    def setImage(self, img):
        """Display numpy array via QGraphicsPixmapItem.

        :param: img - must be a 2D numpy array in 16bit or 8bit format.
        """
        if not isinstance(img, np.ndarray):
            raise ValueError("Image must be a 2d numpy array.")
        if len(img.shape) > 2:
            raise ValueError("Image must be a 2d numpy array.")
        if img.dtype == np.uint16:
            # Need to convert to an 8bit display version
            self.originaldata = img
            self.displaydata = self.map16to8(img)
        elif img.dtype == np.uint8:
            self.originaldata = img
            self.displaydata = img
        else:
            raise ValueError("Image must be 16bit or 8bit Grayscale.")

        self.image = QtGui.QImage(self.displaydata,
                                  self.displaydata.shape[1],
                                  self.displaydata.shape[0],
                                  self.displaydata.strides[0],
                                  QtGui.QImage.Format_Grayscale8)
        self.graphicspixmapitem = QtWidgets.QGraphicsPixmapItem(
                                         QtGui.QPixmap.fromImage(self.image))
        self.scene.addItem(self.graphicspixmapitem)
        self.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
        self.hasloadeddata = True
        self.setScene(self.scene)
        self.graphicspixmapitem.mousePressEvent = self.handleMouseClick

    def handleMouseClick(self, event):
        """Draw QRect centered on event.pos().

        Pass postion back to parent to process I(V) curve and display.
        """
        if not self.hasloadeddata:
            return

        xp = event.pos().x()
        yp = event.pos().y()

        # filter clicks that are too close to edge
        if xp - self.boxrad < 0 or \
           xp + self.boxrad > self.displaydata.shape[1] or \
           yp - self.boxrad < 0 or \
           yp + self.boxrad > self.displaydata.shape[0]:
            print("Too close to Edge.")
            return
        self.num_clicks += 1
        if self.num_clicks > self.max_clicks:
            # reset rects
            self.num_clicks = 1
            for item in self.scene.items():
                if not isinstance(item, QtWidgets.QGraphicsPixmapItem):
                    self.scene.removeItem(item)
            self.clearEvent.emit()
        topleftcorner = QtCore.QPointF(xp - self.boxrad,
                                       yp - self.boxrad)
        rect = QtCore.QRectF(topleftcorner.x(), topleftcorner.y(),
                             2*self.boxrad, 2*self.boxrad)
        pen = QtGui.QPen()
        pen.setStyle(QtCore.Qt.SolidLine)
        pen.setWidth(4)
        # pen.setBrush(QtCore.Qt.red)
        pen.setColor(self.colors[self.num_clicks - 1])
        self.scene.addRect(rect, pen=pen)

        # pass event location to Viewer obect for processing
        self.ivEvent.emit(int(xp), int(yp), self.num_clicks - 1)

    def keyPressEvent(self, event):
        """Navigate LEED images via arrow keys."""
        self.parent().keyPressEvent(event)


class Viewer(QtWidgets.QWidget):
    """Main Container for Viewing LEEM and LEED data."""

    def __init__(self, parent=None):
        """Initialize main LEEM and LEED data stucts.

        Setup Tab structure
        Connect key/mouse event hooks to image plot widgets
        """
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
        self.colors = Palette().color_palette
        self.qcolors = Palette().qcolors
        self.leemdat = LeemData()
        self.leeddat = LeedData()
        self.exp = None  # overwritten on load with Experiment object
        self.hasdisplayedLEEMdata = False
        self.hasdisplayedLEEDdata = False
        self.curLEEMIndex = 0
        self.curLEEDIndex = 0
        dummydata = np.zeros((10, 10))
        self.LEEMimage = pg.ImageItem(dummydata)  # required for signal hook
        # self.LEEDimage = pg.ImageItem(dummydata)  # required for signal hook
        self.labelStyle = {'color': '#FFFFFF',
                           'font-size': '16pt'}
        self.boxrad = 20

    def initLEEMTab(self):
        """Setup Layout of LEEM Tab."""
        self.LEEMTabLayout = QtWidgets.QHBoxLayout()
        imvbox = QtWidgets.QVBoxLayout()
        blanklabel = QtWidgets.QLabel()
        imvbox.addWidget(blanklabel)
        self.LEEMimageplotwidget = pg.PlotWidget()
        self.LEEMimageplotwidget.setTitle("LEEM Real Space Image",
                                          size='18pt', color='#FFFFFF')
        imvbox.addWidget(self.LEEMimageplotwidget)
        self.LEEMTabLayout.addLayout(imvbox)

        ivvbox = QtWidgets.QVBoxLayout()
        titlehbox = QtWidgets.QHBoxLayout()
        self.LEEMIVTitle = QtWidgets.QLabel("LEEM-I(V)")
        titlehbox.addStretch()
        titlehbox.addWidget(self.LEEMIVTitle)
        titlehbox.addStretch()
        ivvbox.addLayout(titlehbox)

        self.LEEMivplotwidget = pg.PlotWidget()
        self.LEEMivplotwidget.setLabel('bottom',
                                       'Energy', units='eV',
                                       **self.labelStyle)
        self.LEEMivplotwidget.setLabel('left',
                                       'Intensity', units='arb units',
                                       **self.labelStyle)

        self.LEEMimageplotwidget.addItem(self.LEEMimage)
        ivvbox.addWidget(self.LEEMivplotwidget)
        self.LEEMTabLayout.addLayout(ivvbox)
        self.LEEMTab.setLayout(self.LEEMTabLayout)

        # ivheight = self.LEEMivplotwidget.frameGeometry().height()
        # ivwidth = self.LEEMivplotwidget.frameGeometry().width()
        # self.LEEMimageplotwidget.setMaximumHeight(ivheight)
        # self.LEEMimageplotwidget.setSizePolicy()

    def initLEEDTab(self):
        """Setup Layout of LEED Tab."""
        self.LEEDTabLayout = QtWidgets.QHBoxLayout()
        """
        self.LEEDimageplotwidget = pg.PlotWidget()
        self.LEEDimageplotwidget.setTitle("LEED Reciprocal Space Image",
                                          size='18pt', color='#FFFFFF')
        self.LEEDTabLayout.addWidget(self.LEEDimageplotwidget)
        """
        self.imvbox = QtWidgets.QVBoxLayout()
        self.ivvbox = QtWidgets.QVBoxLayout()

        imtitlehbox = QtWidgets.QHBoxLayout()
        self.LEEDTitle = QtWidgets.QLabel("Reciprocal Space LEED Image: {} eV".format(0))
        imtitlehbox.addStretch()
        imtitlehbox.addWidget(self.LEEDTitle)
        imtitlehbox.addStretch()
        self.imvbox.addLayout(imtitlehbox)

        self.LEEDimagewidget = ImView(self.qcolors, parent=self, rad=self.boxrad)
        self.LEEDimagewidget.ivEvent.connect(self.processLEEDIV)
        self.LEEDimagewidget.clearEvent.connect(self.clearLEEDIV)
        self.imvbox.addWidget(self.LEEDimagewidget)
        self.LEEDTabLayout.addLayout(self.imvbox)

        ivtitlehbox = QtWidgets.QHBoxLayout()
        ivtitlehbox.addStretch()
        self.LEEDIVTitle = QtWidgets.QLabel("LEED-I(V)")
        ivtitlehbox.addWidget(self.LEEDIVTitle)
        ivtitlehbox.addStretch()
        self.ivvbox.addLayout(ivtitlehbox)
        self.LEEDivplotwidget = pg.PlotWidget()
        self.LEEDivplotwidget.setLabel('bottom',
                                       'Energy', units='eV',
                                       **self.labelStyle)
        self.LEEDivplotwidget.setLabel('left',
                                       'Intensity', units='arb units',
                                       **self.labelStyle)
        self.ivvbox.addWidget(self.LEEDivplotwidget)
        self.LEEDTabLayout.addLayout(self.ivvbox)
        self.LEEDTab.setLayout(self.LEEDTabLayout)

    def initLEEMEventHooks(self):
        """Setup event hooks for mouse click and mouse move.

        Signals beginning with 'sig' are defined by pyqtgraph
        as opposed to being defined in Qt.
        """
        # LEEM #
        # signals
        sigmcLEEM = self.LEEMimage.scene().sigMouseClicked
        sigmmvLEEM = self.LEEMimage.scene().sigMouseMoved

        sigmcLEEM.connect(self.handleLEEMClick)
        sigmmvLEEM.connect(self.handleLEEMMouseMoved)

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
        self.tabs.setCurrentWidget(self.LEEMTab)
        if self.exp.data_type.lower() == 'raw':
            try:
                # use settings from self.sexp
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

    def load_LEED_experiment(self):
        """Load LEED data from settings described by YAML config file."""
        if self.exp is None:
            return
        self.tabs.setCurrentWidget(self.LEEDTab)
        if self.hasdisplayedLEEDdata:
            # self.LEEDimageplotwidget.getPlotItem().clear()
            self.LEEDivplotwidget.getPlotItem().clear()
        if self.exp.data_type.lower() == 'raw':
            try:
                # use settings from self.exp
                self.thread = WorkerThread(task='LOAD_LEED',
                                           path=str(self.exp.path),
                                           imht=self.exp.imh,
                                           imwd=self.exp.imw,
                                           bits=self.exp.bit,
                                           byte=self.exp.byte_order)
                try:
                    self.thread.disconnect()
                except TypeError:
                    # no signal connections - this is OK
                    pass
                self.thread.connectOutputSignal(self.retrieve_LEED_data)
                self.thread.finished.connect(self.update_LEED_img_after_load)
                self.thread.start()
            except ValueError:
                print('Error Loading LEED Data: Please Recheck YAML Settings')
                return

        elif self.exp.data_type.lower() == 'image':
            try:
                self.thread = WorkerThread(task='LOAD_LEED_IMAGES',
                                           ext=self.exp.ext,
                                           path=self.exp.path,
                                           byte=self.exp.byte_order)
                try:
                    self.thread.disconnect()
                except TypeError:
                    # no signals were connected - this is OK
                    pass
                self.thread.connectOutputSignal(self.retrieve_LEED_data)
                self.thread.finished.connect(self.update_LEED_img_after_load)
                self.thread.start()
            except ValueError:
                print('Error Loading LEED Experiment from image files.')
                print('Please Check YAML settings in experiment config file')
                print('Required parameters: data path and data extension.')
                print('Valid data extenstions: \'.tif\', \'.png\', \'.jpg\'')
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
        self.leeddat.dat3d = data
        self.leeddat.dat3ds = data.copy()
        self.leeddat.posMask = np.zeros((self.leeddat.dat3d.shape[0],
                                         self.leeddat.dat3d.shape[1]))

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

    @QtCore.pyqtSlot()
    def update_LEED_img_after_load(self):
        """Called upon data loading I/O thread emitting finished signal."""
        # if self.hasdisplayedLEEDdata:
        #     self.LEEDimageplotwidget.getPlotItem().clear()
        self.curLEEDIndex = self.leeddat.dat3d.shape[2]//2
        self.LEEDimagewidget.setImage(self.leeddat.dat3d[:,
                                                         :,
                                                         self.curLEEDIndex])
        """self.LEEDimage = pg.ImageItem(self.leeddat.dat3d[:,
                                                         ::-1,
                                                         self.curLEEDIndex])

        self.LEEDimageplotwidget.addItem(self.LEEDimage)
        self.LEEDimageplotwidget.hideAxis('bottom')
        self.LEEDimageplotwidget.hideAxis('left')
        """
        self.leeddat.elist = [self.exp.mine]
        while len(self.leeddat.elist) < self.leeddat.dat3d.shape[2]:
            newEnergy = self.leeddat.elist[-1] + self.exp.stepe
            self.leeddat.elist.append(round(newEnergy, 2))
        self.hasdisplayedLEEDdata = True
        title = "Reciprocal Space LEED Image: {} eV"
        energy = LF.filenumber_to_energy(self.leeddat.elist, self.curLEEDIndex)
        self.LEEDTitle.setText(title.format(energy))

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
        """User click in image area.

        There is a discrepancy between the mouse position as recorded
        by the event passed from sigMouseMoved versus the mouse position
        as recorded by sigMouseClicked. The problem appears to be related
        to having a Title set on the plot area. The mouse click coordinates
        are offset in the y direction by roughly 20 units. To remedy this
        one possibility is  to manually offset the y coordinate, but its not
        clear if the number should always be 20 or it it differs by screen size
        or resolution.

        Thus to address the issue, handleMouseMoved records the current mouse
        position and saves to a tuple (x, y) stored as currentLEEMPos. Then
        handleMouseClick extracts the I(V) curve from the stored coordinates
        rather than from the received mouse cooridnates from the click event.
        """
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
        # ymp -= 20  # title interferes with y coordinate

        if xmp < 0 or \
           xmp > self.leemdat.dat3d.shape[1] or \
           ymp < 0 or \
           ymp > self.leemdat.dat3d.shape[0]:
            return  # discard click events originating outside the image

        # xmp = int(event.pos().x())
        # ymp = int(event.pos().y())
        # print("Mouse Click at: {0}, {1}".format(xmp, ymp))
        try:
            xmp = self.currentLEEMPos[0]
            ymp = self.currentLEEMPos[1]
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
        self.currentLEEMPos = (xmp, ymp)
        # print("Mouse moved to: {0}, {1}".format(xmp, ymp))

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
        pen = pg.mkPen(self.qcolors[0], width=2)
        pdi = pg.PlotDataItem(xdata, ydata, pen=pen)
        self.LEEMivplotwidget.getPlotItem().clear()
        self.LEEMivplotwidget.getPlotItem().addItem(pdi, clear=True)

    @QtCore.pyqtSlot(int, int, int)
    def processLEEDIV(self, x, y, idx):
        """Recieve position information from ImView mouseEvent.

        :param: x,y - position of center of mouse click. This defines the center
            of the rectangluar integration window used to generate the I(V)
            curve to be displayed on self.LEEDivplotwidget
        :param: idx - int corresponding to index of color list
        """
        int_window = self.leeddat.dat3d[y - self.boxrad:y + self.boxrad + 1,
                                        x - self.boxrad:x + self.boxrad + 1, :]
        ilist = [img.sum() for img in np.rollaxis(int_window, 2)]
        self.LEEDivplotwidget.plot(self.leeddat.elist,
                                   ilist, pen=pg.mkPen(self.qcolors[idx], width=2))

    @QtCore.pyqtSlot()
    def clearLEEDIV(self):
        """Receive signal from ImView object indicating need to clear IV curves."""
        self.LEEDivplotwidget.clear()

    def keyPressEvent(self, event):
        """Set Arrow keys for navigation."""
        # LEEM Tab is active
        if self.tabs.currentIndex() == 0 and \
           self.hasdisplayedLEEMdata:
            # handle LEEM navigation
            maxIdx = self.leemdat.dat3d.shape[2] - 1
            minIdx = 0
            if (event.key() == QtCore.Qt.Key_Left) and \
               (self.curLEEMIndex >= minIdx + 1):
                self.curLEEMIndex -= 1
                self.showLEEMImage(self.curLEEMIndex)
                title = "Real Space LEEM Image: {} eV"
                energy = LF.filenumber_to_energy(self.leemdat.elist,
                                                 self.curLEEMIndex)
                self.LEEMimageplotwidget.setTitle(title.format(energy))
            elif (event.key() == QtCore.Qt.Key_Right) and \
                 (self.curLEEMIndex <= maxIdx - 1):
                self.curLEEMIndex += 1
                self.showLEEMImage(self.curLEEMIndex)
                title = "Real Space LEEM Image: {} eV"
                energy = LF.filenumber_to_energy(self.leemdat.elist,
                                                 self.curLEEMIndex)
                self.LEEMimageplotwidget.setTitle(title.format(energy))
        # LEED Tab is active
        elif (self.tabs.currentIndex() == 1) and \
             (self.hasdisplayedLEEDdata):
            # handle LEED navigation
            maxIdx = self.leeddat.dat3d.shape[2] - 1
            minIdx = 0
            if (event.key() == QtCore.Qt.Key_Left) and \
               (self.curLEEDIndex >= minIdx + 1):
                self.curLEEDIndex -= 1
                # self.showLEEDImage(self.curLEEDIndex)
                self.LEEDimagewidget.setImage(self.leeddat.dat3d[:,
                                                                 :,
                                                                 self.curLEEDIndex])
                title = "Reciprocal Space LEED Image: {} eV"
                energy = LF.filenumber_to_energy(self.leeddat.elist,
                                                 self.curLEEDIndex)
                self.LEEDTitle.setText(title.format(energy))
            elif (event.key() == QtCore.Qt.Key_Right) and \
                 (self.curLEEDIndex <= maxIdx - 1):
                self.curLEEDIndex += 1
                # self.showLEEDImage(self.curLEEDIndex)
                self.LEEDimagewidget.setImage(self.leeddat.dat3d[:,
                                                                 :,
                                                                 self.curLEEDIndex])
                title = "Reciprocal Space LEED Image: {} eV"
                energy = LF.filenumber_to_energy(self.leeddat.elist,
                                                 self.curLEEDIndex)
                self.LEEDTitle.setText(title.format(energy))

    def showLEEMImage(self, idx):
        """Display LEEM image from main data array at index=idx."""
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
    """Start Qt Event Loop and display main window."""
    # print("Welcome to PLEASE. Installing Custom Exception Handler ...")
    sys.excepthook = custom_exception_handler
    # print("Initializing Qt Event Loop ...")
    app = QtWidgets.QApplication(sys.argv)

    # pyqtgraph settings
    # pg.setConfigOption('imageAxisOrder', __imgorder)

    # print("Creating Please App ...")
    mw = MainWindow(v=__Version)
    mw.showMaximized()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
