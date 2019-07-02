from collections import deque
import logging
import traceback
import time
from os.path import splitext, join
import threading
from random import random
import csv

import numpy as np
import cv2
import matplotlib.pyplot as plt

from PyQt5.QtCore import QObject, QEvent, QTimer, QDir, Qt, QDateTime
from PyQt5.QtGui import QImage, QPalette, QPixmap, QPainter, QFont
from PyQt5.QtWidgets import (QWidget, QGridLayout, QAction, QApplication, QPushButton, QLabel,
    QMainWindow, QMenu, QMessageBox, QSizePolicy, QFileDialog)
from PyQt5.QtChart import QLineSeries, QDateTimeAxis, QValueAxis, QChart, QChartView
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


if platform.system() == 'Linux':
    class CallbackUserData(object):
        pass
else:
    class CallbackUserData(C.Structure):
        """ Example for user data passed to the callback function. """
        def __init__(self):
            self.width = 0
            self.height = 0
            self.iBitsPerPixel = 0
            self.buffer_size = 0



class EventHandler(QObject):
    def __init__(self, seeingMonitor):
        super(QObject, self).__init__()
        self.seeingMonitor = seeingMonitor

        self.mouse_pressed = False
        self.starting_point = []

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if self.seeingMonitor.select_noiseArea == True and self.mouse_pressed == False:
                self.mouse_pressed = True
                self.starting_point.append(event.x())
                self.starting_point.append(event.y())
            return True
        elif event.type() == QEvent.MouseMove:
            if self.seeingMonitor.select_noiseArea == True and self.mouse_pressed == True:
                self.seeingMonitor._set_noiseArea(self.starting_point[0], self.starting_point[1], event.x(), event.y())
                if self.seeingMonitor.pause_pressed:
                    self.seeingMonitor.draw_only_frame = self.seeingMonitor.frame.copy()
                    self.seeingMonitor._draw_noiseArea()
                    self.seeingMonitor._displayImage()
            return True
        elif event.type() == QEvent.MouseButtonRelease:
            self.mouse_pressed = False
            self.starting_point = []
            self.seeingMonitor.select_noiseArea = False
            self.seeingMonitor.label_info.setText("")
            self.seeingMonitor.button_noise.setText("Select Noise Area")
            return True
        else:
            return QObject.eventFilter(self, obj, event)




class SeeingMonitor(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super(SeeingMonitor, self).__init__()
        self.setupUi(self)

        self.Camera = None
        self.THRESH = None
        self.threshold_auto = False
        self.frame = None
        self.draw_only_frame = None
        self.video_source = VideoSource.NONE
        self.export_video = False
        self.select_noiseArea = False
        self.coordinates_noiseArea = []
        self.lineedit_path.setText(QDir.currentPath())
        self.lineedit_filename.setText("seeing.csv")
        self.save_filename = None
        self._updateFileSave()
        self.pause_pressed = False

        self.datetimeedit_start.setMinimumDateTime(QDateTime.currentDateTime())
        self.datetimeedit_end.setMinimumDateTime(QDateTime.currentDateTime())

        if platform.system() == 'Linux':
            self.button_start.setEnabled(False)
            self.button_settings.setEnabled(False)

        self.button_start.clicked.connect(self.startLiveCamera)
        self.button_settings.clicked.connect(self.showSettings)
        self.button_simulation.clicked.connect(self.startSimulation)
        self.button_import.clicked.connect(self.importVideo)
        self.button_export.clicked.connect(self.exportVideo)
        self.button_noise.clicked.connect(self.selectNoiseArea)
        self.lineedit_path.textEdited.connect(self._updateFileSave)
        self.lineedit_filename.textEdited.connect(self._updateFileSave)
        self.slider_threshold.valueChanged.connect(self._updateThreshold)
        self.checkbox_thresh.stateChanged.connect(self._updateThresholdState)

        # Update the Tilt value
        self.spinbox_b.valueChanged.connect(self._updateFormulaZTilt)
        self.spinbox_d.valueChanged.connect(self._updateFormulaZTilt)
        # Update the constants in the FWHM seeing formula
        self.spinbox_d.valueChanged.connect(self._updateFormulaConstants)
        self.spinbox_lambda.valueChanged.connect(self._updateFormulaConstants)


        # Timer for acquiring images at regular intervals
        self.acquisition_timer = QTimer(parent=self.centralwidget)
        self.timer_interval = None


        self._updateThreshold()
        self._updateFormulaZTilt()
        self._updateFormulaConstants()


        # Storing the Delta X and Y in an array to calculate the Standard Deviation
        self.arr_delta_x = deque(maxlen=100)
        self.arr_delta_y = deque(maxlen=100)

        self.plot_length = 1000
        self.fwhm_lat = 0
        self.fwhm_tra = 0
        self.max_lat = 1
        self.min_lat = 0
        self.max_tra = 1
        self.min_tra = 0


        self.series_lat = QLineSeries()
        self.series_lat.setName("Lateral")
        self.series_tra = QLineSeries()
        self.series_tra.setName("Transversal")

        self.chart = QChart()
        self.chart.addSeries(self.series_lat)
        self.chart.addSeries(self.series_tra)

        # self.chart.createDefaultAxes()
        self.axis_horizontal = QDateTimeAxis()
        self.axis_horizontal.setMin(QDateTime.currentDateTime().addSecs(-60 * 1))
        self.axis_horizontal.setMax(QDateTime.currentDateTime().addSecs(0))
        self.axis_horizontal.setFormat("HH:mm:ss.zzz")
        self.axis_horizontal.setLabelsFont(QFont(QFont.defaultFamily(self.font()), pointSize=5))
        self.axis_horizontal.setLabelsAngle(-20)
        self.chart.addAxis(self.axis_horizontal, Qt.AlignBottom)

        self.axis_vertical_lat = QValueAxis()
        self.axis_vertical_lat.setRange(self.max_lat, self.min_lat)
        self.chart.addAxis(self.axis_vertical_lat, Qt.AlignLeft)

        self.axis_vertical_tra = QValueAxis()
        self.axis_vertical_tra.setRange(self.max_tra, self.min_tra)
        self.chart.addAxis(self.axis_vertical_tra, Qt.AlignRight)

        self.series_lat.attachAxis(self.axis_horizontal)
        self.series_lat.attachAxis(self.axis_vertical_lat)

        self.series_tra.attachAxis(self.axis_horizontal)
        self.series_tra.attachAxis(self.axis_vertical_tra)

        self.chart.setTitle("Full Width at Half Maximum")
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignBottom)
        self.chartView = QChartView(self.chart, parent=self.graphicsView)
        self.chartView.resize(640, 250)
        self.chartView.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.chartView.setRenderHint(QPainter.Antialiasing)


    def closeEvent(self, event):
        try:
            self.Camera.StopLive()
        except AttributeError:
            pass

        try:
            self.cap.release()
        except AttributeError:
            pass

        try:
            self.video_writer.release()
        except AttributeError:
            pass

        event.accept()


    def _callbackFunction(self, hGrabber, pBuffer, framenumber, pData):
        """ This is an example callback function for image processig  with 
            opencv. The image data in pBuffer is converted into a cv Matrix
            and with cv.mean() the average brightness of the image is
            measuered.

        :param: hGrabber: This is the real pointer to the grabber object.
        :param: pBuffer : Pointer to the first pixel's first byte
        :param: framenumber : Number of the frame since the stream started
        :param: pData : Pointer to additional user data structure
        """
        if pData.buffer_size > 0:
            image = C.cast(pBuffer, C.POINTER(C.c_ubyte * pData.buffer_size))

            cvMat = np.ndarray(
                buffer = image.contents,
                dtype  = np.uint8,
                shape  = (pData.height, pData.width, pData.iBitsPerPixel)
            )

            frame = np.uint8(cvMat)
            self.frame = cv2.resize(frame, (640, 480))
            self.draw_only_frame = self.frame.copy()
            self._monitor()


    def _startLiveCamera(self):

        # Create a function pointer
        Callbackfunc = IC.TIS_GrabberDLL.FRAMEREADYCALLBACK(self._callbackFunction)
        ImageDescription = CallbackUserData()    

        # Create the camera object
        self.Camera = IC.TIS_CAM()

        self.Camera.ShowDeviceSelectionDialog()
        if self.Camera.IsDevValid() != 1:
            print("[Error Camera Selection] Couldn't open camera device !")
            # QMessageBox.warning(self, "Error Camera Selection", "Couldn't open camera device !")
            # raise Exception("Unable to open camera device !")
            return

        # Now pass the function pointer and our user data to the library
        self.Camera.SetFrameReadyCallback(Callbackfunc, ImageDescription)

        # Handle each incoming frame automatically
        self.Camera.SetContinuousMode(0)

        print('Starting live stream ...')
        self.Camera.StartLive(0)    ####### PAUSE LIVE STREAM WHEN PAUSE CLICKED ??? ##############################################
        # self.Camera.StartLive(1)

        Imageformat = self.Camera.GetImageDescription()[:3]
        ImageDescription.width = Imageformat[0]
        ImageDescription.height= Imageformat[1]
        ImageDescription.iBitsPerPixel=Imageformat[2]//8
        ImageDescription.buffer_size = ImageDescription.width * ImageDescription.height * ImageDescription.iBitsPerPixel

        while self.video_source == VideoSource.CAMERA:
            pass

        # self.timer_interval = 20
        # try:
        #     self.acquisition_timer.disconnect()
        # except TypeError:
        #     pass
        # self.acquisition_timer.timeout.connect(self._updateLiveCamera)
        # self.acquisition_timer.start(self.timer_interval)


    def startLiveCamera(self):
        try:
            self.acquisition_timer.disconnect()
        except TypeError:
            pass

        self.video_source = VideoSource.CAMERA
        self.button_export.setEnabled(True)
        self._setPauseButton()

        # Disable other functionalities
        # self.button_simulation.setEnabled(False)

        t = threading.Thread(target=self._startLiveCamera, args=(), daemon=True)
        t.start()


    def showSettings(self):
        if not self.Camera.IsDevValid():
            QMessageBox.warning(self, "Camera Selection Error",
                "Please select a camera first by clicking on the button <strong>Start</strong>")
            return

        try:
            self.Camera.ShowPropertyDialog()
        except Exception as e:
            logging.error(traceback.format_exc())
            QMessageBox.warning(self, "Property Dialog Error", traceback.format_exc())


    # def _updateLiveCamera(self):
    #     # Capturing a frame
    #     self.Camera.SnapImage()
    #     frame = self.Camera.GetImage()
    #     frame = np.uint8(frame)
    #     self.frame = cv2.resize(frame, (640, 480))
    #     self.draw_only_frame = self.frame.copy()
    #     self._monitor()

        # self.displayParameters()


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

        if self.Camera != None and self.Camera.IsDevValid() == 1:
            self.Camera.StopLive()
        self.video_source = VideoSource.SIMULATION
        self.button_export.setEnabled(True)
        self._setPauseButton()


        # Disable other functionalities
        # self.button_start.setEnabled(False)
        self.button_settings.setEnabled(False)

        # Generating fake images of DIMM star (One single star that is split by the DIMM)
        self.starsGenerator = FakeStars()
        self.timer_interval = 100

        try:
            self.acquisition_timer.disconnect()
        except TypeError:
            pass
        self.acquisition_timer.timeout.connect(self._updateSimulation)
        self.acquisition_timer.start(self.timer_interval)


    def _updateSimulation(self):
        frame = self.starsGenerator.generate()
        self.frame = cv2.resize(frame, (640, 480))
        self.draw_only_frame = self.frame.copy()
        self._monitor()


################################################################################################################################################################
    def _writeCSV(self, headerOnly=False):
        if headerOnly:
            with open(self.save_filename, "w") as csvFile:
                fieldnames = ["timestamp", "lateral", "transversal", "star"]
                writer = csv.DictWriter(csvFile, fieldnames=fieldnames)
                writer.writeheader()
                csvFile.close()

        else:
            with open(self.save_filename, "a") as csvFile:
                writer = csv.writer(csvFile)
                writer.writerow([self.current.toTime_t() , self.fwhm_lat, self.fwhm_tra, self.lineedit_star.text()])
                # csvFile.write(",".join([str(self.current) , str(self.fwhm_lat), str(self.fwhm_tra), self.lineedit_star.text()]))
                # csvFile.write("\n")
                # csvFile.close()


    def selectNoiseArea(self):
        self.label_info.setText("Please select on the video a noise area.")
        self.button_noise.setText("Selecting ...")
        self.coordinates_noiseArea = []
        self.select_noiseArea = True


    def _set_noiseArea(self, x1, y1, x2, y2):
        if len(self.coordinates_noiseArea) == 0:
            self.coordinates_noiseArea.append([x1, y1])
            self.coordinates_noiseArea.append([x2, y2])

        elif len(self.coordinates_noiseArea) == 2:
            self.coordinates_noiseArea[0] = [x1, y1]
            self.coordinates_noiseArea[1] = [x2, y2]


    def _draw_noiseArea(self):
        if len(self.coordinates_noiseArea) >= 2:
            cv2.rectangle(
                self.draw_only_frame,
                (self.coordinates_noiseArea[0][0], self.coordinates_noiseArea[0][1]),
                (self.coordinates_noiseArea[1][0], self.coordinates_noiseArea[1][1]),
                (0, 255, 0), 1)


    def _updateFileSave(self):
        self.save_filename = join(self.lineedit_path.text(), self.lineedit_filename.text())
        self._writeCSV(headerOnly=True)


    def _updateThreshold(self):
        if self.threshold_auto:
            if self.coordinates_noiseArea.__len__() >= 2:
                noise_area = self.frame[
                    self.coordinates_noiseArea[0][1] : self.coordinates_noiseArea[1][1],
                    self.coordinates_noiseArea[0][0] : self.coordinates_noiseArea[1][0]
                ]
                try:
                    self.THRESH = noise_area.max() + 20
                    # self.THRESH = int(round(noise_area.mean()))
                except ValueError:
                    return

                self.slider_threshold.setValue(self.THRESH)
                self.checkbox_thresh.setText("Threshold ({}, auto)".format(self.THRESH))
        else:
            self.THRESH = self.slider_threshold.value()
            self.checkbox_thresh.setText("Threshold ({})".format(self.THRESH))


    def _updateThresholdState(self, state):
        if state == 0:
            self.threshold_auto = False
            self.slider_threshold.setEnabled(True)
        else:
            if self.coordinates_noiseArea.__len__() < 2:
                QMessageBox.information(self, "Select Noise Area", "Please select the noise area")
                self.selectNoiseArea()

            self.threshold_auto = True
            self.slider_threshold.setEnabled(False)


    def _updateFormulaZTilt(self):
        self.spinbox_d.setStyleSheet("QSpinBox { background-color: blue; }")
        try:
            b = float(self.spinbox_b.value()) / float(self.spinbox_d.value())
        except ZeroDivisionError:
            QMessageBox.warning(self, "Zero Division Error", "D (Apertures Diameter cannot be Zero")
            return
        self.K_lat = 0.364 * (1 - 0.532 * np.power(b, -1 / 3) - 0.024 * np.power(b, -7 / 3))
        self.K_tra = 0.364 * (1 - 0.798 * np.power(b, -1 / 3) - 0.018 * np.power(b, -7 / 3))


    def _updateFormulaConstants(self):
        # Calculate value to make process faster
        self.A = 0.98 * np.power(float(self.spinbox_d.value()) / float(self.spinbox_lambda.value()), 0.2)


    def _calcSeeing(self):
        std_x = np.std(self.arr_delta_x)
        std_y = np.std(self.arr_delta_y)

        # Seeing
        self.current = QDateTime.currentDateTime()
        self.fwhm_lat = self.A * np.power(std_x / self.K_lat, 0.6)
        self.fwhm_tra = self.A * np.power(std_y / self.K_tra, 0.6)

        threading.Thread(target=self._plotSeeing, args=(), daemon=True).start()
        threading.Thread(target=self._writeCSV, args=(), daemon=True).start()

        self.label_info.setText("lat: " + str(self.fwhm_lat) + " | lon: " + str(self.fwhm_tra))


    def _calcSeeing_arcsec(self):
        std_x = np.std(self.arr_delta_x)
        std_y = np.std(self.arr_delta_y)

        # Seeing
        self.current = QDateTime.currentDateTime()
        self.fwhm_lat = self.A * np.power(std_x / self.K_lat, 0.6) * 205.0 * self.spinbox_pwidth.value() / self.spinbox_focal.value()
        self.fwhm_tra = self.A * np.power(std_y / self.K_tra, 0.6) * 205.0 * self.spinbox_pheight.value() / self.spinbox_focal.value()

        threading.Thread(target=self._plotSeeing, args=(), daemon=True).start()
        threading.Thread(target=self._writeCSV, args=(), daemon=True).start()

        self.label_info.setText("lat: " + str(self.fwhm_lat) + " | lon: " + str(self.fwhm_tra))


    def _monitor(self):

        tic = time.time()

        gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)

        self._updateThreshold()
        _, thresholded = cv2.threshold(gray, self.THRESH, 255, cv2.THRESH_TOZERO)

        # _, contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        contours = contours[:2]

        # if contours.__len__() > 2:
        #     QMessageBox.warning(self, "Thresholding error", "More than 2 projections were found. " + \
        #         "Please increase threshold manually or select a better noise area.")

        cv2.drawContours(self.draw_only_frame, contours, -1, (0,255,0), 2)
        self._draw_noiseArea()

        try:
            moments_star_1 = cv2.moments(contours[0])
            moments_star_2 = cv2.moments(contours[1])

        except IndexError:
            print("Only {} were found ! (Must be at least 2)".format(len(contours)))

        else:

            try:
                cX_star1 = int(moments_star_1["m10"] / moments_star_1["m00"])
                cY_star1 = int(moments_star_1["m01"] / moments_star_1["m00"])

                cX_star2 = int(moments_star_2["m10"] / moments_star_2["m00"])
                cY_star2 = int(moments_star_2["m01"] / moments_star_2["m00"])

            except ZeroDivisionError:
                return

            if self.enable_seeing.isChecked():
                delta_x = abs(cX_star2 - cX_star1)
                delta_y = abs(cY_star2 - cY_star1)

                self.arr_delta_x.append(delta_x)
                self.arr_delta_y.append(delta_y)

                # self._calcSeeing()
                self._calcSeeing_arcsec()


            cv2.drawMarker(
                self.draw_only_frame,
                (cX_star1, cY_star1),
                color=(0, 0, 255), markerSize=30, thickness=1)
            cv2.drawMarker(
                self.draw_only_frame,
                (cX_star2, cY_star2),
                color=(0, 0, 255), markerSize=30, thickness=1)

        finally:

            self._displayImage()

            threading.Thread(target=self._writeVideoFile, args=(), daemon=True).start()

        toc = time.time()
        elapsed = toc - tic
        try:
            print("FPS max = {}".format(int(1.0 / elapsed)))
        except ZeroDivisionError:
            pass


    def _displayImage(self):
        qImage = array2qimage(self.draw_only_frame)
        self.stars_capture.setPixmap(QPixmap(qImage))


    def _plotSeeing(self):

        self.axis_horizontal.setMin(QDateTime.currentDateTime().addSecs(-60 * 1))
        self.axis_horizontal.setMax(QDateTime.currentDateTime().addSecs(0))

        if self.series_lat.count() > self.plot_length - 1:
            self.series_lat.removePoints(0, self.series_lat.count() - self.plot_length - 1)

        if self.series_tra.count() > self.plot_length - 1:
            self.series_tra.removePoints(0, self.series_tra.count() - self.plot_length - 1)

        if self.fwhm_lat > self.max_lat:
            self.max_lat = self.fwhm_lat
            self.axis_vertical_lat.setMax(self.max_lat + 10)
        if self.fwhm_lat < self.min_lat:
            self.min_lat = self.fwhm_lat
            self.axis_vertical_lat.setMax(self.min_lat - 10)
        if self.fwhm_tra > self.max_tra:
            self.max_tra = self.fwhm_tra
            self.axis_vertical_tra.setMax(self.max_tra + 10)
        if self.fwhm_tra < self.min_tra:
            self.min_tra = self.fwhm_tra
            self.axis_vertical_tra.setMax(self.min_tra - 10)


        # print(self.fwhm_lat, self.fwhm_tra)

        self.series_lat.append(self.current.toMSecsSinceEpoch(), self.fwhm_lat)
        self.series_tra.append(self.current.toMSecsSinceEpoch(), self.fwhm_tra)


    def importVideo(self):

        self.video_source = VideoSource.VIDEO
        self.button_export.setEnabled(True)
        self._setPauseButton()

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self,
            "Import from Video File",
            QDir.currentPath(),
            "Video Files (*.avi *.mp4 *.mpeg *.flv *.3gp *.mov);;All Files (*)",
            options=options)

        if filename:
            if self.Camera != None and self.Camera.IsDevValid() == 1:
                self.Camera.StopLive()

            self.cap = cv2.VideoCapture(filename)

            # print("CAP_PROP_POS_MSEC :", self.cap.get(cv2.CAP_PROP_POS_MSEC))
            # print("CAP_PROP_POS_FRAMES :", self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            # print("CAP_PROP_POS_AVI_RATIO :", self.cap.get(cv2.CAP_PROP_POS_AVI_RATIO))
            # print("CAP_PROP_FRAME_WIDTH :", self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            # print("CAP_PROP_FRAME_HEIGHT :", self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            # print("CAP_PROP_FPS :", self.cap.get(cv2.CAP_PROP_FPS))
            # print("CAP_PROP_FOURCC :", self.cap.get(cv2.CAP_PROP_FOURCC))
            # print("CAP_PROP_FRAME_COUNT :", self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # print("CAP_PROP_FORMAT :", self.cap.get(cv2.CAP_PROP_FORMAT))
            # print("CAP_PROP_MODE :", self.cap.get(cv2.CAP_PROP_MODE))
            # print("CAP_PROP_BRIGHTNESS :", self.cap.get(cv2.CAP_PROP_BRIGHTNESS))
            # print("CAP_PROP_CONTRAST :", self.cap.get(cv2.CAP_PROP_CONTRAST))
            # print("CAP_PROP_SATURATION :", self.cap.get(cv2.CAP_PROP_SATURATION))
            # print("CAP_PROP_HUE :", self.cap.get(cv2.CAP_PROP_HUE))
            # print("CAP_PROP_GAIN :", self.cap.get(cv2.CAP_PROP_GAIN))
            # print("CAP_PROP_EXPOSURE :", self.cap.get(cv2.CAP_PROP_EXPOSURE))
            # print("CAP_PROP_CONVERT_RGB :", self.cap.get(cv2.CAP_PROP_CONVERT_RGB))
            # print("CAP_PROP_WHITE_APERTURE :", self.cap.get(cv2.CAP_PROP_APERTURE))
            # print("CAP_PROP_RECTIFICATION :", self.cap.get(cv2.CAP_PROP_RECTIFICATION))
            # print("CAP_PROP_ISO_SPEED :", self.cap.get(cv2.CAP_PROP_ISO_SPEED))
            # print("CAP_PROP_BUFFERSIZE :", self.cap.get(cv2.CAP_PROP_BUFFERSIZE))


            if self.cap.isOpened() == False:
                QMessageBox.warning(self, "Import from Video", "Cannot load file '{}'.".format(filename))
                return

            self.timer_interval = round(1000.0 / self.cap.get(cv2.CAP_PROP_FPS))
            try:
                self.acquisition_timer.disconnect()
            except TypeError:
                pass
            self.acquisition_timer.timeout.connect(self._grabVideoFrame)
            self.acquisition_timer.start(self.timer_interval)


    def _grabVideoFrame(self):
        ret, frame = self.cap.read()
        if ret == True:
            self.frame = cv2.resize(frame, (640, 480))
            self.draw_only_frame = self.frame.copy()
            self._monitor()

        else:
            try:
                self.acquisition_timer.disconnect()
            except TypeError:
                pass

            QMessageBox.information(self, "Import from Video", "Video complete !")
            self.cap.release()


    def exportVideo(self):
        # if not self.enable_seeing.isChecked():
        #     answer = QMessageBox.question(self,
        #         "Export to Video File",
        #         "Seeing Monitoring is not activated. Continue ?",
        #         QMessageBox.Yes|QMessageBox.No,
        #         QMessageBox.No)

        #     if answer == QMessageBox.No:
        #         return

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(self,
            "Export to Video File",
            QDir.currentPath(),
            "All Files (*);;Video Files (*.avi *.mp4 *.mpeg *.flv *.3gp *.mov)",
            options=options)

        if filename:
            if splitext(filename)[1] != ".avi":
                filename = splitext(filename)[0] + ".avi"
                QMessageBox.information(self, "Export to Video File", "Only '.avi' extension is supported. Video will be saved as '{}'".format(filename))

            print(round(1000.0 / float(self.timer_interval)))

            self.video_writer = cv2.VideoWriter(
                filename,
                cv2.VideoWriter_fourcc(*'MJPG'),
                round(1000.0 / float(self.timer_interval)),
                (640, 480)  #################################################################################
            )
            self.export_video = True

    def _writeVideoFile(self):
        current = QDateTime.currentDateTime()
        if self.export_video and current >= self.datetimeedit_start.dateTime() and \
            current < self.datetimeedit_end.dateTime():

            # self.video_writer.write(self.frame)
            self.video_writer.write(self.draw_only_frame)


    def _setPauseButton(self):
        self.button_pause.setEnabled(True)
        self.button_pause.setText("⏸ Pause")
        self.button_pause.clicked.connect(self._pause)


    def _pause(self):
        self.pause_pressed = True

        # IC_SuspendLive IC_StopLive ##################################################################################
        self.button_pause.setText("▶ Resume")
        self.button_pause.clicked.connect(self._resume)

        if self.video_source == VideoSource.CAMERA:
            self.Camera.StopLive()
        else:
            self.acquisition_timer.stop()


    def _resume(self):
        self.pause_pressed = False
        self._setPauseButton()

        if self.video_source == VideoSource.CAMERA:
            self.Camera.StartLive(0)
        else:
            try:
                self.acquisition_timer.disconnect()
            except TypeError:
                pass

            self.acquisition_timer.start(self.timer_interval)

            if self.video_source == VideoSource.CAMERA:
                pass
            elif self.video_source == VideoSource.SIMULATION:
                self.acquisition_timer.timeout.connect(self._updateSimulation)
            elif self.video_source == VideoSource.VIDEO:
                self.acquisition_timer.timeout.connect(self._grabVideoFrame)






if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)

    seeingMonitor = SeeingMonitor()
    eventHandler = EventHandler(seeingMonitor)
    seeingMonitor.stars_capture.installEventFilter(eventHandler)
    seeingMonitor.show()
    sys.exit(app.exec_())
