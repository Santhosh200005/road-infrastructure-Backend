from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO('runs/rdd2022/yolov8m_rdd-3/weights/last.pt')
    model.train(resume=True)