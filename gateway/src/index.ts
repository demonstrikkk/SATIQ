import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs';

// Import routes
import authRouter from './routes/auth';
import sessionRouter from './routes/session';
import uploadRouter from './routes/upload';
import queryRouter from './routes/query';
import sttRouter from './routes/stt';

// Import middlewares
import { apiLimiter } from './middleware/rateLimiter';
import { authenticateToken } from './middleware/auth';

// Load environment variables
dotenv.config();

if (!process.env.JWT_SECRET) {
  console.warn('[auth] JWT_SECRET is not set — authentication endpoints will refuse to work until it is configured.');
}

const app = express();
const PORT = process.env.PORT || 4000;

// Security and Logging middleware — allow cross-origin images for chat (fix Preview unavailable)
app.set('trust proxy', 1);
app.use(helmet({ crossOriginResourcePolicy: false, crossOriginEmbedderPolicy: false }));

// CORS: explicit allow-list, no * in production. In prod CORS_ORIGIN must be set.
const corsOrigins = (process.env.CORS_ORIGIN ?? (process.env.NODE_ENV === 'production' ? '' : '*')).split(',').map((o) => o.trim()).filter(Boolean);
if (process.env.NODE_ENV === 'production' && corsOrigins.includes('*')) {
  console.error('[security] CORS_ORIGIN=* in production — refusing wildcard. Set CORS_ORIGIN to explicit origins.');
  process.exit(1);
}
app.use(cors({
  origin: corsOrigins.includes('*') ? true : corsOrigins.length ? corsOrigins : true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
}));
app.use(morgan('dev'));
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ limit: '2mb', extended: true }));

// Global API rate limiting
app.use('/api', apiLimiter);

// Health check endpoint (unprotected)
app.get('/health', (req: Request, res: Response) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

// Serve uploaded assets statically (used by AssetMeta.url)
// Robust for both ts-node-dev (gateway/src -> ../upload) and compiled (dist/gateway/src -> ../../../gateway/upload)
const candidates = [
  path.join(__dirname, '../upload'),
  path.resolve(__dirname, '../../../gateway/upload'),
  path.resolve(process.cwd(), 'gateway/upload'),
];
const uploadDir = candidates.find((p) => { try { return fs.existsSync(p); } catch { return false; } }) ?? candidates[0];
app.use('/api/assets', (req, res, next) => {
  res.setHeader('Cross-Origin-Resource-Policy', 'cross-origin');
  // CORS for assets respects main CORS_ORIGIN, not wildcard
  const origin = req.headers.origin as string | undefined;
  if (origin && (corsOrigins.includes('*') || corsOrigins.includes(origin))) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  }
  next();
}, express.static(uploadDir));

// Unprotected routes
app.use('/api/auth', authRouter);

// Protected routes (require valid JWT)
app.use('/api/session', authenticateToken as any, sessionRouter);
app.use('/api/upload', authenticateToken as any, uploadRouter);
app.use('/api/query', authenticateToken as any, queryRouter);
app.use('/api/stt', authenticateToken as any, sttRouter);

// Global Error Handler
app.use((err: any, req: Request, res: Response, next: NextFunction) => {
  console.error('Unhandled Error:', err.message);
  
  if (err instanceof Error && err.message.includes('Invalid file type')) {
    return res.status(400).json({ error: err.message });
  }
  
  return res.status(500).json({
    error: 'Internal Server Error',
    details: process.env.NODE_ENV === 'development' ? err.message : undefined
  });
});

// Start Server with keepalive tuned for long SSE (45s pipeline + 60s ingest + composer streaming)
const server = app.listen(PORT, () => {
  console.log(`[API Gateway] Running in ${process.env.NODE_ENV || 'development'} mode on port ${PORT}`);
});
server.keepAliveTimeout = 70000;
server.headersTimeout = 71000;
(server as any).timeout = 120000; // proxy fetch: 60s ingest + 45s pipeline

// Handle graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM signal received. Shutting down gracefully...');
  server.close(() => {
    console.log('HTTP server closed.');
  });
});

process.on('SIGINT', () => {
  console.log('SIGINT signal received. Shutting down gracefully...');
  server.close(() => {
    console.log('HTTP server closed.');
  });
});
