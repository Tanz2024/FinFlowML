FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN addgroup -S finflow && adduser -S -G finflow finflow
COPY --from=builder --chown=finflow:finflow /app/.next/standalone ./
COPY --from=builder --chown=finflow:finflow /app/.next/static ./.next/static
COPY --from=builder --chown=finflow:finflow /app/public ./public
USER finflow
EXPOSE 3000
CMD ["node", "server.js"]
