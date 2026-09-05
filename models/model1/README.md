# User Guide: Standalone Merged Model (Model 1 X)

This package contains the **fully fused, 100% offline 13.5 GB model** (`merged_model/`) where the trained LoRA weights (Step 650) have been permanently baked into the base GeoChat-7B architecture.

---

## 🚀 Key Advantages of Model 1 X
- **Zero Internet Requirement:** No downloading from Hugging Face Hub. Everything is stored locally in `merged_model/`.
- **Plug-and-Play Backend:** Built-in FastAPI REST server for direct integration with Web and Mobile frontends.
- **Flexible Precision:** Run in 4-bit mode (~7 GB VRAM) or full FP16 (~14 GB VRAM).

---

## ⚡ Quickstart

### 1. Install Requirements
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

### 2. Run Interactive Console
```bash
python run_inference.py
```

### 3. Start REST API Server (For Frontend / Backend)
```bash
python api_server.py --port 8000
```
- Interactive Swagger UI: `http://localhost:8000/docs`
- Endpoint: `POST http://localhost:8000/api/v1/vqa` (Image upload + question)

### 4. JavaScript / React Frontend Call
```javascript
const formData = new FormData();
formData.append("image", fileInput.files[0]);
formData.append("question", "Describe the land cover in this satellite patch.");

const res = await fetch("http://localhost:8000/api/v1/vqa", {
  method: "POST",
  body: formData,
});
const data = await res.json();
console.log("Answer:", data.answer);
```
