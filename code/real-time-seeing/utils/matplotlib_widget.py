
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

class MatplotlibWidget(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=6.4, height=3.6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = [
            self.fig.add_subplot(211),       # Graph 1
            self.fig.add_subplot(212)        # Graph 2
        ]
        self.fig.tight_layout()

        FigureCanvasQTAgg.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvasQTAgg.setSizePolicy(self,
                QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        FigureCanvasQTAgg.updateGeometry(self)

    def plot(self, data, position=0):
        self.axes[position].clear()
        self.axes[position].plot(data, 'r-')
        # self.axes[position].set_title('PyQt Matplotlib Example')
        self.draw()
        # self.fig.tight_layout()
        # plt.pause(1e-3)
