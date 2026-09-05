import argparse
import sys
from pathlib import Path
import numpy as np
import torch
import cv2
import matplotlib.pyplot as plt
import warnings

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg
from train import build_groundingdino, run_inference
from torchvision import transforms as T

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    warnings.warn("rasterio not installed. Install with: pip install rasterio")

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_normalize = T.Normalize(mean=IMAGENET_MEAN.tolist(), std=IMAGENET_STD.tolist())

def load_and_convert_s2(patch_dir: Path, size: int = cfg.IMAGE_SIZE):
    if not RASTERIO_AVAILABLE:
        raise RuntimeError("rasterio is required.")
        
    patch_name = patch_dir.name
    channels = []
    raw_channels = []
    
    for band in cfg.RGB_BANDS:
        tif_path = patch_dir / f"{patch_name}_{band}.tif"
        with rasterio.open(tif_path) as src:
            native = src.read(1).astype(np.float32)
            raw_channels.append(native)
            
        p_lo = np.percentile(native, cfg.S2_PERCENTILE_LOW)
        p_hi = np.percentile(native, cfg.S2_PERCENTILE_HIGH)
        
        if p_hi <= p_lo:
            p_lo, p_hi = native.min(), native.max()
        if p_hi <= p_lo:
            channels.append(np.zeros_like(native))
            continue
            
        data = np.clip(native, p_lo, p_hi)
        data = (data - p_lo) / (p_hi - p_lo)
        
        if native.shape[0] != size or native.shape[1] != size:
            data = cv2.resize(data, (size, size), interpolation=cv2.INTER_LINEAR)
            
        channels.append(data)
        
    img = torch.from_numpy(np.stack(channels, axis=0))
    normalized_tensor = _normalize(img)
    
    # Create raw "blackish" image by just normalizing by a fixed large value (e.g., 4000 for S2)
    raw_img = np.stack(raw_channels, axis=-1)
    raw_img = np.clip(raw_img / 4000.0, 0, 1) # simple normalization to show it as dark
    
    return normalized_tensor, raw_img

def tensor_to_display_rgb(img_tensor: torch.Tensor) -> np.ndarray:
    img = img_tensor.cpu().numpy().transpose(1, 2, 0)
    img = img * IMAGENET_STD + IMAGENET_MEAN
    img = np.clip(img, 0.0, 1.0)
    img = (img * 255).astype(np.uint8)
    return img

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--conf", type=float, default=cfg.INFERENCE_CONF_THRESHOLD)
    parser.add_argument("--out", default="pipeline_graph.png")
    args = parser.parse_args()

    patch_dir = Path(args.patch)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    config_path = cfg.PRETRAINED_DIR / cfg.GDINO_CONFIG_FILES[cfg.MODEL_TYPE]
    weights_path = cfg.PRETRAINED_DIR / cfg.GDINO_WEIGHT_FILES[cfg.MODEL_TYPE]
    
    model = build_groundingdino(config_path, weights_path, device)
    model.eval()

    image_tensor, raw_img = load_and_convert_s2(patch_dir, size=cfg.IMAGE_SIZE)
    boxes, scores = run_inference(image_tensor, args.query, model, device, conf_threshold=args.conf)
    
    display_img = tensor_to_display_rgb(image_tensor)
    H, W = display_img.shape[:2]
    
    # Create the annotated image matching the exact styling of result.png / demo_inference_s2.py
    annotated_img = display_img.copy()
    for i, (box, score) in enumerate(zip(boxes, scores)):
        x1 = int(box[0].item() * W)
        y1 = int(box[1].item() * H)
        x2 = int(box[2].item() * W)
        y2 = int(box[3].item() * H)
        
        cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{score:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(annotated_img, (x1, y1 - th - 4), (x1 + tw + 4, y1), (0, 255, 0), -1)
        cv2.putText(annotated_img, label, (x1 + 2, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    cv2.putText(annotated_img, f"query: {args.query[:60]}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

    # CREATE THE GRAPH/PLOT
    fig = plt.figure(figsize=(24, 6))
    fig.suptitle(f"End-to-End Multi-Model Inference Pipeline", fontsize=18)

    # 1. Raw S2 Image (Dark)
    ax1 = plt.subplot(1, 4, 1)
    ax1.imshow(raw_img)
    ax1.set_title("1. Input Image\n(Raw S2 Blackish Image)")
    ax1.axis('off')

    # 2. Converted RGB Image
    ax2 = plt.subplot(1, 4, 2)
    ax2.imshow(display_img)
    ax2.set_title("2. Converted to RGB\n(Percentile Stretched)")
    ax2.axis('off')

    # 3. Model 1 Output (Text/Query generation)
    ax3 = plt.subplot(1, 4, 3)
    ax3.text(0.5, 0.5, f"Predicted Class / Query:\n\n'{args.query}'", 
             fontsize=16, ha='center', va='center', 
             bbox=dict(facecolor='white', alpha=0.8, edgecolor='black', boxstyle='round,pad=1'))
    ax3.set_xlim(0, 1)
    ax3.set_ylim(0, 1)
    ax3.set_title("3. Model 1 Output\n(Semantic Labels)")
    ax3.axis('off')
    
    # 4. Model 2 Output
    ax4 = plt.subplot(1, 4, 4)
    ax4.imshow(annotated_img)
    ax4.set_title("4. Model 2 Output\n(Grounding & Bounding Boxes)")
    ax4.axis('off')

    plt.tight_layout()
    # Ensure it saves as JPG if asked
    out_path = args.out
    if not out_path.lower().endswith('.jpg'):
        out_path = out_path.rsplit('.', 1)[0] + '.jpg'
    
    plt.savefig(out_path, bbox_inches='tight', dpi=150)
    print(f"Graph saved to {out_path}")

    # Also save the converted RGB "tif photo" representation as a separate JPG
    cv2.imwrite("input_photo.jpg", cv2.cvtColor(display_img, cv2.COLOR_RGB2BGR))
    print("Input photo saved to input_photo.jpg")

if __name__ == "__main__":
    main()
