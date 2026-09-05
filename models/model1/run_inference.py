"""
run_inference.py (model_1_x - Standalone Merged Model)
------------------------------------------------------
Turnkey inference runner for the fully merged GeoChat-7B model (100% offline).
Does NOT require downloading any weights from Hugging Face.

Usage:
    # 1. Interactive console:
    python run_inference.py

    # 2. Single question:
    python run_inference.py --image sample_images/sample_patch_1.png --question "What type of terrain is visible in this satellite image?"
"""

import os
import sys
import glob
import argparse
from pathlib import Path

import torch
from PIL import Image
from transformers import (
    AutoTokenizer,
    BitsAndBytesConfig,
    LlamaForCausalLM,
    CLIPImageProcessor,
)

ROOT_DIR = Path(__file__).resolve().parent
MERGED_DIR = ROOT_DIR / "merged_model"


def load_model(model_dir: str = str(MERGED_DIR), load_4bit: bool = True):
    print("\n" + "=" * 70)
    print("  LOADING STANDALONE OFFLINE MERGED MODEL (GEOCHAT-7B)")
    print("=" * 70)
    print(f"[*] Model Directory: {model_dir}")

    has_cuda = torch.cuda.is_available()
    if has_cuda and load_4bit:
        print("[*] Loading with 4-bit NF4 quantization (~7 GB VRAM footprint)...")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        model = LlamaForCausalLM.from_pretrained(
            model_dir,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )
    else:
        print("[*] Loading in full FP16 precision...")
        model = LlamaForCausalLM.from_pretrained(
            model_dir,
            device_map="auto" if has_cuda else "cpu",
            torch_dtype=torch.float16 if has_cuda else torch.float32,
            low_cpu_mem_usage=True,
        )

    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.unk_token or tokenizer.eos_token
    
    image_processor = CLIPImageProcessor.from_pretrained(model_dir)
    print("[+] Model loaded successfully and ready for inference!\n")
    return model, tokenizer, image_processor


def ask_geochat(model, tokenizer, image_processor, image_path: str, question: str, max_new_tokens: int = 128, temperature: float = 0.2) -> str:
    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image = Image.open(img_path).convert("RGB")
    prompt = f"<image>\nUSER: {question} ASSISTANT:"
    device = next(model.parameters()).device
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    _ = image_processor(images=image, return_tensors="pt")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=(temperature > 0.0),
            temperature=max(temperature, 1e-2),
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

    prompt_len = inputs["input_ids"].shape[1]
    generated_tokens = output_ids[0, prompt_len:]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()


def display_image(image_path: str):
    try:
        abs_p = os.path.abspath(image_path)
        if hasattr(os, "startfile"):
            os.startfile(abs_p)
        else:
            with Image.open(abs_p) as img:
                img.show()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Run inference with standalone merged GeoChat model")
    parser.add_argument("--model_dir", type=str, default=str(MERGED_DIR), help="Path to merged model directory")
    parser.add_argument("--image", type=str, default=None, help="Path to satellite image")
    parser.add_argument("--question", type=str, default=None, help="Question about the image")
    parser.add_argument("--max_tokens", type=int, default=128, help="Max new tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--no_4bit", action="store_true", help="Disable 4-bit quantization and load in full FP16")
    parser.add_argument("--no_display", action="store_true", help="Disable image popup window")
    args = parser.parse_args()

    model, tokenizer, image_processor = load_model(args.model_dir, load_4bit=(not args.no_4bit))

    img_path = args.image
    if not img_path:
        samples = glob.glob(str(ROOT_DIR / "sample_images" / "*.png"))
        img_path = samples[0] if samples else input("Enter image path: ").strip().strip('"')

    if not args.no_display and os.path.exists(img_path):
        display_image(img_path)

    if args.question:
        ans = ask_geochat(model, tokenizer, image_processor, img_path, args.question, args.max_tokens, args.temperature)
        print("\n" + "─" * 70)
        print(f"[?] Question: {args.question}")
        print(f"[+] Answer  :\n{ans}")
        print("─" * 70 + "\n")
        return

    presets = [
        "What type of terrain is visible in this remote sensing image?",
        "Describe the land cover visible in this satellite image.",
        "Is there significant vegetation present in this satellite patch?",
        "Estimate the vegetation density in this satellite image.",
        "Can you identify any water bodies in this satellite image?",
        "Are there signs of urban development or built-up areas in this image?",
        "What spectral characteristics can be identified in this Sentinel-2 image?",
        "Is this area predominantly natural or human-modified landscape?",
    ]

    print("\n" + "=" * 70)
    print("  OFFLINE GEOCHAT INTERACTIVE CONSOLE")
    print("=" * 70)
    print(f"Current Image: {img_path}\n")
    for idx, q in enumerate(presets, 1):
        print(f"  [{idx}] {q}")
    print("  [V] View / Re-open Image")
    print("  [C] Change Image")
    print("  [Q] Quit")
    print("=" * 70)

    while True:
        try:
            choice = input("\nEnter option (1-8 / question / V / C / Q): ").strip()
            if choice.lower() in ("q", "quit", "exit"):
                break
            if choice.lower() in ("v", "view"):
                display_image(img_path)
                continue
            if choice.lower() in ("c", "change"):
                new_p = input("Enter new image path: ").strip().strip('"')
                if os.path.exists(new_p):
                    img_path = new_p
                    display_image(img_path)
                continue
            selected_q = presets[int(choice) - 1] if (choice.isdigit() and 1 <= int(choice) <= len(presets)) else choice
            print("\nGenerating answer...")
            ans = ask_geochat(model, tokenizer, image_processor, img_path, selected_q, args.max_tokens, args.temperature)
            print("\n" + "─" * 70)
            print(f"[?] Question: {selected_q}")
            print(f"[+] Answer  :\n{ans}")
            print("─" * 70)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[!] Error: {e}")

if __name__ == "__main__":
    main()
