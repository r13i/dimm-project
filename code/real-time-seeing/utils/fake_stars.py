import random
import numpy as np

class FakeStars(object):

    def __init__(self, value = 255, height = 360, width = 480):
        self.value = value
        self.height = height
        self.width = width

        self.x1 = random.randint(a=40, b=self.width // 2 - 40)
        self.y1 = random.randint(a=40, b=self.height - 40)

        self.x2 = random.randint(a=self.width // 2 + 40, b=self.width - 40)
        self.y2 = random.randint(a=40, b=self.height - 40)

    def generate(self, rand_range=5):
        image = np.zeros(shape=(self.height, self.width))

        rand_x1 = self.x1 + random.randint(-rand_range, rand_range)
        rand_y1 = self.y1 + random.randint(-rand_range, rand_range)
        rand_radius1 = random.randint(5, 10)
        image[self._get_circle(rand_x1, rand_y1, rand_radius1)] = 255

        rand_x2 = self.x2 + random.randint(-rand_range, rand_range)
        rand_y2 = self.y2 + random.randint(-rand_range, rand_range)
        rand_radius2 = random.randint(5, 10)
        image[self._get_circle(rand_x2, rand_y2, rand_radius2)] = self.value

        return np.uint8(image)


    def _get_circle(self, center_x, center_y, radius):
        range_x = np.arange(0, self.width)
        range_y = np.arange(0, self.height)
        
        return (range_x[np.newaxis, :] - center_x) ** 2 + (range_y[:, np.newaxis] - center_y) ** 2 < radius ** 2


if __name__ == "__main__":
    fake = FakeStars()

    import cv2

    while True:
        image = fake.generate()

        cv2.imshow('test', image)

        if cv2.waitKey(500) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
