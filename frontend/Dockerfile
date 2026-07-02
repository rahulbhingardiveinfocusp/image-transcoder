#./frontend/Dockerfile
FROM node:24 AS build
WORKDIR /app
COPY . .

ARG BACKEND_API_URL
ARG COGNITO_USER_POOL_ID
ARG COGNITO_CLIENT_ID
ARG COGNITO_REGION

RUN npm ci
RUN sed -i "s#BACKEND_API_URL_PLACEHOLDER#${BACKEND_API_URL}#g"         src/environments/environment.prod.ts && \
    sed -i "s#COGNITO_USER_POOL_ID_PLACEHOLDER#${COGNITO_USER_POOL_ID}#g" src/environments/environment.prod.ts && \
    sed -i "s#COGNITO_CLIENT_ID_PLACEHOLDER#${COGNITO_CLIENT_ID}#g"      src/environments/environment.prod.ts && \
    sed -i "s#COGNITO_REGION_PLACEHOLDER#${COGNITO_REGION}#g"            src/environments/environment.prod.ts
RUN npm run build -- --configuration=production

FROM nginx:alpine
COPY --from=build /app/dist/*/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80