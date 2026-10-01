import cv2
import json
from detector import FishBarDetector
import config

def test_detector():
    img_path = "test_sample.png"
    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not load {img_path}")
        return

    h, w = img.shape[:2]
    print(f"Image dimensions: width={w}, height={h}")

    # Load default configuration
    cfg = config.load_config()
    detector = FishBarDetector(cfg)

    # Let's crop roughly where the fishing bar is in test_sample.png
    # In test_sample.png (from screenshot, right side of the screen):
    # The bar is visible on the right half. Let's find it or test full image first.
    res = detector.detect(img)
    print("\n--- Detection on full/cropped image ---")
    print("Is Active:", res["is_active"])
    print("White Box:", res["white_box"])
    print("Target Zone:", res["target_zone"])
    print("White Center Y:", res["white_center_y"])
    print("Target Center Y:", res["target_center_y"])
    print("Target Top/Bottom Y:", res["target_top_y"], res["target_bottom_y"])

    # Save output visualization
    if res["annotated_frame"] is not None:
        cv2.imwrite("test_detection_output.png", res["annotated_frame"])
        print("Saved annotated frame to test_detection_output.png")

if __name__ == "__main__":
    test_detector()
