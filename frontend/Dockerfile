# Tax Assist AI — frontend image (Sprint 3 Wave F, design §3).
#
# Multi-stage: deps (npm ci) -> build (next build with the API URL baked
# in) -> runner (non-root, npm run start).
#
# NEXT_PUBLIC_API_URL is the BROWSER-REACHABLE base URL of the backend —
# it is inlined into the client bundle at BUILD time, so it must be the
# URL the user's browser uses, never a container-internal hostname:
#   - single-origin production (reverse proxy serves both apps): "" (empty)
#     — apiFetch then uses same-origin relative URLs;
#   - split-host production: e.g. https://api.your-app.example;
#   - local container dev: http://localhost:8000 (host-published port).
# docker-compose.yml passes it as a build arg (default "" for the
# single-origin topology).

# ---------------------------------------------------------------------------
# deps — install exact versions from package-lock.json
# ---------------------------------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------------
# build — NEXT_PUBLIC_API_URL is read at build time (Next.js inlines it)
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# ---------------------------------------------------------------------------
# runner — non-root runtime
# ---------------------------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -S -g 10001 app \
    && adduser -S -u 10001 -G app app
COPY --from=build --chown=app:app /app/package.json ./package.json
COPY --from=build --chown=app:app /app/node_modules ./node_modules
COPY --from=build --chown=app:app /app/.next ./.next
COPY --from=build --chown=app:app /app/public ./public
COPY --from=build --chown=app:app /app/next.config.ts ./next.config.ts

USER 10001:10001
EXPOSE 3000
CMD ["npm", "run", "start"]
