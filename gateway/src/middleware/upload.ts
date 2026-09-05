import multer from 'multer';
import path from 'path';
import fs from 'fs';

// Ensure upload directory exists
const uploadDir = path.join(__dirname, '../../upload');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const { randomUUID } = require('crypto');
    const uniqueSuffix = randomUUID();
    const ext = path.extname(file.originalname);
    const safe = file.fieldname.replace(/[^a-z0-9]/gi, '_');
    cb(null, safe + '-' + uniqueSuffix + ext);
  }
});

const fileFilter = (req: any, file: Express.Multer.File, cb: multer.FileFilterCallback) => {
  const allowedExtensions = ['.tif', '.tiff', '.geotiff', '.gtiff', '.png', '.jpg', '.jpeg', '.jp2'];
  const ext = path.extname(file.originalname).toLowerCase();
  // also validate mimetype prefix image/ or application/octet-stream for GeoTIFF
  const okMime = !file.mimetype || file.mimetype.startsWith('image/') || file.mimetype === 'application/octet-stream' || file.mimetype === 'image/tiff' || file.mimetype === 'image/geotiff' || file.mimetype === 'image/jp2';
  if (allowedExtensions.includes(ext) && okMime) {
    cb(null, true);
  } else {
    cb(new Error(`Invalid file type. Allowed formats: ${allowedExtensions.join(', ')}`));
  }
};

export const upload = multer({
  storage: storage,
  fileFilter: fileFilter,
  limits: {
    fileSize: 100 * 1024 * 1024 // 100MB limit
  }
});

export default upload;
