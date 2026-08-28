import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import dotenv from 'dotenv';
import path from 'path';

// Import routes
import authRouter from './routes/auth';
import sessionRouter from './routes/session';
import uploadRouter from './routes/upload';
import queryRouter from './routes/query';

// Import middlewares
import { apiLimiter } from './middleware/rateLimiter';
import { authenticateToken } from './middleware/auth';

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

// Security and Logging middleware
app.use(helmet());
app.use(cors({
  origin: '*', // Allow all origins in development; tighten in production
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
app.use(morgan('dev'));
app.use(express.json());

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

// Serve uploaded files statically (optional, for viewing overlays/masks)
app.use('/upload', express.static(path.join(__dirname, '../upload')));

// Unprotected routes
app.use('/api/auth', authRouter);

// Protected routes (require valid JWT)
app.use('/api/session', authenticateToken as any, sessionRouter);
app.use('/api/upload', authenticateToken as any, uploadRouter);
app.use('/api/query', authenticateToken as any, queryRouter);

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
