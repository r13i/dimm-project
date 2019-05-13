from collections import deque
import numpy as np
import cv2
import matplotlib.pyplot as plt

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPalette, QPixmap
from PyQt5.QtWidgets import (QWidget, QGridLayout, QAction, QApplication, QPushButton, QLabel,
    QMainWindow, QMenu, QMessageBox, QSizePolicy)

from qimage2ndarray import array2qimage, gray2qimage


# Dev only ########################################################
import platform
if platform.system() == 'Linux':
    from PyQt5.uic import compileUi
    with open("./code/real-time-seeing/ui/ui_mainwindow.py", "wt") as ui_file:
        compileUi("./code/real-time-seeing/ui/layout.ui", ui_file)
    from ui.ui_mainwindow import Ui_MainWindow
else:
    from ui.ui_mainwindow import Ui_MainWindow
    import tis.tisgrabber as IC
    import ctypes as C

    lWidth          = C.c_long()
    lHeight         = C.c_long()
    iBitsPerPixel   = C.c_int()
    COLORFORMAT     = C.c_int()





from utils.fake_stars import FakeStars
from utils.matplotlib_widget import MatplotlibWidget



class SeeingMonitor(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(SeeingMonitor, self).__init__()
        self.setupUi(self)

        # TIS (The Imaging Source) CCD Camera
        if platform.system() != 'Linux':
            self.Camera = IC.TIS_CAM()
            # self.initCameraDroplist()

        self.matplotlib_widget = MatplotlibWidget(parent=self.seeing_graph, width=7, height=1)

        self.button_start.clicked.connect(self.startLiveCamera)
        self.button_settings.clicked.connect(self.showSettings)
        self.button_simulation.clicked.connect(self.startSimulation)

        # Timer for acquiring images at regular intervals
        self.acquisition_timer = QTimer(parent=self.centralwidget)


    def startLiveCamera(self):

        # Disable other functionalities
        self.button_simulation.setEnabled(False)


        self.Camera.ShowDeviceSelectionDialog()
        if self.Camera.IsDevValid() != 1:
            raise Exception("Unable to open camera device !")

        print('Starting live stream ...')
        self.Camera.StartLive(0)
        # self.Camera.StartLive(1)

        self.acquisition_timer.timeout.connect(self._updateLiveCamera)
        self.acquisition_timer.start(20)


    def showSettings(self):
        print("Is Device Valid ? ", self.Camera.IsDevValid())
        if not self.Camera.IsDevValid():
            QMessageBox.warning(self, "Camera Selection Error",
                "Please select a camera first by clicking on the button <strong>Start</strong>")
            return -1

        self.Camera.ShowPropertyDialog()


    def _updateLiveCamera(self):

        # Capturing a frame
        self.Camera.SnapImage()
        frame = self.Camera.GetImage()
        frame = cv2.resize(frame, (640, 480))

        print('>>>>>> Image captured')

        qImage = array2qimage(frame)
        self.stars_capture.setPixmap(QPixmap(qImage))



    def startSimulation(self):

        # Disable other functionalities
        self.button_start.setEnabled(False)
        self.button_settings.setEnabled(False)

        # Define constants for the simulation
        self.THRESH         = 127       # Pixels below this value will be set to 0

        DIAMETER_GDIMM      = 0.06      # 6 cm
        L                   = 0.03      # 30 cm : The distance between two DIMM apertures
        b                   = L / DIAMETER_GDIMM
        K_L = 0.364 * (1 - 0.532 * np.power(b, -1 / 3) - 0.024 * np.power(b, -7 / 3))
        K_T = 0.364 * (1 - 0.798 * np.power(b, -1 / 3) - 0.018 * np.power(b, -7 / 3))

        LAMBDA              = 0.0005    # 500 micro-meters
        Z                   = 45        # Zenithal angle (in degrees)

        # Calculate values to make process faster
        self.A = 0.98 * np.power(np.cos(Z), 0.6)
        self.B = DIAMETER_GDIMM / (LAMBDA * K_L)
        # self.C = DIAMETER_GDIMM / (LAMBDA * K_T)
        self.C = abs(DIAMETER_GDIMM / (LAMBDA * K_T))

        # Storing the Delta X and Y in an array to calculate the Standard Deviation
        self.arr_delta_x = deque(maxlen=100)
        self.arr_delta_y = deque(maxlen=100)

        self.arr_epsilon_x = deque(maxlen=10)
        self.arr_epsilon_y = deque(maxlen=10)


        # Generating fake images of DIMM star (One single star that is split by the DIMM)
        self.starsGenerator = FakeStars()

        # WIDTH, HEIGHT = self.starsGenerator.width, self.starsGenerator.height
        # self.resize(int(round(float(HEIGHT) * 10. / 3.)), int(round(float(WIDTH) * 10. / 3.)))

        self.acquisition_timer.timeout.connect(self._updateSimulation)
        self.acquisition_timer.start(500)


    def _updateSimulation(self):

        frame = self.starsGenerator.generate()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        _, thresholded = cv2.threshold(gray, self.THRESH, 255, cv2.THRESH_TOZERO)

        # _, contours, hierarchy = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        _, contours, hierarchy = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        # cv2.drawContours(frame, contours, -1, (0,0,255), 2)

        moments_star_1 = cv2.moments(contours[0])
        moments_star_2 = cv2.moments(contours[1])

        cX_star1 = int(moments_star_1["m10"] / moments_star_1["m00"])
        cY_star1 = int(moments_star_1["m01"] / moments_star_1["m00"])

        cX_star2 = int(moments_star_2["m10"] / moments_star_2["m00"]) # + frame.shape[1] // 2
        cY_star2 = int(moments_star_2["m01"] / moments_star_2["m00"])

        if self.enable_seeing.isChecked():
            # Calcul Seeing ######################################################################
            delta_x = abs(cX_star2 - cX_star1)
            delta_y = abs(cY_star2 - cY_star1)

            self.arr_delta_x.append(delta_x)
            self.arr_delta_y.append(delta_y)

            sigma_x = np.std(self.arr_delta_x)
            sigma_y = np.std(self.arr_delta_y)


            # Seeing
            epsilon_x = self.A * np.power(self.B * sigma_x, 0.2)
            epsilon_y = self.A * np.power(self.C * sigma_y, 0.2)

            # print("Time elapsed: {} sec | Maximum FPS: {}".format(elapsed, round(1.0 / elapsed)))

            self.arr_epsilon_x.append(epsilon_x)
            self.arr_epsilon_y.append(epsilon_y)

            self.matplotlib_widget.plot(self.arr_epsilon_x)


            # plt.subplot(211)
            # plt.ylim(-5, 10)
            # plt.title("Seeing on X axis")
            # plt.plot(self.arr_epsilon_x, c='blue')

            # plt.subplot(212)
            # plt.ylim(-5, 10)
            # plt.title("Seeing on Y axis")
            # plt.plot(self.arr_epsilon_y, c='cyan')

            # plt.tight_layout()
            # plt.pause(1e-3)


        # Displaying #########################################################################
        cv2.drawMarker(frame, (cX_star1, cY_star1), color=(255, 0, 0), markerSize=30, thickness=1)
        cv2.drawMarker(frame, (cX_star2, cY_star2), color=(0, 0, 255), markerSize=30, thickness=1)

        qImage = array2qimage(frame)
        self.stars_capture.setPixmap(QPixmap(qImage))



if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    seeingMonitor = SeeingMonitor()
    seeingMonitor.show()
    sys.exit(app.exec_())