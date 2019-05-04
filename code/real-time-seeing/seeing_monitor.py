from collections import deque
from time import clock
import numpy as np
import cv2
import matplotlib.pyplot as plt

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPalette, QPixmap
from PyQt5.QtWidgets import (QWidget, QGridLayout, QAction, QApplication, QPushButton, QLabel,
    QMainWindow, QMenu, QMessageBox, QSizePolicy)


# Dev only #####################################################################################
import platform
if platform.system() == 'Windows':
    import tis.tisgrabber as IC
    from ui.ui_mainwindow import Ui_MainWindow

elif platform.system() == 'Linux':
    from PyQt5.uic import compileUi
    with open("./code/real-time-seeing/ui/ui_mainwindow.py", "wt") as ui_file:
        compileUi("./code/real-time-seeing/ui/layout.ui", ui_file)
    from ui.ui_mainwindow import Ui_MainWindow


from utils.fake_stars import FakeStars
from utils.matplotlib_widget import MatplotlibWidget



class SeeingMonitor(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(SeeingMonitor, self).__init__()

        self.setupUi(self)

        # TIS (The Imaging Source) CCD Camera
        if platform.system == 'Windows':
            self.Camera = IC.TIS_CAM()
            self.initCameraDroplist()


        # self.stars_capture = QLabel(parent=self.central_widget)
        # self.stars_capture.setBackgroundRole(QPalette.Base)
        # self.stars_capture.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # self.stars_capture.setScaledContents(True)

        self.matplotlib_widget = MatplotlibWidget(parent=self.seeing_graph)

        self.button_start.clicked.connect(self.startLiveCamera)
        self.button_simulation.clicked.connect(self.startSimulation)

        # Timer for acquiring images at regular intervals
        self.acquisition_timer = QTimer(parent=self.centralwidget)


        # Define actions such as zoom-in, zoom-out, open camera stream, ...
        self.createActions()
        # Create menus with the actions
        self.createMenus()

        # self.setWindowTitle("Seeing Monitor")
        # self.resize(640, 480)

    def initCameraDroplist(self):
        devices = self.Camera.GetDevices()
        devices = [device.decode("utf-8") for device in devices]
        self.select_camera_button.addItems(devices)

        self.select_camera_button.currentTextChanged.connect(self.selectCamera)

    def selectCamera(self, camera_name):

        # Open camera with specific model number
        print("Opening camera: {}".format(camera_name))
        self.Camera.open(camera_name)

        if Camera.IsDevValid() == 1:
            print("Camera opened successfully !")
        else:
            raise Exception("Cannot open camera !")

        # Set a video format
        self.Camera.SetVideoFormat("RGB32 (640x480)")
        #Set a frame rate of 30 frames per second
        self.Camera.SetFrameRate( 30.0 )

        print('Successfully setup camera {}'.format(camera_name))


    def startLiveCamera(self):

        # Disable other functionalities
        self.button_simulation.setEnabled(False)

        # QMessageBox.information(self, "Camera Stream", "This functionality will soon be added")
        print('Starting live stream ...')
        self.Camera.StartLive(0)
        # self.Camera.StartLive(1)

        # self.resize(int(round(480. * 10. / 7.)), int(round(640. * 10. / 7.)))

        self.acquisition_timer.timeout.connect(self._updateLiveCamera)
        self.acquisition_timer.start(20)



    def _updateLiveCamera(self):

        # Capturing a frame
        self.Camera.SnapImage()
        frame = self.Camera.GetImage()

        qImage = QImage(frame.data, 480, 360, QImage.Format_Grayscale8)

        self.stars_capture.setPixmap(QPixmap(qImage))


    def startSimulation(self):

        # Disable other functionalities
        self.button_start.setEnabled(False)
        self.select_camera_button.setEnabled(False)

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
        gray = frame

        # Fast thresholding
        _, thresholded = cv2.threshold(gray, self.THRESH, 255, cv2.THRESH_TOZERO)

        # # Slow thresholding
        # thresholded = np.where(gray > self.THRESH, gray, 0)

        star_1 = thresholded[:, : thresholded.shape[1] // 2]
        star_2 = thresholded[:, thresholded.shape[1] // 2 :]

        moments_star_1 = cv2.moments(star_1)
        moments_star_2 = cv2.moments(star_2)

        cX_star1 = int(moments_star_1["m10"] / moments_star_1["m00"])
        cY_star1 = int(moments_star_1["m01"] / moments_star_1["m00"])

        cX_star2 = int(moments_star_2["m10"] / moments_star_2["m00"]) + frame.shape[1] // 2
        cY_star2 = int(moments_star_2["m01"] / moments_star_2["m00"])


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
        cv2.drawMarker(frame, (cX_star1, cY_star1), color=(127, 0, 0), markerSize=30, thickness=1)
        cv2.drawMarker(frame, (cX_star2, cY_star2), color=(127, 0, 0), markerSize=30, thickness=1)


        qImage = QImage(frame.data, self.starsGenerator.width, self.starsGenerator.height, QImage.Format_Grayscale8)
        self.stars_capture.setPixmap(QPixmap(qImage))


        # self.scaleFactor = 1.0
        # self.fitToWindowAct.setEnabled(True)
        # self.updateActions()

        # if not self.fitToWindowAct.isChecked():
        #     self.stars_capture.adjustSize()



    # Zoom +25%
    def zoomIn(self):
        self.scaleImage(1.25)

    # Zoom -25%
    def zoomOut(self):
        self.scaleImage(0.8)

    def normalSize(self):
        self.stars_capture.adjustSize()
        self.scaleFactor = 1.0

    def fitToWindow(self):
        fitToWindow = self.fitToWindowAct.isChecked()
        self.scrollArea.setWidgetResizable(fitToWindow)
        if not fitToWindow:
            self.normalSize()

        self.updateActions()

    def about(self):
        QMessageBox.about(self, "About Seeing Monitor",
                "<p>Version 1.0</p>")

    def createActions(self):
        self.startAct = QAction("&Open camera stream...", self, shortcut="Ctrl+O",
                triggered=self.startLiveCamera)

        self.simulationAct = QAction("&Start simulation...", self, shortcut="Ctrl+S",
                triggered=self.startSimulation)

        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q",
                triggered=self.close)

        self.zoomInAct = QAction("Zoom &In (25%)", self, shortcut="Ctrl++",
                enabled=False, triggered=self.zoomIn)

        self.zoomOutAct = QAction("Zoom &Out (25%)", self, shortcut="Ctrl+-",
                enabled=False, triggered=self.zoomOut)

        self.normalSizeAct = QAction("&Normal Size", self, shortcut="Ctrl+S",
                enabled=False, triggered=self.normalSize)

        self.fitToWindowAct = QAction("&Fit to Window", self, enabled=False,
                checkable=True, shortcut="Ctrl+F", triggered=self.fitToWindow)

        self.aboutAct = QAction("&About", self, triggered=self.about)

        self.aboutQtAct = QAction("About &Qt", self,
                triggered=QApplication.instance().aboutQt)

    def createMenus(self):
        self.fileMenu = QMenu("&Start", self)
        self.fileMenu.addAction(self.startAct)
        self.fileMenu.addAction(self.simulationAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.viewMenu = QMenu("&View", self)
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.fitToWindowAct)

        self.helpMenu = QMenu("&Help", self)
        self.helpMenu.addAction(self.aboutAct)
        self.helpMenu.addAction(self.aboutQtAct)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.helpMenu)

    def updateActions(self):
        self.zoomInAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.zoomOutAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.normalSizeAct.setEnabled(not self.fitToWindowAct.isChecked())

    def scaleImage(self, factor):
        self.scaleFactor *= factor
        self.stars_capture.resize(self.scaleFactor * self.stars_capture.pixmap().size())

        self.adjustScrollBar(self.scrollArea.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scrollArea.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scaleFactor < 3.0)
        self.zoomOutAct.setEnabled(self.scaleFactor > 0.333)

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                                + ((factor - 1) * scrollBar.pageStep()/2)))



if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    seeingMonitor = SeeingMonitor()
    seeingMonitor.show()
    sys.exit(app.exec_())