import os
import sys
import yaml
import LEEMFUNCTIONS as LF
import numpy as np
import pyqtgraph as pg
from experiment import Experiment
from qthreads import WorkerThread
from PyQt5 import QtCore, QtGui, QtWidgets


class ExtendedCrossHair(QtCore.QObject):
    """ set of perpindicular InfiniteLines tracking mouse postion """
    def __init__(self):
        super(ExtendedCrossHair, self).__init__()
        self.hline = pg.InfiniteLine(angle=0, movable=False)
        self.vline = pg.InfiniteLine(angle=90, movable=False)
        self.curPos = (0, 0)  # store (x, y) mouse position


class LiveViewer(QtWidgets.QWidget):
    """ LEEM data analysis in real-time """
    def __init__(self, parent=None):
        super(QtWidgets.QWidget, self).__init__()

        self.layout = QtWidgets.QHBoxLayout()

        self.imageplotwidget = pg.PlotWidget()
        self.imageplotwidget.setTitle("LEEM Real Space Image")
        self.layout.addWidget(self.imageplotwidget)

        self.ivplotwidget = pg.PlotWidget()
        self.ivplotwidget.setLabel('bottom', 'Energy', units='eV')
        self.ivplotwidget.setLabel('left', 'Intensity', units='arb units')
        self.layout.addWidget(self.ivplotwidget)

        self.setLayout(self.layout)

        self.crosshair = ExtendedCrossHair()

        self.exp = None
        self.setupData()
        self.load_experiment()
        self.setupEventHooks()
        self.show()

    def setupData(self):
        self.dat3d = np.zeros((600,592,250))  # dummy data - will get overwritten on load
        self.dat3ds = self.dat3d.copy()  # will get filled with smoothed data as needed
        self.posMask = np.zeros((600,592))  # will get resized on load
        self.image = pg.ImageItem(self.dat3d[:,:, 0])
        self.imageplotwidget.addItem(self.image)

    def setupEventHooks(self):
        """
        setup hooks for mouse clicks and mouse movement
        key press events get tracked directly via overlaoding KeyPressEvent()
        """
        self.image.scene().sigMouseClicked.connect(self.handleClick)

        sig = self.image.scene().sigMouseMoved
        self.proxy = pg.SignalProxy(signal=sig, rateLimit=60, slot=self.handleMouseMoved)

    def load_experiment(self):
        """
        :return none
        """
        # On Windows 10 there seems to be an error where files are not displayed in the FileDialog
        # The user may select a directory they know to contain a .yaml file but no files are shown
        # one possible work around may be to use options=QtGui.QFileDialog.DontUseNativeDialog
        # but this changes the entire look and feel of the window. Thus is not an ideal solution

        yamlFilter = "YAML (*.yaml);;YML (*.yml);;All Files (*)"
        homeDir = os.getenv("HOME")
        fileName = QtGui.QFileDialog.getOpenFileName(parent=None,
                                                    caption="Select YAML Experiment Config File",
                                                    directory=homeDir,
                                                    filter=yamlFilter)
        if isinstance(fileName, str):
            config = fileName  # string path to .yaml or .yml config file
        elif isinstance(fileName, tuple):
            try:
                config = fileName[0]
            except IndexError:
                print('No Config file found. Please Select a directory with a .yaml file')
                print('Loading Canceled ...')
                return
        else:
            print('No Config file found. Please Select a directory with a .yaml file')
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
        # yaml.dump(self.exp.loaded_settings, stream=self.message_console.stream)
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
            print("Please refer to Experiment.yaml for documentation on valid YAML config files")
            return

    def load_LEEM_experiment(self):
        """ Load LEEM data from settings described by YAML config file """
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
                    pass  # no signals were connected, that is OK, continue as needed
                self.thread.connectOutputSignal(self.retrieve_LEEM_data)
                self.thread.finished.connect(self.update_img_after_load)
                self.thread.start()
            except ValueError:
                print("Error loading LEEM Experiment: Please Verify Experiment Config Settings")
                return

        elif self.exp.data_type.lower() == 'image':
            try:
                self.thread = WorkerThread(task='LOAD_LEEM_IMAGES',
                                           path=self.exp.path,
                                           ext=self.exp.ext)
                try:
                    self.thread.disconnect()
                except TypeError:
                    pass  # no signals were connected, that is OK, continue as needed
                self.thread.connectOutputSignal(self.retrieve_LEEM_data)
                self.thread.finished.connect(self.update_img_after_load)
                self.thread.start()
            except ValueError:
                print('Error loading LEEM data from images. Please check YAML experiment config file')
                print('Required parameters to load images from YAML config: path, ext')
                print('Check for valid data path and valid file extensions: \'.tif\' and \'.png\'.')
                return

    @QtCore.pyqtSlot(np.ndarray)
    def retrieve_LEEM_data(self, data):
        self.dat3d = data
        self.posMask = np.zeros((self.dat3d.shape[0], self.dat3d.shape[1]))
        print("LEEM data recieved from QThread.")
        return

    def update_img_after_load(self):
        print("QThread has finished execution ...")
        self.currentIndex = self.dat3d.shape[2]//2
        self.image = pg.ImageItem(self.dat3d[:, :, self.currentIndex].T)
        self.imageplotwidget.addItem(self.image)
        self.imageplotwidget.hideAxis('bottom')
        self.imageplotwidget.hideAxis('left')
        self.imageplotwidget.addItem(self.crosshair.hline, ignoreBounds=True)
        self.imageplotwidget.addItem(self.crosshair.vline, ignoreBounds=True)

        self.elist = [self.exp.mine]
        while len(self.elist) < self.dat3d.shape[2]:
            self.elist.append(round(self.elist[-1] + self.exp.stepe, 2))

    def showImage(self, idx):
        """ Display image from main data array at index=idx """
        if idx not in range(self.dat3d.shape[2] - 1):
            return
        self.imageplotwidget.setImage(self.dat3d[:, :, idx])

    def handleClick(self, event):
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
            ydata = LF.smooth(self.dat3d[ymp, xmp, :], window_len=10, window_type='flat')
            self.dat3ds[ymp, xmp, :] = ydata
            self.posMask[ymp, xmp] = 1
        pdi = pg.PlotDataItem(xdata, ydata, pen='r')
        self.ivplotwidget.getPlotItem().clear()
        self.ivplotwidget.getPlotItem().addItem(pdi, clear=True)


def main():
    app = QtWidgets.QApplication(sys.argv)
    lv = LiveViewer()
    lv.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
