import rateLimit from 'express-rate-limit';

const windowMs = Number(process.env.RATE_LIMIT_WINDOW_MS ?? 15 * 60 * 1000);
const maxRequests = Number(process.env.RATE_LIMIT_MAX ?? 100);

// General rate limiter — trust proxy handled in index.ts
export const apiLimiter = rateLimit({
  windowMs,
  max: maxRequests,
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => (req as any).user?.userId || req.ip || 'unknown',
  message: {
    error: 'Too many requests, please try again after 15 minutes'
  }
});

// Stricter rate limiter specifically for file uploads
export const uploadLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 10, // Limit each IP to 10 upload requests per `window`
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: 'Too many upload attempts from this IP, please try again after 15 minutes'
  }
});
