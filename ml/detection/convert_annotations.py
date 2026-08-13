import os
import xml.etree.ElementTree as ET
from PIL import Image
import shutil
import random

BASE = "../../datasets/rdd2022/raw"
COUNTRIES = ["Japan", "India", "Czech", "Norway", "United_States", "China_MotorBike", "China_Drone"]
CLASS_MAP = {"D00": 0, "D10": 1, "D20": 2, "D40": 3}


def find_image_path(ann_path):
    parts = ann_path.split(os.sep)
    if "train" not in parts:
        return None
    train_idx = parts.index("train")
    train_dir = os.sep.join(parts[:train_idx + 1])
    img_name = os.path.basename(ann_path).replace(".xml", ".jpg")
    return os.path.join(train_dir, "images", img_name)


def convert_xml_to_yolo(xml_path, img_width, img_height):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    lines = []
    for obj in root.findall("object"):
        cls_name = obj.find("name").text
        if cls_name not in CLASS_MAP:
            continue
        cls_id = CLASS_MAP[cls_name]

        bbox = obj.find("bndbox")
        xmin = float(bbox.find("xmin").text)
        ymin = float(bbox.find("ymin").text)
        xmax = float(bbox.find("xmax").text)
        ymax = float(bbox.find("ymax").text)

        x_center = ((xmin + xmax) / 2) / img_width
        y_center = ((ymin + ymax) / 2) / img_height
        w = (xmax - xmin) / img_width
        h = (ymax - ymin) / img_height

        lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}")
    return lines


def collect_all_annotations():
    all_files = []
    for country in COUNTRIES:
        ann_dir = os.path.join(BASE, country, "train", "annotations", "xmls")
        if not os.path.isdir(ann_dir):
            ann_dir = os.path.join(BASE, country, "train", "annotations")
        if not os.path.isdir(ann_dir):
            print(f"Skipping {country} — annotations folder not found")
            continue
        for fname in os.listdir(ann_dir):
            if fname.endswith(".xml"):
                all_files.append(os.path.join(ann_dir, fname))
    return all_files


def get_dominant_class(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    classes = [obj.find("name").text for obj in root.findall("object")]
    classes = [c for c in classes if c in CLASS_MAP]
    if not classes:
        return None
    return max(set(classes), key=classes.count)


def stratified_split(valid_pairs, train_ratio=0.7, val_ratio=0.2, seed=42):
    random.seed(seed)
    by_class = {"D00": [], "D10": [], "D20": [], "D40": [], "none": []}
    for ann_path, img_path in valid_pairs:
        dom = get_dominant_class(ann_path)
        key = dom if dom else "none"
        by_class[key].append((ann_path, img_path))

    train, val, test = [], [], []
    for cls, items in by_class.items():
        random.shuffle(items)
        n = len(items)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        train += items[:n_train]
        val += items[n_train:n_train + n_val]
        test += items[n_train + n_val:]
        print(f"  {cls}: {n} total -> train {n_train}, val {n_val}, test {n - n_train - n_val}")

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)
    return train, val, test


def process_split(pairs, split_name, output_base="../../datasets/rdd2022"):
    img_out_dir = os.path.join(output_base, "images", split_name)
    label_out_dir = os.path.join(output_base, "labels", split_name)
    os.makedirs(img_out_dir, exist_ok=True)
    os.makedirs(label_out_dir, exist_ok=True)

    skipped = 0
    for ann_path, img_path in pairs:
        try:
            with Image.open(img_path) as im:
                w, h = im.size
        except Exception:
            skipped += 1
            continue

        yolo_lines = convert_xml_to_yolo(ann_path, w, h)

        parts = ann_path.split(os.sep)
        country = parts[parts.index("raw") + 1] if "raw" in parts else "unk"
        base_name = f"{country}_{os.path.splitext(os.path.basename(img_path))[0]}"

        shutil.copy(img_path, os.path.join(img_out_dir, base_name + ".jpg"))

        with open(os.path.join(label_out_dir, base_name + ".txt"), "w") as f:
            f.write("\n".join(yolo_lines))

    print(f"  {split_name}: processed {len(pairs)} pairs, skipped {skipped} unreadable images")


if __name__ == "__main__":
    print("Collecting annotation files across all countries...")
    all_annotations = collect_all_annotations()
    print(f"Total annotation files found: {len(all_annotations)}")

    valid_pairs = []
    for ann_path in all_annotations:
        img_path = find_image_path(ann_path)
        if img_path and os.path.exists(img_path):
            valid_pairs.append((ann_path, img_path))

    print(f"Valid annotation-image pairs: {len(valid_pairs)}")

    print("\nSplitting dataset (stratified by dominant class)...")
    train, val, test = stratified_split(valid_pairs)
    print(f"\nFinal split sizes -> train: {len(train)}, val: {len(val)}, test: {len(test)}")

    print("\nProcessing train split (this will take a while)...")
    process_split(train, "train")
    print("Processing val split...")
    process_split(val, "val")
    print("Processing test split...")
    process_split(test, "test")

    print("\nDone! Check datasets/rdd2022/images/ and datasets/rdd2022/labels/")