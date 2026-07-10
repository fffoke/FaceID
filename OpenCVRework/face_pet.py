import face_2

# Настройки для камеры KPP1 (HiWatch substream)
# RTSP URL для HiWatch камеры (substream канал 102)
face_2.CAMERA_URL = "rtsp://192.168.96.76:3666/h264_ulaw.sdp"
face_2.CAMERA_NAME = "ВЫХОД"
face_2.SHOW_WINDOW = False
face_2.ESP = 'http://192.168.97.79/open1?token=Hellosbtc2'
face_2.NOTIFY_NAMES = ['rahimova_zhanar_zekenovna']
face_2.SERVER_URL = 'http://127.0.0.1:8080/api/v1/recognitions'
face_2.ACTIVE_SESSION_URL = 'http://127.0.0.1:8080/api/v1/active-session'
# Дополнительно можно настроить параметры ниже при необходимости:
face_2.THRESHOLD = 0.5
# face.MIN_FRAMES_BETWEEN_EVENTS = 3
print("before:", face_2.SHOW_WINDOW)


# Перезагрузить базу лиц, если путь менялся
face_2.load_face_database()

if __name__ == "__main__":
    face_2.main()


