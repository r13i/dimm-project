import logging
from PyQt5.QtWidgets import QApplication

from models import BuiltinCamera
from views import StartWindow

import tis.tisgrabber as IC
import cv2
import numpy as np



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    logger = logging.getLogger()


    camera = IC.TIS_CAM()
    devices = camera.GetDevices()
    for i in range(len(devices)):
        print(str(i) + " : " + str(devices[i]))

    camera_idx = -1
    try:
        camera_idx = int(input("Please select a camera [Default: Built-in webcam] : "))
    except ValueError:
        print("Not a valid index. Using built-in webcam.")

    if camera_idx = -1:
        camera = BuiltinCamera(0)
        camera.initialize()
        logger.info("Initialized: {}".format(camera))

        app = QApplication([])
        logger.info("Starting main window ...")
        start_window = StartWindow(camera, logger)
        start_window.show()

        app.exit(app.exec_())

    else:
        if camera_idx in range(len(Devices)):
            # Open camera with specific model number
            Camera.open(Devices[camera_idx])
            # Set a video format
            Camera.SetVideoFormat("RGB32 (640x480)")
            #Set a frame rate of 30 frames per second
            Camera.SetFrameRate( 30.0 )
            print('Successfully opened camera {}'.format(Devices[camera_idx]))

            print('Starting live stream ...')
            # Camera.StartLive(0)
            Camera.StartLive(1)

            # Capturing a frame
            Camera.SnapImage()
            frame = Camera.GetImage()

            cv2.imshow('CCD Camera', frame)
        else:
            raise Exception("No camera with given index: {}".format(camera_idx))
