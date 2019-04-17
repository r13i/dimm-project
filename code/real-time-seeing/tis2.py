import cv2
import numpy as np

cap = cv2.VideoCapture("polaris0004 22-56-53.avi")
while True:
    ret, frame = cap.read()
    gray_image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # convert the grayscale image to binary image
    ret, thresh = cv2.threshold(gray_image, 127, 255, 0)

    # calculate moments of binary image
    M = cv2.moments(thresh)

    # calculate x,y coordinate of center
    cX = int(M["m10"] / M["m00"])
    cY = int(M["m01"] / M["m00"])

    # put text and highlight the center
    cv2.circle(frame, (cX, cY), 5, (255, 0, 0), 2)
    cv2.putText(frame, "etoile", (cX - 25, cY - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    # display the image
    cv2.imshow("Image", frame)



    key = cv2.waitKey(25)
    if key == 27:
        break
cap.release()
cv2.destroyAllWindows()