FROM node:20-alpine
WORKDIR /app
COPY gateway/package.json gateway/package-lock.json* ./gateway/
COPY shared ./shared
WORKDIR /app/gateway
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev
COPY gateway/ ./
RUN npm run build
EXPOSE 4000
CMD ["node", "dist/gateway/src/index.js"]
