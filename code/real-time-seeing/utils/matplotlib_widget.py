
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

class MatplotlibWidget(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=5, dpi=100):
        # super(MatplotlibWidget, self).__init__(parent)

        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)

        FigureCanvasQTAgg.__init__(self, fig)
        self.setParent(parent)

        FigureCanvasQTAgg.setSizePolicy(self,
                QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        FigureCanvasQTAgg.updateGeometry(self)

    def plot(self, data):
        print(data)
        self.axes.plot(data, 'r-')
        self.axes.set_title('PyQt Matplotlib Example')
        self.draw()
        # plt.pause(1e-3)
