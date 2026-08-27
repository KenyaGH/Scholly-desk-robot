from picamera2 import Picamera2
import cv2

def main():
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam2.configure(config)
    picam2.start()
    print("Camera opened! Press 'q' to quit.")

    while True:
        frame = picam2.capture_array()
        cv2.imshow("Arducam Live Feed", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    picam2.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
