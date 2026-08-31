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
app.use(helmet({ crossOriginResourcePolicy: false, crossOriginEmbedderPolicy: false }));

// CORS: allow-list from CORS_ORIGIN (comma-separated); defaults to all origins in development.
const corsOrigins = (process.env.CORS_ORIGIN ?? '*').split(',').map((o) => o.trim());
app.use(cors({
  origin: corsOrigins.includes('*') ? true : corsOrigins,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
app.use(morgan('dev'));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

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
  res.setHeader('Access-Control-Allow-Origin', '*');
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

// Start Server
const server = app.listen(PORT, () => {
  console.log(`[API Gateway] Running in ${process.env.NODE_ENV || 'development'} mode on port ${PORT}`);
});

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
