from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO('yolov8m.pt')  # downloads automatically on first run (~50MB)

    model.train(
        data='../../datasets/rdd2022/dataset.yaml',
        epochs=100,
        imgsz=640,
        batch=8,          # reduced from 16 to fit 6GB VRAM
        lr0=0.001,
        patience=20,      # auto-stop if val mAP doesn't improve for 20 epochs
        project='../../runs/rdd2022',
        name='yolov8m_rdd',
        device=0,         # use GPU 0 (your RTX 4050)
        workers=4,        # adjust down if you get CPU bottleneck warnings
        amp=True          # mixed precision — reduces VRAM usage, speeds up training
    )