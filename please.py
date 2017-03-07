"""PLEASE - The Python Low-energy Electron Analysis SuitE.

Author: Maxwell Grady
Affiliation: University of New Hampshire Department of Physics Pohl group
Version 1.0.0
Date: February, 2017

PLEASE provides a convienient Graphical User Interface for exploration and
analysis of Low Energy Electron Microscopy and Diffraction data sets.
Specifically, emphasis is placed on visualization of Intensity-Voltage data
sets and providing an easy popint and click method for extracting I(V) curves.

Analysis of LEEM-I(V) and LEED-I(V) data sets provides inisght with atomic
scale resolution to the surface structure of a wide array of materials from
semiconductors to metals in bulk or thin film as well as single layer 2D materials.

Usage:
    python please.py
    This will enter the prgram via the main() method found in this file.
"""

# Stdlib and Scientific Stack imports
import os
import sys
import traceback
import yaml
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

# local project imports
import LEEMFUNCTIONS as LF
from colors import Palette
from data import LeedData, LeemData
from experiment import Experiment
from qthreads import WorkerThread
from terminal import MessageConsole

__Version = '1.0.0'
__imgorder = 'row-major'  # pyqtgraph global setting


class ExtendedCrossHair(QtCore.QObject):
    """Set of perpindicular InfiniteLines tracking mouse postion."""

    def __init__(self):
        """."""
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

        self.menubar = self.menuBar()
        self.setupMenu()

        self.setupDockableWidgets()
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockwidget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.bottomdock)

    def setupDockableWidgets(self):
        """Dock control and information widgets to main window."""
        # Leftside button widgets
        self.dockwidget = QtWidgets.QDockWidget(self)

        # setup pushbutton functions
        self.groupbox = QtWidgets.QGroupBox()
        self.buttonboxlayout = QtWidgets.QVBoxLayout()
        self.loadexperimentbutton = QtWidgets.QPushButton("Load Experiment")
        self.loadexperimentbutton.clicked.connect(self.viewer.load_experiment)
        self.outputLEEMbutton = QtWidgets.QPushButton("Output LEEM Data")
        self.outputLEEDbutton = QtWidgets.QPushButton("Output LEED Data")
        self.outputLEEMbutton.clicked.connect(lambda: self.viewer.outputIV(datatype='LEEM'))
        self.outputLEEDbutton.clicked.connect(lambda: self.viewer.outputIV(datatype='LEED'))
        self.quitbutton = QtWidgets.QPushButton("Quit")
        self.quitbutton.clicked.connect(self.quit)
        self.buttonboxlayout.addWidget(self.loadexperimentbutton)
        self.buttonboxlayout.addWidget(self.outputLEEMbutton)
        self.buttonboxlayout.addWidget(self.outputLEEDbutton)
        self.buttonboxlayout.addStretch()
        self.buttonboxlayout.addWidget(self.quitbutton)
        self.groupbox.setLayout(self.buttonboxlayout)

        self.dockwidget.setWidget(self.groupbox)

        # bottom message console
        self.bottomdock = QtWidgets.QDockWidget(self)
        self.console = MessageConsole()
        self.bottomdock.setWidget(self.console)

    def setupMenu(self):
        """Set Menu actions for LEEM and LEED."""
        fileMenu = self.menubar.addMenu("File")
        LEEMMenu = self.menubar.addMenu("LEEM")
        LEEDMenu = self.menubar.addMenu("LEED")

        # File menu
        exitAction = QtWidgets.QAction("Exit", self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(self.quit)
        fileMenu.addAction(exitAction)

        # LEEM menu
        outputLEEMAction = QtWidgets.QAction("Output I(V)", self)
        outputLEEMAction.triggered.connect(lambda: self.viewer.outputIV(datatype='LEEM'))
        LEEMMenu.addAction(outputLEEMAction)

        # LEED menu
        extractAction = QtWidgets.QAction("Extract I(V)", self)
        # extractAction.setShortcut("Ctrl-E")
        extractAction.triggered.connect(self.viewer.processLEEDIV)
        LEEDMenu.addAction(extractAction)

        clearAction = QtWidgets.QAction("Clear I(V)", self)
        clearAction.triggered.connect(self.viewer.clearLEEDIV)
        LEEDMenu.addAction(clearAction)

    @staticmethod
    def quit():
        """."""
        QtWidgets.QApplication.instance().quit()


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
        self.ConfigTab = QtWidgets.QWidget()
        self.initLEEMTab()
        self.initLEEDTab()
        self.initConfigTab()
        self.tabs.addTab(self.LEEMTab, "LEEM-I(V)")
        self.initLEEMEventHooks()
        self.initLEEDEventHooks()
        self.tabs.addTab(self.LEEDTab, "LEED-I(V)")
        self.tabs.addTab(self.ConfigTab, "Config")

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)
        self.show()

    def initData(self):
        """Specific initialization.

        Certain attributes require initialization so that their signals
        can be accessed.
        """
        self.staticLEEMplot = pg.PlotWidget()  # not displayed until User clicks LEEM image

        # container for circular patches indicating locations of User clicks in LEEM image
        self.LEEMcircs = []
        self.LEEMclicks = 0

        # container for QRectF patches to be drawn atop LEEDimage
        self.LEEDrects = []  # stored as tuple (rect, pen)
        self.LEEDclicks = 0
        self.boxrad = 20  # Integration windows are rectangles 2*boxrad x 2*boxrad

        self.threads = []  # container for QThread objects used for outputting files

        self.colors = Palette().color_palette
        self.qcolors = Palette().qcolors
        self.leemdat = LeemData()
        self.leeddat = LeedData()
        self.LEEMselections = []  # store coords of leem clicks in (r,c) format
        self.LEEDselections = []  # store coords of leed clicks in (r,c) format

        self.smoothLEEDoutput = False
        self.smoothLEEMoutput = False
        self.LEEDWindowType = 'flat'
        self.LEEMWindowType = 'flat'
        self.LEEDWindowLen = 4
        self.LEEMWindowLen = 4

        self.exp = None  # overwritten on load with Experiment object
        self.hasdisplayedLEEMdata = False
        self.hasdisplayedLEEDdata = False
        self.curLEEMIndex = 0
        self.curLEEDIndex = 0
        dummydata = np.zeros((10, 10))
        self.LEEMimage = pg.ImageItem(dummydata)  # required for signal hook
        self.LEEDimage = pg.ImageItem(dummydata)
        # self.LEEDimage = pg.ImageItem(dummydata)  # required for signal hook
        self.labelStyle = {'color': '#FFFFFF',
                           'font-size': '16pt'}
        self.boxrad = 20

    def initLEEMTab(self):
        """Setup Layout of LEEM Tab."""
        self.LEEMTabLayout = QtWidgets.QHBoxLayout()
        imvbox = QtWidgets.QVBoxLayout()
        imtitlehbox = QtWidgets.QHBoxLayout()

        self.LEEMimtitle = QtWidgets.QLabel("LEEM Real Space Image")
        imtitlehbox.addStretch()
        imtitlehbox.addWidget(self.LEEMimtitle)
        imtitlehbox.addStretch()
        imvbox.addLayout(imtitlehbox)
        self.LEEMimageplotwidget = pg.PlotWidget()
        self.LEEMimageplotwidget.hideAxis("bottom")
        self.LEEMimageplotwidget.hideAxis("left")
        # self.LEEMimageplotwidget.setTitle("LEEM Real Space Image",
        #                                  size='18pt', color='#FFFFFF')
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

    def initConfigTab(self):
        """Setup Layout of Config Tab."""
        configTabGroupbox = QtWidgets.QGroupBox()
        configtabBottomButtonHBox = QtWidgets.QHBoxLayout()
        configTabGroupButtonBox = QtWidgets.QHBoxLayout()
        configTabVBox = QtWidgets.QVBoxLayout()

        self.quitbut = QtWidgets.QPushButton("Quit", self)
        # self.quitbut.clicked.connect(self.Quit)

        self.setEnergyLEEMBut = QtWidgets.QPushButton("Set LEEM Energy", self)
        # self.setEnergyLEEMBut.clicked.connect(lambda: pass)

        self.setEnergyLEEDBut = QtWidgets.QPushButton("Set LEED Energy", self)
        # self.setEnergyLEEDBut.clicked.connect(lambda: pass)

        self.toggleDebugBut = QtWidgets.QPushButton("Toggle DEBUG mode")
        # self.toggleDebugBut.clicked.connect(lambda: pass)

        self.swapLEEMByteOrderBut = QtWidgets.QPushButton("Swap LEEM Byte Order")
        # self.swapLEEMByteOrderBut.clicked.connect(lambda: pass)

        self.swapLEEDByteOrderBut = QtWidgets.QPushButton("Swap LEED Byte Order")
        # self.swapLEEDByteOrderBut.clicked.connect(lambda: pass)

        buttons = [self.setEnergyLEEMBut, self.setEnergyLEEDBut,
                   self.toggleDebugBut, self.swapLEEDByteOrderBut,
                   self.swapLEEMByteOrderBut]

        configTabGroupButtonBox.addStretch()
        for b in buttons:
            configTabGroupButtonBox.addWidget(b)
            configTabGroupButtonBox.addStretch()
        configTabGroupbox.setLayout(configTabGroupButtonBox)

        configTabVBox.addWidget(configTabGroupbox)
        configTabVBox.addWidget(self.h_line())

        # smooth settings
        smoothLEEDVBox = QtWidgets.QVBoxLayout()
        smoothColumn = QtWidgets.QHBoxLayout()
        # smoothGroupBox = QtWidgets.QGroupBox()

        # LEED
        self.LEEDSettingsLabel = QtWidgets.QLabel("LEED Data Smoothing Settings")
        smoothLEEDVBox.addWidget(self.LEEDSettingsLabel)

        self.smoothLEEDCheckBox = QtWidgets.QCheckBox()
        self.smoothLEEDCheckBox.setText("Enable Smoothing")
        # self.smoothLEEDCheckBox.stateChanged.connect(lambda: pass)
        smoothLEEDVBox.addWidget(self.smoothLEEDCheckBox)

        window_LEED_hbox = QtWidgets.QHBoxLayout()
        self.LEED_window_label = QtWidgets.QLabel("Select Window Type")
        self.smooth_LEED_window_type_menu = QtWidgets.QComboBox()
        self.smooth_LEED_window_type_menu.addItem("Flat")
        self.smooth_LEED_window_type_menu.addItem("Hanning")
        self.smooth_LEED_window_type_menu.addItem("Hamming")
        self.smooth_LEED_window_type_menu.addItem("Bartlett")
        self.smooth_LEED_window_type_menu.addItem("Blackman")
        window_LEED_hbox.addWidget(self.LEED_window_label)
        window_LEED_hbox.addWidget(self.smooth_LEED_window_type_menu)
        smoothLEEDVBox.addLayout(window_LEED_hbox)

        LEED_window_len_box = QtWidgets.QHBoxLayout()
        self.LEED_window_len_label = QtWidgets.QLabel("Enter Window Length [even integer]")
        self.LEED_window_len_entry = QtWidgets.QLineEdit()

        LEED_window_len_box.addWidget(self.LEED_window_len_label)
        LEED_window_len_box.addWidget(self.LEED_window_len_entry)
        smoothLEEDVBox.addLayout(LEED_window_len_box)

        self.apply_settings_LEED_button = QtWidgets.QPushButton("Apply Smoothing Settings", self)
        # self.apply_settings_LEED_button.clicked.connect(lambda: pass)
        smoothLEEDVBox.addWidget(self.apply_settings_LEED_button)

        smoothColumn.addLayout(smoothLEEDVBox)
        smoothColumn.addStretch()
        smoothColumn.addWidget(self.v_line())
        smoothColumn.addStretch()

        # LEEM
        smooth_LEEM_vbox = QtWidgets.QVBoxLayout()
        smooth_group = QtWidgets.QGroupBox()

        self.LEEM_settings_label = QtWidgets.QLabel("LEEM Data Smoothing Settings")
        smooth_LEEM_vbox.addWidget(self.LEEM_settings_label)

        self.smooth_LEEM_checkbox = QtWidgets.QCheckBox()
        self.smooth_LEEM_checkbox.setText("Enable Smoothing")
        # self.smooth_LEEM_checkbox.stateChanged.connect(self.smooth_LEEM_state_change)
        smooth_LEEM_vbox.addWidget(self.smooth_LEEM_checkbox)

        window_LEEM_hbox = QtWidgets.QHBoxLayout()
        self.LEEM_window_label = QtWidgets.QLabel("Select Window Type")
        self.smooth_LEEM_window_type_menu = QtWidgets.QComboBox()
        self.smooth_LEEM_window_type_menu.addItem("Flat")
        self.smooth_LEEM_window_type_menu.addItem("Hanning")
        self.smooth_LEEM_window_type_menu.addItem("Hamming")
        self.smooth_LEEM_window_type_menu.addItem("Bartlett")
        self.smooth_LEEM_window_type_menu.addItem("Blackman")
        window_LEEM_hbox.addWidget(self.LEEM_window_label)
        window_LEEM_hbox.addWidget(self.smooth_LEEM_window_type_menu)
        smooth_LEEM_vbox.addLayout(window_LEEM_hbox)

        LEEM_window_len_box = QtWidgets.QHBoxLayout()
        self.LEEM_window_len_label = QtWidgets.QLabel("Enter Window Length [even integer]")
        self.LEEM_window_len_entry = QtWidgets.QLineEdit()

        LEEM_window_len_box.addWidget(self.LEEM_window_len_label)
        LEEM_window_len_box.addWidget(self.LEEM_window_len_entry)
        smooth_LEEM_vbox.addLayout(LEEM_window_len_box)

        self.apply_settings_LEEM_button = QtWidgets.QPushButton("Apply Smoothing Settings", self)
        # self.apply_settings_LEEM_button.clicked.connect(lambda: pass)
        smooth_LEEM_vbox.addWidget(self.apply_settings_LEEM_button)

        smoothColumn.addLayout(smooth_LEEM_vbox)
        smooth_group.setLayout(smoothColumn)

        configTabVBox.addWidget(smooth_group)
        configTabVBox.addStretch()
        configTabVBox.addStretch()

        configtabBottomButtonHBox.addStretch(1)
        configtabBottomButtonHBox.addWidget(self.quitbut)
        configTabVBox.addLayout(configtabBottomButtonHBox)
        self.ConfigTab.setLayout(configTabVBox)

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
        self.LEEDTitle = QtWidgets.QLabel("Reciprocal Space LEED Image")
        imtitlehbox.addStretch()
        imtitlehbox.addWidget(self.LEEDTitle)
        imtitlehbox.addStretch()
        self.imvbox.addLayout(imtitlehbox)

        self.LEEDimagewidget = pg.PlotWidget()
        self.LEEDimagewidget.hideAxis("bottom")
        self.LEEDimagewidget.hideAxis("left")
        self.LEEDimagewidget.addItem(self.LEEDimage)  # dummy data
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

    def initLEEDEventHooks(self):
        """Setup event hooks for mouse click in LEEDimagewidget."""
        sigmcLEED = self.LEEDimage.scene().sigMouseClicked
        sigmcLEED.connect(self.handleLEEDClick)

    def h_line(self):
        """Convienience to quickly add UI separators."""
        f = QtWidgets.QFrame()
        f.setFrameShape(QtWidgets.QFrame.HLine)
        f.setFrameShadow(QtWidgets.QFrame.Sunken)
        return f

    def v_line(self):
        """Convienience to quickly add UI separators."""
        f = QtWidgets.QFrame()
        f.setFrameShape(QtWidgets.QFrame.VLine)
        f.setFrameShadow(QtWidgets.QFrame.Sunken)
        return f

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
        self.tabs.setCurrentIndex(0)
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
        self.tabs.setCurrentIndex(1)

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

    def outputIV(self, datatype=None):
        """Output current I(V) plots as tab delimited text files.

        :param: datatype- String desginating either 'LEEM' or 'LEED' data to output
        """
        if datatype is None:
            return
        elif datatype == 'LEEM' and self.hasdisplayedLEEMdata and self.LEEMselections:
            outdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                                                options=QtWidgets.QFileDialog.ShowDirsOnly)
            try:
                outdir = outdir[0]
            except IndexError:
                print("Error selecting output file directory.")
                return
            outdir = str(outdir)  # cast from QString to string

            # Query User for output file name
            msg = "Enter name for output file(s)."
            outname = QtWidgets.QFileDialog.getSaveFileName(self, msg)

            try:
                outname = outname[0]
            except IndexError:
                print("Error getting output file name.")
                return
            outname = str(outname)  # cast from QString ot string

            outfile = os.path.join(outdir, outname)
            if self.threads:
                # there are still thread objects in the container
                for thread in self.threads:
                    if not thread.isFinished():
                        print("Error: One or more threads has not finished file I/O ...")
                        return
            self.threads = []
            for idx, tup in enumerate(self.LEEMselections):
                outfile = os.path.join(outdir, outname+str(idx)+'.txt')
                x = tup[1]
                y = tup[0]
                ilist = self.leemdat.dat3d[y, x, :]
                if self.smoothLEEMoutput:
                    ilist = LF.smooth(ilist,
                                      window_len=self.LEEMWindowLen,
                                      window_type=self.LEEMWindowType)
                thread = WorkerThread(task='OUTPUT_TO_TEXT',
                                           elist=self.leemdat.elist,
                                           ilist=ilist,
                                           name=outfile)
                thread.finished.connect(self.output_complete)
                self.threads.append(thread)
                thread.start()

        elif datatype == 'LEED' and self.hasdisplayedLEEDdata and self.LEEDselections:
            # Query User for output directory
            # PyQt5 - This method now returns a tuple - we want only the first element
            outdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                                                options=QtWidgets.QFileDialog.ShowDirsOnly)
            try:
                outdir = outdir[0]
            except IndexError:
                print("Error selecting output file directory.")
                return
            outdir = str(outdir)  # cast from QString to string

            # Query User for output file name
            msg = "Enter name for output file(s)."
            outname = QtWidgets.QFileDialog.getSaveFileName(self, msg)

            try:
                outname = outname[0]
            except IndexError:
                print("Error getting output file name.")
                return
            outname = str(outname)  # cast from QString ot string

            outfile = os.path.join(outdir, outname)
            if self.threads:
                # there are still thread objects in the container
                for thread in self.threads:
                    if not thread.isFinished():
                        print("Error: One or more threads has not finished file I/O ...")
                        return
            self.threads = []
            for idx, tup in enumerate(self.LEEDselections):
                outfile = os.path.join(outdir, outname+str(idx)+'.txt')
                x = int(tup[1])
                y = int(tup[0])
                int_window = self.leeddat.dat3d[y - self.boxrad:y + self.boxrad + 1,
                                                x - self.boxrad:x + self.boxrad + 1, :]
                ilist = [img.sum() for img in np.rollaxis(int_window, 2)]
                if self.smoothLEEDoutput:
                    ilist = LF.smooth(ilist,
                                      window_len=self.LEEDWindowLen,
                                      window_type=self.LEEDWindowType)
                thread = WorkerThread(task='OUTPUT_TO_TEXT',
                                           elist=self.leeddat.elist,
                                           ilist=ilist,
                                           name=outfile)
                thread.finished.connect(self.output_complete)
                self.threads.append(thread)
                thread.start()

    @staticmethod
    @QtCore.pyqtSlot()
    def output_complete():
        """Recieved a finished() SIGNAL from a QThread object."""
        print('File output successfully')

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
                                                         self.curLEEMIndex])
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
        # self.LEEMimageplotwidget.setTitle(title.format(energy),
        #                                  **self.labelStyle)
        self.LEEMimtitle.setText(title.format(energy))
        self.LEEMimageplotwidget.setFocus()

    @QtCore.pyqtSlot()
    def update_LEED_img_after_load(self):
        """Called upon data loading I/O thread emitting finished signal."""
        # if self.hasdisplayedLEEDdata:
        #     self.LEEDimageplotwidget.getPlotItem().clear()
        self.curLEEDIndex = self.leeddat.dat3d.shape[2]//2
        self.LEEDimage = pg.ImageItem(self.leeddat.dat3d[:,
                                                         :,
                                                         self.curLEEDIndex])
        self.LEEDimagewidget.addItem(self.LEEDimage)
        self.LEEDimagewidget.hideAxis('bottom')
        self.LEEDimagewidget.hideAxis('left')

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
        """User click registered in LEEMimage area.

        Handles offset for QRectF drawn for circular patch to ensure that
        the circle is drawn directly below the mouse pointer.

        Appends I(V) curve from clicked location to alternate plot window so
        as to not interfere with the live tracking plot.
        """
        if not self.hasdisplayedLEEMdata:
            return

        # clicking outside image area may cause event.currentItem
        # to be None. This would then raise an error when trying to
        # call event.pos()
        if event.currentItem is None:
            return

        self.LEEMclicks += 1
        if self.LEEMclicks > len(self.qcolors):
            self.LEEMclicks = 1
            if self.staticLEEMplot.isVisible():
                self.staticLEEMplot.clear()
            if self.LEEMcircs:
                for circ in self.LEEMcircs:
                    self.LEEMimageplotwidget.scene().removeItem(circ)
            self.LEEMcircs = []
            self.LEEMselections = []

        pos = event.pos()
        mappedPos = self.LEEMimage.mapFromScene(pos)
        xmapfs = int(mappedPos.x())
        ymapfs = int(mappedPos.y())

        if xmapfs < 0 or \
           xmapfs > self.leemdat.dat3d.shape[1] or \
           ymapfs < 0 or \
           ymapfs > self.leemdat.dat3d.shape[0]:
            return  # discard click events originating outside the image

        if self.currentLEEMPos is not None:
            try:
                # mouse position
                xmp = self.currentLEEMPos[0]
                ymp = self.currentLEEMPos[1]  # x and y in data coordinates
            except IndexError:
                return
        xdata = self.leemdat.elist
        ydata = self.leemdat.dat3d[ymp, xmp, :]

        brush = QtGui.QBrush(self.qcolors[self.LEEMclicks - 1])
        rad = 8
        x = pos.x() - rad/2  # offset for QRectF
        y = pos.y() - rad/2  # offset for QRectF

        circ = self.LEEMimageplotwidget.scene().addEllipse(x, y, rad, rad, brush=brush)
        self.LEEMcircs.append(circ)
        self.LEEMselections.append((ymp, xmp))  # (r,c) format

        pen = pg.mkPen(self.qcolors[self.LEEMclicks - 1], width=2)
        pdi = pg.PlotDataItem(xdata, ydata, pen=pen)
        self.staticLEEMplot.setTitle("LEEM-I(V)")
        self.staticLEEMplot.setLabel('bottom', 'Energy', units='eV', **self.labelStyle)
        self.staticLEEMplot.setLabel('left', 'Intensity', units='a.u.', **self.labelStyle)
        self.staticLEEMplot.addItem(pdi)
        if not self.staticLEEMplot.isVisible():
            self.staticLEEMplot.show()

    def handleLEEMMouseMoved(self, pos):
        """Track mouse movement within LEEM image area and display I(V) from mouse location."""
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
        self.crosshair.curPos = (xmp, ymp)
        self.crosshair.vline.setPos(xmp)
        self.crosshair.hline.setPos(ymp)
        self.currentLEEMPos = (xmp, ymp)  # used for handleLEEMClick()
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

    def handleLEEDClick(self, event):
        """User click registered in LEEDimage area."""
        if not self.hasdisplayedLEEDdata:
            return

        # clicking outside image area may cause event.currentItem
        # to be None. This would then raise an error when trying to
        # call event.pos()
        if event.currentItem is None:
            return

        self.LEEDclicks += 1
        if self.LEEDclicks > len(self.qcolors):
            self.LEEDclicks = 1
            if self.LEEDrects:
                for rect in self.LEEDrects:
                    self.LEEDimagewidget.scene().removeItem(rect)
            self.LEEDrects = []

        pos = event.pos()
        mappedPos = self.LEEMimage.mapFromScene(pos)
        xmapfs = int(mappedPos.x())
        ymapfs = int(mappedPos.y())

        if xmapfs < 0 or \
           xmapfs > self.leeddat.dat3d.shape[1] or \
           ymapfs < 0 or \
           ymapfs > self.leeddat.dat3d.shape[0]:
            return  # discard click events originating outside the image
        xp = pos.x()
        yp = pos.y()
        topleftcorner = QtCore.QPointF(xp - self.boxrad,
                                       yp - self.boxrad)
        rect = QtCore.QRectF(topleftcorner.x(), topleftcorner.y(),
                             2*self.boxrad, 2*self.boxrad)

        pen = QtGui.QPen()
        pen.setStyle(QtCore.Qt.SolidLine)
        pen.setWidth(4)
        # pen.setBrush(QtCore.Qt.red)
        pen.setColor(self.qcolors[self.LEEDclicks - 1])
        self.LEEDimage.scene().addRect(rect, pen=pen)
        self.LEEDrects.append((rect, pen))

    def processLEEDIV(self):
        """Plot I(V) from User selections."""
        if not self.hasdisplayedLEEDdata or not self.LEEDrects:
            return

        for idx, tup in enumerate(self.LEEDrects):
            center = tup[0].center()
            self.LEEDselections.append((center.y(), center.x()))
            topleft = tup[0].topLeft()
            xtl = int(topleft.x())
            ytl = int(topleft.y())
            int_window = self.leeddat.dat3d[ytl:ytl+2*self.boxrad+1,
                                            xtl:xtl+2*self.boxrad+1, :]
            ilist = [img.sum() for img in np.rollaxis(int_window, 2)]
            self.LEEDivplotwidget.plot(self.leeddat.elist, ilist, pen=pg.mkPen(self.qcolors[idx], width=2))

    def clearLEEDIV(self):
        """Triggered by menu action to clear all LEED selections."""
        self.LEEDivplotwidget.clear()
        if self.LEEDrects:
            # items stored as (QRectF, QPen)
            for tup in self.LEEDrects:
                self.LEEDimagewidget.scene().removeItem(tup[0])
            self.LEEDrects = []
            self.LEEDselections = []
            self.LEEDclicks = 0

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
                # self.LEEMimageplotwidget.setTitle(title.format(energy))
                self.LEEMimtitle.setText(title.format(energy))
            elif (event.key() == QtCore.Qt.Key_Right) and \
                 (self.curLEEMIndex <= maxIdx - 1):
                self.curLEEMIndex += 1
                self.showLEEMImage(self.curLEEMIndex)
                title = "Real Space LEEM Image: {} eV"
                energy = LF.filenumber_to_energy(self.leemdat.elist,
                                                 self.curLEEMIndex)
                # self.LEEMimageplotwidget.setTitle(title.format(energy))
                self.LEEMimtitle.setText(title.format(energy))
        # LEED Tab is active
        elif (self.tabs.currentIndex() == 1) and \
             (self.hasdisplayedLEEDdata):
            # handle LEED navigation
            maxIdx = self.leeddat.dat3d.shape[2] - 1
            minIdx = 0
            if (event.key() == QtCore.Qt.Key_Left) and \
               (self.curLEEDIndex >= minIdx + 1):
                self.curLEEDIndex -= 1

                self.showLEEDImage(self.curLEEDIndex)

                title = "Reciprocal Space LEED Image: {} eV"
                energy = LF.filenumber_to_energy(self.leeddat.elist,
                                                 self.curLEEDIndex)
                self.LEEDTitle.setText(title.format(energy))
            elif (event.key() == QtCore.Qt.Key_Right) and \
                 (self.curLEEDIndex <= maxIdx - 1):
                self.curLEEDIndex += 1

                self.showLEEDImage(self.curLEEDIndex)

                title = "Reciprocal Space LEED Image: {} eV"
                energy = LF.filenumber_to_energy(self.leeddat.elist,
                                                 self.curLEEDIndex)
                self.LEEDTitle.setText(title.format(energy))

    def showLEEMImage(self, idx):
        """Display LEEM image from main data array at index=idx."""
        if idx not in range(self.leemdat.dat3d.shape[2] - 1):
            return
        self.LEEMimage.setImage(self.leemdat.dat3d[:, :, idx])

    def showLEEDImage(self, idx):
        """Display LEED image from main data array at index=idx."""
        if idx not in range(self.leeddat.dat3d.shape[2] - 1):
            return
        self.LEEDimage.setImage(self.leeddat.dat3d[:, :, idx])


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
    pg.setConfigOption('imageAxisOrder', __imgorder)

    # print("Creating Please App ...")
    mw = MainWindow(v=__Version)
    mw.showMaximized()

    # This is a big fix for PyQt5 on macOS
    # When running a PyQt5 application that is not bundled into a
    # macOS app bundle; the main menu will not be clickable until you
    # switch to another application then switch back.
    # Thus to fix this we execute a quick applescript from the file
    # cmd.scpt which automates the keystroke "Cmd+Tab" twice to swap
    # applications then immediately swap back and set Focus to the main window.
    if "darwin" in sys.platform:
        cmd = """osascript cmd.scpt"""
        os.system(cmd)
        os.system(cmd)
        mw.viewer.setFocus()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
