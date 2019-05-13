from collections import deque
import numpy as np
import cv2
import matplotlib.pyplot as plt

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPalette, QPixmap
from PyQt5.QtWidgets import (QWidget, QGridLayout, QAction, QApplication, QPushButton, QLabel,
    QMainWindow, QMenu, QMessageBox, QSizePolicy)

from qimage2ndarray import array2qimage, gray2qimage

import ctypes as C
import tis.tisgrabber as IC

lWidth          = C.c_long()
lHeight         = C.c_long()
iBitsPerPixel   = C.c_int()
COLORFORMAT     = C.c_int()



from ui.ui_mainwindow import Ui_MainWindow
from utils.fake_stars import FakeStars
from utils.matplotlib_widget import MatplotlibWidget



class SeeingMonitor(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(SeeingMonitor, self).__init__()
        self.setupUi(self)


        # TIS (The Imaging Source) CCD Camera
        self.Camera = IC.TIS_CAM()
        Devices = self.Camera.GetDevices()

        self.button_start.clicked.connect(self.startLiveCamera)
        self.button_settings.clicked.connect(self.showSettings)

        # self.button_settings.setEnabled(False)
        self.button_simulation.setEnabled(False)


        # Timer for acquiring images at regular intervals
        self.acquisition_timer = QTimer(parent=self.centralwidget)



    def startLiveCamera(self):

        # Partie Camera CCD ###################################################
        self.Camera.ShowDeviceSelectionDialog()

        # if Camera.IsDevValid() != 1:
        #     raise Exception("Unable to open camera device !")

        print('Starting live stream ...')
        self.Camera.StartLive(0)


        # # Partie simulation ###################################################
        # self.starsGenerator = FakeStars()


        # Debut Timer d'acqusition ############################################
        self.acquisition_timer.timeout.connect(self._updateLiveCamera)
        self.acquisition_timer.start(100)



    def showSettings(self):
        self.Camera.ShowPropertyDialog()



    def _updateLiveCamera(self):

        # Capturing a frame
        self.Camera.SnapImage()
        frame = self.Camera.GetImage()
        frame = cv2.resize(frame, (640, 480))

        print('>>>>>> Image captured')

        # self.image_properties.setText(self.Camera.GetImageDescription())
        # self.video_formats.setText(self.Camera.GetVideoFormats())

        qImage = array2qimage(frame)

        self.stars_capture.setPixmap(QPixmap(qImage))




        # debut test

        # ##### test 1
        # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # frame = cv2.resize(frame, (640, 480))
        # frame = np.uint8(frame)
        # qImage = QImage(frame.data, 640, 480, QImage.Format_Grayscale8)

        # ##### test 2
        # frame = cv2.resize(frame, (640, 480))
        # qImage = QImage(frame.data, 640, 480, QImage.Format_RGB32)

        # ##### test 3
        # frame = cv2.resize(frame, (640, 480))
        # qImage = array2qimage(frame)

        # ##### test 4
        # frame = cv2.resize(frame, (640, 480))
        # qImage = gray2qimage(frame)

        # fin test




        # Fonction d'affichage
        # self.stars_capture.setPixmap(QPixmap(qImage))











if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    seeingMonitor = SeeingMonitor()
    seeingMonitor.show()
    sys.exit(app.exec_())