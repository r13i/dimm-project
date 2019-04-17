
import numpy as np
import cv2

import skimage


import time


THRESH = 127
cap = cv2.VideoCapture("/home/peaceful/workspace/Qt/dimm/dimm-project/recording.avi")


arr1 = []

try:
    while cap.isOpened():
        ret, frame = cap.read()

        tic = time.clock()

        if frame is None:
            break        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Fast thresholding
        _, thresholded = cv2.threshold(gray, THRESH, 255, cv2.THRESH_TOZERO)

        # # Slow thresholding
        # thresholded = np.where(gray > THRESH, gray, 0)



        M = cv2.moments(thresholded)

        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])

        toc = time.clock()
        arr1.append(toc - tic)

        cv2.drawMarker(frame, (cX, cY), color=(255, 0, 0))


        cv2.imshow('image', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break



    print(len(arr1), np.mean(arr1))


    cap.release()
    cv2.destroyAllWindows()

except KeyboardInterrupt:
    cap.release()
    cv2.destroyAllWindows()
