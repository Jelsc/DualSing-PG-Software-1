FROM node:22.14.0-bookworm-slim

WORKDIR /workspace
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
COPY test ./test
COPY README.md ./README.md
RUN npm run format:check && npm run build && npm test
