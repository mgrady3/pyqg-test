import pyqtgraph as pg

win = pg.GraphicsWindow()
win.addPlot(range(10), row=0, col=0)
win.addPlot(range(10, 20), row=0, col=1)
win.addPlot(range(30, 40), row=1, col=0, colspan=2)
