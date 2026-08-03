import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { v4 as uuidv4 } from 'uuid';
import { config } from '../config';

const ALLOWED_MIME = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
]);

const MIME_TO_EXT: Record<string, string> = {
  'image/jpeg': '.jpg',
  'image/png':  '.png',
  'image/webp': '.webp',
  'image/heic': '.heic',
  'image/heif': '.heic',
};

// Ensure uploads dir exists at startup
fs.mkdirSync(config.uploadsDir, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, config.uploadsDir),
  filename: (_req, file, cb) => {
    const ext =
      path.extname(file.originalname).toLowerCase() ||
      MIME_TO_EXT[file.mimetype] ||
      '.jpg';
    cb(null, `${uuidv4()}${ext}`);
  },
});

export const upload = multer({
  storage,
  limits: { fileSize: 8 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    if (ALLOWED_MIME.has(file.mimetype)) {
      cb(null, true);
    } else {
      cb(Object.assign(new Error('invalid_file_type'), { code: 'INVALID_FILE_TYPE' }));
    }
  },
});

// URL stored in DB is /uploads/<filename>; derive filesystem path from it
export function deleteFileByUrl(url: string): void {
  const filename = path.basename(url);
  const fullPath = path.join(config.uploadsDir, filename);
  fs.unlink(fullPath, () => {});
}
