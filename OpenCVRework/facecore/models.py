"""Модели детекции и распознавания лиц.

YuNet и SFace из OpenCV не потокобезопасны, поэтому доступ к ним всегда
идёт через общий лок: их дёргают и основной цикл, и фоновая загрузка фото.
"""

import os
import threading

import cv2 as cv

# Больше этого размера YuNet начинает терять лица, поэтому фото ужимаются
MAX_PHOTO_DIM = 640


class FaceModels:
    def __init__(self, detector_path: str, recognizer_path: str, cv_threads: int = 2):
        for path in (detector_path, recognizer_path):
            if not os.path.exists(path):
                raise FileNotFoundError(f"❌ Файл модели не найден: {path}")

        cv.setNumThreads(cv_threads)
        self.detector = cv.FaceDetectorYN.create(detector_path, "", (640, 480))
        self.recognizer = cv.FaceRecognizerSF.create(recognizer_path, "")
        self.lock = threading.Lock()

    def detect(self, img):
        """Возвращает результат YuNet для кадра. Размер входа выставляется под кадр."""
        h, w = img.shape[:2]
        with self.lock:
            self.detector.setInputSize((w, h))
            return self.detector.detect(img)

    def embed(self, img, face_data):
        """Считает эмбеддинг одного найденного лица."""
        with self.lock:
            aligned = self.recognizer.alignCrop(img, face_data)
            return self.recognizer.feature(aligned)

    def embed_first_face(self, img):
        """Эмбеддинг первого лица на изображении или None. Для фото из папки faces/."""
        h, w = img.shape[:2]
        if max(h, w) > MAX_PHOTO_DIM:
            scale = MAX_PHOTO_DIM / max(h, w)
            img = cv.resize(img, (int(w * scale), int(h * scale)))
            h, w = img.shape[:2]

        with self.lock:
            self.detector.setInputSize((w, h))
            faces = self.detector.detect(img)
            if faces[1] is None:
                return None, (w, h)
            aligned = self.recognizer.alignCrop(img, faces[1][0])
            return self.recognizer.feature(aligned), (w, h)
