
from collections import deque
from time import clock
import numpy as np
import cv2
import matplotlib.pyplot as plt

from utils.fake_stars import FakeStars


THRESH          = 127       # Pixels below this value are set to 0

DIAMETER_GDIMM  = 0.06      # 6 cm
L               = 0.03      # 30 cm : The distance between two DIMM apertures
B               = L / DIAMETER_GDIMM
K_L = 0.364 * (1 - 0.532 * np.power(B, -1 / 3) - 0.024 * np.power(B, -7 / 3))
K_T = 0.364 * (1 - 0.798 * np.power(B, -1 / 3) - 0.018 * np.power(B, -7 / 3))

LAMBDA          = 0.0005    # 500 micro-meters
Z               = 45        # Zenithal angle (in degrees)

# Calculate values to make process faster
A = 0.98 * np.power(np.cos(Z), 0.6)
B = DIAMETER_GDIMM / (LAMBDA * K_L)
C = DIAMETER_GDIMM / (LAMBDA * K_T)



# Generating fake images of DIMM star (One single star that is split by the DIMM)
fake_stars = FakeStars()

# Storing the Delta X and Y in an array to calculate the Standard Deviation
arr_delta_x = deque(maxlen=100)
arr_delta_y = deque(maxlen=100)

arr_epsilon_x = deque(maxlen=100)
arr_epsilon_y = deque(maxlen=100)

fig = plt.figure()

try:

    while True:
        frame = fake_stars.generate()

    # cap = cv2.VideoCapture('recording.avi')
    # while(cap.isOpened()):
    #     ret, frame = cap.read()

        if frame is None or frame.size == 0:
            print("Frame is empty")
            continue

        tic = clock()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Fast thresholding
        _, thresholded = cv2.threshold(gray, THRESH, 255, cv2.THRESH_TOZERO)

        # # Slow thresholding
        # thresholded = np.where(gray > THRESH, gray, 0)




        # star_1 = thresholded[:, : thresholded.shape[1] // 2]
        # star_2 = thresholded[:, thresholded.shape[1] // 2 :]



        # _, contours, hierarchy = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        _, contours, hierarchy = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        # cv2.drawContours(frame, contours, -1, (0,0,255), 2)

        moments_star_1 = cv2.moments(contours[0])
        moments_star_2 = cv2.moments(contours[1])

        cX_star1 = int(moments_star_1["m10"] / moments_star_1["m00"])
        cY_star1 = int(moments_star_1["m01"] / moments_star_1["m00"])

        cX_star2 = int(moments_star_2["m10"] / moments_star_2["m00"]) # + frame.shape[1] // 2
        cY_star2 = int(moments_star_2["m01"] / moments_star_2["m00"])


        # Calcul Seeing ######################################################################
        delta_x = abs(cX_star2 - cX_star1)
        delta_y = abs(cY_star2 - cY_star1)

        arr_delta_x.append(delta_x)
        arr_delta_y.append(delta_y)

        sigma_x = np.std(arr_delta_x)
        sigma_y = np.std(arr_delta_y)

        # print(sigma_x, sigma_y)

        # Seeing
        epsilon_x = A * np.power(B * sigma_x, 0.2)
        epsilon_y = A * np.power(C * sigma_y, 0.2)

        toc = clock()
        elapsed = toc - tic
        print("Time elapsed: {} sec | Maximum FPS: {}".format(elapsed, round(1.0 / elapsed)))

        arr_epsilon_x.append(epsilon_x)
        arr_epsilon_y.append(epsilon_y)


        plt.subplot(211)
        plt.ylim(-5, 10)
        plt.title("Seeing on X axis")
        plt.plot(arr_epsilon_x, c='blue')

        plt.subplot(212)
        plt.ylim(-5, 10)
        plt.title("Seeing on Y axis")
        plt.plot(arr_epsilon_y, c='cyan')

        plt.tight_layout()
        plt.pause(1e-3)


        # Displaying #########################################################################
        cv2.drawMarker(frame, (cX_star1, cY_star1), color=(0, 0, 255), markerSize=30, thickness=1)
        cv2.drawMarker(frame, (cX_star2, cY_star2), color=(0, 0, 255), markerSize=30, thickness=1)

        cv2.imshow('image', frame)
        if cv2.waitKey(200) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

except KeyboardInterrupt:
    cv2.destroyAllWindows()
