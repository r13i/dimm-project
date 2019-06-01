from collections import deque
import logging
import traceback

import numpy as np
import cv2
import matplotlib.pyplot as plt

from PyQt5.QtCore import QTimer, QDir
from PyQt5.QtGui import QImage, QPalette, QPixmap
from PyQt5.QtWidgets import (QWidget, QGridLayout, QAction, QApplication, QPushButton, QLabel,
    QMainWindow, QMenu, QMessageBox, QSizePolicy, QFileDialog)
from qimage2ndarray import array2qimage, gray2qimage

from utils.state_enum import VideoSource


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
            self.initCamera()

        self.video_source = VideoSource.NONE

        self.matplotlib_widget = MatplotlibWidget(parent=self.seeing_graph, width=6.4, height=3.6, dpi=100)

        self.button_start.clicked.connect(self.startLiveCamera)
        # self.button_settings.clicked.connect(self.showSettings)
        self.button_settings.setEnabled(False)
        self.button_simulation.clicked.connect(self.startSimulation)

        self.button_import.clicked.connect(self.importVideo)
        self.button_export.clicked.connect(self.exportVideo)


        # Timer for acquiring images at regular intervals
        self.acquisition_timer = QTimer(parent=self.centralwidget)
        self.timer_interval = None


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


    def initCamera(self):
        self.Camera = IC.TIS_CAM()

        # self.Camera.SetPropertySwitch("Exposure","Auto",1)
        # self.Camera.SetPropertySwitch("Gain","Auto",1)
        # self.Camera.SetPropertySwitch("WhiteBalance","Auto",1)


    def startLiveCamera(self):

        self.video_source = VideoSource.CAMERA
        self._setPauseButton()

        # Disable other functionalities
        # self.button_simulation.setEnabled(False)

        self.Camera.ShowDeviceSelectionDialog()
        if self.Camera.IsDevValid() != 1:
            QMessageBox.warning(self, "Error Camera Selection", "Unable to open camera device !")
            raise Exception("Unable to open camera device !")

        print('Starting live stream ...')
        self.Camera.StartLive(0)    ####### PAUSE LIVE STREAM FOR PAUSE ??? ##############################################
        # self.Camera.StartLive(1)

        self.timer_interval = 20
        self.acquisition_timer.timeout.connect(self._updateLiveCamera)
        self.acquisition_timer.start(self.timer_interval)


    def showSettings(self):
        print("Is Device Valid ? ", self.Camera.IsDevValid())
        if not self.Camera.IsDevValid():
            QMessageBox.warning(self, "Camera Selection Error",
                "Please select a camera first by clicking on the button <strong>Start</strong>")
            return

        try:
            self.Camera.ShowPropertyDialog()
        except Exception as e:
            logging.error(traceback.format_exc())
            QMessageBox.warning(self, "Property Dialog Error", traceback.format_exc())


    def _updateLiveCamera(self):
        # Capturing a frame
        self.Camera.SnapImage()
        frame = self.Camera.GetImage()
        frame = np.uint8(frame)
        self.frame = cv2.resize(frame, (640, 480))

        print('>>>>>> camera captured')

        self._monitor()
        self.displayParameters()


    def displayParameters(self):
        parameters_text = ""

        ExposureTime = [0]
        self.Camera.GetPropertyAbsoluteValue("Exposure", "Value", ExposureTime)
        parameters_text = parameters_text + str(ExposureTime[0]) + "\n"

        GainValue = [0]
        self.Camera.GetPropertyAbsoluteValue("Gain", "Value", GainValue)
        parameters_text = parameters_text + str(GainValue[0]) + "\n"

        self.parameters_label.setText(parameters_text)
        self.parameters_label.adjustSize()


    def startSimulation(self):

        self.video_source = VideoSource.SIMULATION
        self._setPauseButton()


        # Disable other functionalities
        # self.button_start.setEnabled(False)
        self.button_settings.setEnabled(False)

        # Generating fake images of DIMM star (One single star that is split by the DIMM)
        self.starsGenerator = FakeStars()

        # WIDTH, HEIGHT = self.starsGenerator.width, self.starsGenerator.height
        # self.resize(int(round(float(HEIGHT) * 10. / 3.)), int(round(float(WIDTH) * 10. / 3.)))

        self.timer_interval = 100
        self.acquisition_timer.timeout.connect(self._updateSimulation)
        self.acquisition_timer.start(self.timer_interval)



    def _updateSimulation(self):
        self.frame = self.starsGenerator.generate()
        self._monitor()


    def _monitor(self):

        gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)

        _, thresholded = cv2.threshold(gray, self.THRESH, 255, cv2.THRESH_TOZERO)

        # _, contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        _, contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(self.frame, contours, -1, (0,255,0), 2)

        # if len(contours) >= 2:
        #     moments_star_1 = cv2.moments(contours[0])
        #     moments_star_2 = cv2.moments(contours[1])

        #     cX_star1 = int(moments_star_1["m10"] / moments_star_1["m00"])
        #     cY_star1 = int(moments_star_1["m01"] / moments_star_1["m00"])

        #     cX_star2 = int(moments_star_2["m10"] / moments_star_2["m00"])
        #     cY_star2 = int(moments_star_2["m01"] / moments_star_2["m00"])

        #     if self.enable_seeing.isChecked():
        #         # Calcul Seeing ######################################################################
        #         delta_x = abs(cX_star2 - cX_star1)
        #         delta_y = abs(cY_star2 - cY_star1)

        #         self.arr_delta_x.append(delta_x)
        #         self.arr_delta_y.append(delta_y)

        #         sigma_x = np.std(self.arr_delta_x)
        #         sigma_y = np.std(self.arr_delta_y)


        #         # Seeing
        #         epsilon_x = self.A * np.power(self.B * sigma_x, 0.2)
        #         epsilon_y = self.A * np.power(self.C * sigma_y, 0.2)

        #         # print("Time elapsed: {} sec | Maximum FPS: {}".format(elapsed, round(1.0 / elapsed)))

        #         self.arr_epsilon_x.append(epsilon_x)
        #         self.arr_epsilon_y.append(epsilon_y)

        #         self.matplotlib_widget.plot(self.arr_epsilon_x, 0)
        #         self.matplotlib_widget.plot(self.arr_epsilon_y, 1)


        #         # plt.subplot(211)
        #         # plt.ylim(-5, 10)
        #         # plt.title("Seeing on X axis")
        #         # plt.plot(self.arr_epsilon_x, c='blue')

        #         # plt.subplot(212)
        #         # plt.ylim(-5, 10)
        #         # plt.title("Seeing on Y axis")
        #         # plt.plot(self.arr_epsilon_y, c='cyan')

        #         # plt.tight_layout()
        #         # plt.pause(1e-3)


        #     # Displaying #########################################################################
        #     cv2.drawMarker(self.frame, (cX_star1, cY_star1), color=(255, 0, 0), markerSize=30, thickness=1)
        #     cv2.drawMarker(self.frame, (cX_star2, cY_star2), color=(0, 0, 255), markerSize=30, thickness=1)

        qImage = array2qimage(self.frame)
        self.stars_capture.setPixmap(QPixmap(qImage))


    def importVideo(self):

        self.video_source = VideoSource.VIDEO
        self._setPauseButton()

        filename, _ = QFileDialog.getOpenFileName(self,
            "Select Video File",
            QDir.currentPath(),
            "Video Files (*.avi *.mp4 *.mpeg *.flv *.3gp *.mov);;All Files (*)")

        if filename:
            self.cap = cv2.VideoCapture(filename)

            print("CAP_PROP_POS_MSEC :", self.cap.get(cv2.CAP_PROP_POS_MSEC))
            print("CAP_PROP_POS_FRAMES :", self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            print("CAP_PROP_POS_AVI_RATIO :", self.cap.get(cv2.CAP_PROP_POS_AVI_RATIO))
            print("CAP_PROP_FRAME_WIDTH :", self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            print("CAP_PROP_FRAME_HEIGHT :", self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print("CAP_PROP_FPS :", self.cap.get(cv2.CAP_PROP_FPS))
            print("CAP_PROP_FOURCC :", self.cap.get(cv2.CAP_PROP_FOURCC))
            print("CAP_PROP_FRAME_COUNT :", self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            print("CAP_PROP_FORMAT :", self.cap.get(cv2.CAP_PROP_FORMAT))
            print("CAP_PROP_MODE :", self.cap.get(cv2.CAP_PROP_MODE))
            print("CAP_PROP_BRIGHTNESS :", self.cap.get(cv2.CAP_PROP_BRIGHTNESS))
            print("CAP_PROP_CONTRAST :", self.cap.get(cv2.CAP_PROP_CONTRAST))
            print("CAP_PROP_SATURATION :", self.cap.get(cv2.CAP_PROP_SATURATION))
            print("CAP_PROP_HUE :", self.cap.get(cv2.CAP_PROP_HUE))
            print("CAP_PROP_GAIN :", self.cap.get(cv2.CAP_PROP_GAIN))
            print("CAP_PROP_EXPOSURE :", self.cap.get(cv2.CAP_PROP_EXPOSURE))
            print("CAP_PROP_CONVERT_RGB :", self.cap.get(cv2.CAP_PROP_CONVERT_RGB))
            print("CAP_PROP_WHITE_APERTURE :", self.cap.get(cv2.CAP_PROP_APERTURE))
            print("CAP_PROP_RECTIFICATION :", self.cap.get(cv2.CAP_PROP_RECTIFICATION))
            print("CAP_PROP_ISO_SPEED :", self.cap.get(cv2.CAP_PROP_ISO_SPEED))
            print("CAP_PROP_BUFFERSIZE :", self.cap.get(cv2.CAP_PROP_BUFFERSIZE))


            if self.cap.isOpened() == False:
                QMessageBox.warning(self, "Import from Video", "Cannot load file '{}'.".format(filename))
                return

            self.timer_interval = round(1000.0 / self.cap.get(cv2.CAP_PROP_FPS))
            self.acquisition_timer.timeout.connect(self._grabVideoFrame)
            self.acquisition_timer.start(self.timer_interval)


    def _grabVideoFrame(self):
        ret, frame = self.cap.read()
        if ret == True:
            self.frame = cv2.resize(frame, (640, 480))
            self._monitor()

        else:
            QMessageBox.information(self, "Import from Video", "Video complete !")
            self.cap.release()


    def exportVideo(self):
        pass


    def _setPauseButton(self):
        self.button_pause.setEnabled(True)
        self.button_pause.setText("⏸ Pause")
        self.button_pause.clicked.connect(self._pause)


    def _pause(self):
        self.acquisition_timer.stop()
        self.button_pause.setText("▶ Resume")
        self.button_pause.clicked.connect(self._resume)


    def _resume(self):
        self.acquisition_timer.start(self.timer_interval)
        self._setPauseButton()

        if self.video_source == VideoSource.CAMERA:
            self.acquisition_timer.timeout.connect(self._updateLiveCamera)
        elif self.video_source == VideoSource.SIMULATION:
            self.acquisition_timer.timeout.connect(self._updateSimulation)
        elif self.video_source == VideoSource.CAMERA:
            self.acquisition_timer.timeout.connect(self._grabVideoFrame)






if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    seeingMonitor = SeeingMonitor()
    seeingMonitor.show()
    sys.exit(app.exec_())