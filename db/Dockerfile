FROM postgres:16-alpine

# Set environment variables
ENV POSTGRES_DB=postgres
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# Create directory for initialization scripts
RUN mkdir -p /docker-entrypoint-initdb.d
COPY data.csv /tmp/data.csv

# Create initialization script
# Copy initialization script
COPY init-db.sh /docker-entrypoint-initdb.d/01-init.sh
RUN chmod +x /docker-entrypoint-initdb.d/01-init.sh

# Expose PostgreSQL port
EXPOSE 5432