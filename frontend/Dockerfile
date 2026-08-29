FROM node:20-alpine AS build
WORKDIR /app
ARG VITE_API_BASE=http://localhost:4000
ENV VITE_API_BASE=$VITE_API_BASE
COPY frontend/package.json frontend/package-lock.json* ./frontend/
WORKDIR /app/frontend
RUN npm ci 2>/dev/null || npm install
COPY frontend/ ./
COPY shared ../shared
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN npm i -g serve
COPY --from=build /app/frontend/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
