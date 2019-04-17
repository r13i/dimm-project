
# import ctypes as C
# import tisgrabber as IC
import cv2
import numpy as np
import matplotlib.pyplot as plt

# from sklearn.mixture import GaussianMixture
# import scipy.optimize as opt

from skimage.measure import label
from skimage import color
from skimage.morphology import extrema
from skimage import exposure




# Camera = IC.TIS_CAM()

# Devices = Camera.GetDevices()
# for i in range(len(Devices)):
# 	print(str(i) + " : " + str(Devices[i]))


camera_idx = -1
try:
	camera_idx = int(input("Please select a camera [Default: Built-in webcam] : "))
except ValueError:
	print("Not a valid index. Using built-in webcam.")


# gmm = GaussianMixture(n_components=2, covariance_type='diag')


if camera_idx == -1:
	print("Selecting built-in webcam ...")
	cam = cv2.VideoCapture(0)
	if not cam.isOpened():
		raise Exception("Could not open built-in camera device")


	fig = plt.figure()

	while True:
		_, frame = cam.read()
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		# _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_TOZERO)


		img = exposure.rescale_intensity(gray)

		local_maxima = extrema.local_maxima(img)
		label_maxima = label(local_maxima)
		overlay = color.label2rgb(label_maxima, img, alpha=0.7, bg_label=0, bg_color=None, colors=[(1, 0, 0)])

		h = 0.05
		h_maxima = extrema.h_maxima(img, h)
		label_h_maxima = label(h_maxima)
		overlay_h = color.label2rgb(label_h_maxima, img, alpha=0.7, bg_label=0, bg_color=None, colors=[(1, 0, 0)])


		# plt.subplot(131)
		# plt.imshow(img, cmap='gray', interpolation=None)
		# # plt.set_title('Original image')
		# plt.axis('off')

		# plt.subplot(132)
		# plt.imshow(overlay, interpolation='none')
		# # plt.set_title('Local Maxima')
		# plt.axis('off')

		# plt.subplot(133)
		# plt.imshow(overlay_h, interpolation='none')
		# # plt.set_title('h maxima for h = %.2f' % h)
		# plt.axis('off')
		# plt.pause(1e-2)

		cv2.imshow('Built-in camera', img)
		cv2.imshow('1', overlay)
		cv2.imshow('2', overlay_h)
		if cv2.waitKey(30) & 0xFF == ord('q'):
			break
	cam.release()
	cv2.destroyAllWindows()

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