#!/usr/bin/env bash
# exit on error

set -o errexit

# Function to show usage
usage() {
    echo "Usage: $0 -u <username> -p <password> -d <database_name>"
    exit 1
}

# Check if arguments are provided
if [ "$#" -ne 6 ]; then
    usage
fi

# Parse arguments
while getopts ":u:p:d:" opt; do
    case $opt in
        u) USER="$OPTARG"
        ;;
        p) PASSWORD="$OPTARG"
        ;;
        d) DB_NAME="$OPTARG"
        ;;
        \?) echo "Invalid option -$OPTARG" >&2
            usage
        ;;
    esac
done

# Check that arguments are not empty
if [[ -z "$USER" || -z "$PASSWORD" || -z "$DB_NAME" ]]; then
    usage
fi

# Pull PostgreSQL image
echo "Pulling PostgreSQL image..."
docker pull postgres:latest

# Create and run the PostgreSQL container
echo "Creating and running PostgreSQL container..."
docker run -d \
    --name postgres_container \
    -e POSTGRES_DB="$DB_NAME" \
    -e POSTGRES_USER="$USER" \
    -e POSTGRES_PASSWORD="$PASSWORD" \
    -p 5432:5432 \
    postgres:latest

# Print connection string
echo "PostgreSQL is running. Connection string:"
echo "postgres://$USER:$PASSWORD@localhost:5432/$DB_NAME"
