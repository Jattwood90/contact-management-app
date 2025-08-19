#!/bin/bash
set -e

# Create the contacts table and load CSV data
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE TABLE IF NOT EXISTS contacts (
        id SERIAL PRIMARY KEY,
        first_name VARCHAR(50),
        last_name VARCHAR(50),
        address VARCHAR(200),
        city VARCHAR(100),
        state VARCHAR(2),
        zipcode VARCHAR(10),
        country VARCHAR(3),
        valid BOOLEAN DEFAULT true
    );

    -- Load CSV data into the table
    COPY contacts(first_name, last_name, address, city, state, zipcode, country, valid)
    FROM '/tmp/data.csv'
    DELIMITER ','
    CSV HEADER;

    -- Optional: Display count of loaded records
    SELECT COUNT(*) as total_contacts FROM contacts;
EOSQL

echo "Database initialization completed successfully!"